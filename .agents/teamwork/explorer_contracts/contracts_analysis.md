# Interaction Rooms & Analytics Dashboards Contracts Analysis

## Executive Summary

This report establishes the architectural contracts, API specifications, and data flows for VoxPrep's frontend rebuild, covering the core interaction rooms (`/interview` and `/coach`), analytics dashboards (`/analytics/interview` and `/analytics/communication`), and user state management. 

All specifications are strictly aligned with the authoritative FastAPI backend (`backend/app/main.py`, `backend/app/routers/`, `backend/app/models/report.py`, and `backend/schema.sql`).

---

## 1. WebRTC & Voice Pipeline Architecture

### 1.1 Candidate Camera & Microphone Stream Handling
- **Next.js Client Environment**: All media capture must execute inside `"use client"` components inside `useEffect` or user event triggers. Never execute `navigator.mediaDevices` during SSR.
- **Stream Acquisition**:
  ```typescript
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
    audio: { echoCancellation: true, noiseSuppression: true }
  });
  ```
- **Preview `<video>` Binding**:
  - Bind to video ref: `videoRef.current.srcObject = stream;`
  - HTML Attributes: `<video ref={videoRef} autoPlay playsInline muted />`.
  - **Critical**: The `muted` attribute is mandatory on the candidate's self-preview to prevent severe audio feedback loops and browser autoplay blocks.
- **Stream Cleanup**:
  - On component unmount or room exit:
    ```typescript
    stream.getTracks().forEach((track) => track.stop());
    ```
  - On toggle controls:
    - Camera toggle: `videoTrack.enabled = !videoTrack.enabled` (avoids re-prompting permissions).
    - Mic toggle: `audioTrack.enabled = !audioTrack.enabled`.
- **Permission Fallbacks**: Catch `NotAllowedError` / `NotFoundError` and render a fallback candidate avatar with status badge, ensuring the user is never blocked from completing the interview.

### 1.2 Audio Recording & `POST /voice/process` Contract
- **Recording via `MediaRecorder`**:
  ```typescript
  let mimeType = "audio/webm;codecs=opus";
  if (!MediaRecorder.isTypeSupported(mimeType)) {
    mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
  }
  const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
  ```
- **Backend Endpoint**: `POST /voice/process`
  - **Content-Type**: `multipart/form-data`
  - **Payload Parameters**:
    | Parameter | Type | Required | Description |
    |---|---|---|---|
    | `file` | Binary Blob / File | Yes | Audio blob recorded from client microphone (`audio.wav` or `user_recording.webm`) |
    | `agent_type` | string (Form) | No (default: `"interview"`) | `"interview"` or `"coach"` |
    | `session_id` | string (Form) | No | Active interview or coach session UUID |
    | `conversation_history` | string (Form) | No | Optional conversation context |
  - **Backend Validation**: Payloads under 12 bytes trigger a safe fallback response without crashing:
    `{ transcript: "", spoken_response: "Could not understand. Please try again.", audio_base64: null, session_id }`.
  - **Response Model (`VoiceProcessResponse`)**:
    ```typescript
    interface VoiceProcessResponse {
      transcript: string;
      spoken_response: string;
      audio_base64: string | null;
      session_id?: string | null;
    }
    ```

### 1.3 Spoken Audio Playback
- **Response Payloads from Core Routers**:
  - `POST /interview/start` returns `{ session_id: string, opening_message: string }`.
  - `POST /interview/respond` returns `{ spoken_response: string, is_complete: boolean, ... }`.
  - `POST /coach/start` returns `{ session_id: string, opening_message: string, mode: string }`.
  - `POST /coach/respond` returns `{ coach_message: string, correction: CoachCorrection | null, next_prompt: string }`.
  - *Observation*: The core interview and coach endpoints return natural spoken response strings, not binary audio.
- **Playback Implementation**:
  - Primary Playback: Browser native Web Speech API (`window.speechSynthesis`) via `speakText(text, options)`.
  - Fallback / Base64 Audio: If `audio_base64` is returned by `POST /voice/process`, it can be played directly via `new Audio("data:audio/wav;base64," + audio_base64).play()` or `<VoicePlayer audioBase64={...} />`.
  - **Chromium Garbage Collection Fix**: Retain a module-scoped reference `let activeUtterance: SpeechSynthesisUtterance | null = null;` to prevent Chromium from cutting speech playback mid-sentence.
  - **Lifecycle Cleanup**: Call `window.speechSynthesis.cancel()` upon route change or unmount.

### 1.4 Turn-Taking Lifecycle (Interview Room)
```
1. [Lobby Configuration]
   - Candidate sets name, role, experience_level, and interview_type ('technical' | 'hr').
2. [POST /interview/start]
   - Returns { session_id, opening_message }.
3. [AI Opening Greeting]
   - Agent speaks opening_message via Web Speech API / TTS.
   - UI reflects AI speaking state (visual pulse).
4. [Candidate Answer]
   - Candidate clicks Record or speaks.
   - MediaRecorder captures audio blob.
5. [STT Transcription]
   - Audio blob submitted to POST /voice/process (multipart/form-data).
   - Returns transcript.
6. [Agent Evaluation & Progression]
   - Transcript submitted to POST /interview/respond:
     { session_id, answer_text: transcript }.
   - Evaluates 4 rubric dimensions (Relevance, Clarity, Depth, Examples).
   - Returns { spoken_response, is_complete, follow_up_or_next, question_index, total_questions }.
7. [AI Spoken Response]
   - Agent speaks spoken_response.
   - If !is_complete: loop to Step 4.
   - If is_complete:
8. [Session Conclusion]
   - Client calls POST /interview/end with { session_id }.
   - Backend compiles InterviewReport and finalizes record in Supabase.
   - Store report in Zustand (setLatestEvaluation).
   - Redirect to /analytics/interview.
```

---

## 2. Communication Coach Room Architecture

### 2.1 The 3 Backend Coach Modes
The frontend mode selector must directly map to the 3 exact backend modes defined in `backend/app/agents/coach.py`:
1. `conversation`:
   - Natural conversational fluency, everyday topics (travel, hobbies, daily routines).
   - Evaluates conversational momentum and relaxed pacing over rigid grammar rules.
2. `answer_training`:
   - Professional interview answer structuring using the STAR framework (Situation, Task, Action, Result).
   - Focuses on conciseness, measurable metrics, and quantifying impact.
3. `english_improvement`:
   - Grammar, sentence structure, tense accuracy (e.g. past tense irregular verbs), and filler word elimination.
   - Strictly capped at 1–2 gentle, actionable corrections per turn.

*Note for Implementation*: Remove previous frontend mode aliases (`"star"`, `"fluency"`, `"vocab"`). Directly use `"conversation"`, `"answer_training"`, and `"english_improvement"`.

### 2.2 Opening Message & Next Prompt Handling
- **Start**: `POST /coach/start` with `{ user_id: string, mode: string }`.
  - Backend generates mode-specific opening message and initial exercise prompt.
  - UI stores `opening_message` as the initial active prompt.
- **Turn Progression**: `POST /coach/respond` with `{ session_id: string, user_text: string }`.
  - Returns:
    - `coach_message`: Supportive conversational feedback.
    - `correction`: Structural linguistic correction model or `null`.
    - `next_prompt`: Next challenge or question for the user.
  - UI updates active prompt to `next_prompt` and plays/renders `coach_message`.
- **End**: `POST /coach/end` with `{ session_id: string }`.
  - Updates user communication profile in Supabase.
  - Returns session summary and updated profile; redirects to `/analytics/communication`.

### 2.3 Linguistic Correction UI Contract
Backend Model (`CoachCorrection` in `backend/app/routers/coach.py:42-47`):
```typescript
interface CoachCorrection {
  original: string; // The phrase that needed improvement
  improved: string; // Recommended alternative
  reason: string;   // Explanation of why the improvement is suggested
}
```

UI Card Structure:
- **Correction State (`correction !== null`)**:
  - Container: Dark card (`#0F172A` / `#111A2E`, border `#1E293B`).
  - Original Utterance: Strikethrough style in muted slate (`text-slate-400 line-through text-xs font-mono`).
  - Improved Alternative: Highlighted in vibrant emerald (`text-emerald-400 font-semibold text-sm`).
  - Rationale: Contextual explanation (`text-slate-300 italic text-xs mt-1`).
- **Clean Utterance State (`correction === null`)**:
  - Container with emerald accent border.
  - Displays positive feedback badge: "Clear expression — no correction needed".

### 2.4 Live Client-Side WPM & Filler Word Detection
- **Real-Time Client Detection (Chrome / Edge / Safari Web Speech Recognition)**:
  During recording, initialize `SpeechRecognition` in parallel with `MediaRecorder`:
  ```typescript
  const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
  recognition.continuous = true;
  recognition.interimResults = true;
  
  recognition.onresult = (event) => {
    const liveText = Array.from(event.results).map((r) => r[0].transcript).join(" ");
    const elapsedMinutes = (Date.now() - startTimeMs) / 60000;
    const wordCount = liveText.trim().split(/\s+/).filter(Boolean).length;
    const liveWpm = elapsedMinutes > 0 ? Math.round(wordCount / elapsedMinutes) : 0;
    
    // Scan for filler words
    const FILLERS = ["um", "uh", "like", "basically", "actually", "you know", "sort of", "kind of"];
    let detectedCount = 0;
    FILLERS.forEach((filler) => {
      const matches = liveText.match(new RegExp(`\\b${filler}\\b`, "gi"));
      if (matches) detectedCount += matches.length;
    });
    
    setLiveWpm(liveWpm);
    setLiveFillers(detectedCount);
  };
  ```
- **Fallback / Reconciliation**:
  If browser does not support `SpeechRecognition`, use `durationSeconds` from `MediaRecorder` and the authoritative transcript from `POST /voice/process`:
  ```typescript
  const wpm = durationSeconds > 0 ? Math.round((transcript.split(/\s+/).length / durationSeconds) * 60) : 0;
  const fillers = detectFillerWords(transcript);
  ```

---

## 3. Guest vs Authenticated User State Flow in Zustand

### 3.1 Backend Contract Comparison
| Endpoint | `user_id` Parameter | Database Table | Constraint |
|---|---|---|---|
| `POST /interview/start` | `user_id: Optional[str] = Field(None)` | `interview_sessions.user_id` | Nullable (`ON DELETE SET NULL`). Guest access fully supported with `user_id = null`. |
| `POST /coach/start` | `user_id: str = Field(..., min_length=1)` | `coach_sessions.user_id` | Requires non-empty string. `coach_persistence.py:321` auto-provisions a baseline profile for any user ID. |

### 3.2 Zustand State Architecture (`frontend/store/useStore.ts`)
To eliminate mocked bloat while supporting guest & authenticated flows:
- **Clean Store Shape**:
  ```typescript
  interface AppState {
    // Auth State
    user: AuthUser | null;
    guestId: string; // Generated once per client (UUID)
    setUser: (user: AuthUser | null) => void;
    
    // Active Sessions
    activeInterviewSessionId: string | null;
    setActiveInterviewSessionId: (id: string | null) => void;
    activeCoachSessionId: string | null;
    setActiveCoachSessionId: (id: string | null) => void;
    
    // Report Payloads
    latestInterviewReport: BackendInterviewReport | null;
    setLatestInterviewReport: (report: BackendInterviewReport | null) => void;
    latestCoachSummary: CoachEndResponse | null;
    setLatestCoachSummary: (summary: CoachEndResponse | null) => void;
  }
  ```
- **Guest ID Strategy**:
  - Initialize `guestId` in store: `crypto.randomUUID()` or fallback `00000000-0000-0000-0000-000000000001` (from `schema.sql` seed).
  - When starting interview: pass `user?.id || undefined`.
  - When starting coach: pass `user?.id || guestId` (satisfies `min_length=1` requirement).
- **Mock Bloat Elimination**:
  - Remove all pre-seeded mock resumes, fake 2026 sessions, and hardcoded question arrays.

---

## 4. Score Normalization Contract

### 4.1 Backend 1.0–10.0 Scale vs Frontend 0–100% Display
All scores stored and returned by the backend (`report.py:9-35`) adhere to the 1.0–10.0 rubric scale:
- `overall_score`: float (1.0 to 10.0, e.g., `8.8`)
- `dimension_scores.relevance`: float (1.0 to 10.0, e.g., `9.2`)
- `dimension_scores.clarity`: float (1.0 to 10.0, e.g., `8.8`)
- `dimension_scores.depth`: float (1.0 to 10.0, e.g., `8.6`)
- `dimension_scores.examples`: float (1.0 to 10.0, e.g., `8.0`)
- `question_breakdown[i].scores`: float (1.0 to 10.0)

### 4.2 Normalization Algorithm
Per requirement R4 and acceptance criteria:
```typescript
export function normalizeScore(score?: number | null, fallback = 0): number {
  if (score === undefined || score === null || isNaN(score)) return fallback;
  return score <= 10 ? Math.round(score * 10) : Math.round(score);
}
```

### 4.3 Test Matrix
| Raw Backend Score | Normalized UI Display | Description |
|---|---|---|
| `1.0` | `10%` | Minimum rubric score |
| `7.5` | `75%` | Competent score |
| `8.8` | `88%` | Strong performance |
| `9.2` | `92%` | Exemplary score |
| `10.0` | `100%` | Maximum possible rubric score |
| `88` (Legacy 100-pt) | `88%` | Preserved without double multiplication |
| `null` / `undefined` | `fallback` | Safe boundary handling |

---

## 5. Analytics Dashboards Structure

### 5.1 Interview Report (`/analytics/interview`)
Directly maps to `backend/app/models/report.py`:
- **Overall Score**: Hero score card displaying `normalizeScore(report.overall_score)%`.
- **4 Dimension Scores**:
  - Relevance: `normalizeScore(report.dimension_scores.relevance)%`
  - Clarity: `normalizeScore(report.dimension_scores.clarity)%`
  - Technical Depth: `normalizeScore(report.dimension_scores.depth)%`
  - Examples: `normalizeScore(report.dimension_scores.examples)%`
- **Summary**: `report.summary` (Executive performance synopsis).
- **Coach Recommendation**: `report.coach_recommendation` accompanied by CTA button linking directly to `/coach`.
- **Key Strengths**: List of strings from `report.strengths`.
- **Areas for Improvement**: List of strings from `report.areas_for_improvement` (or backward-compatible `report.weaknesses`).
- **Action Items**: List of strings from `report.action_items` (or backward-compatible `report.improvement_tips`).
- **Question Breakdown Table**:
  - Columns: Question, Answer Summary, Scores (4 dimensions normalized to 0-100%), Specific Feedback.

### 5.2 Communication Report (`/analytics/communication`)
Directly maps to `CoachEndResponse` from `POST /coach/end` (`backend/app/routers/coach.py:80-88`):
- **Speaking Pace**: `summary.avg_wpm` (Target: 130–150 WPM).
- **Filler Word Count**: `summary.total_fillers` (Target: < 3 per minute).
- **Grammar Score**: `summary.grammar_score` (Percentage).
- **Fluency Tier**: `summary.fluency_tier` (e.g. "Proficient", "Intermediate", "Advanced").
- **Coach Insight**: `summary.encouragement`.
- **Key Learnings**: List of strings from `summary.key_learnings`.
- **Logged Linguistic Corrections**: Render list of `{ original, improved, reason }` logged during the session.
- **Updated Profile Tags**: `profile_updated.skill_level`, `profile_updated.weak_areas`, `profile_updated.strong_areas`.

---

## 6. Crucial Recommendations & Scope Boundary Rules

1. **Remove Resume Upload Feature**:
   The backend API has no resume upload endpoint. `InterviewStartRequest` requires only `candidate_name`, `role`, `experience_level`, `interview_type`, and optional `user_id`. Remove `ResumeUploadModal.tsx`, `resumeParser.ts`, and `frontend/app/api/parse-resume/route.ts` to strictly adhere to R1.
2. **Eliminate Mode Aliases in Coach Room**:
   Use exact backend modes: `'conversation'`, `'answer_training'`, `'english_improvement'`.
3. **Turn-Taking Coordination**:
   Use `POST /voice/process` to obtain `transcript`, then pass that transcript to `POST /interview/respond` or `POST /coach/respond`. Speak the agent's authoritative response returned from the session router.
4. **Zustand State Cleanup**:
   Purge all hardcoded mock sessions from `useStore.ts`.
