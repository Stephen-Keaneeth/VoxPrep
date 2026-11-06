# Handoff Report: Interaction Rooms & Analytics Dashboards Contracts

## 1. Observation

1. **Backend Voice Router (`backend/app/routers/voice.py:35-46`)**:
   - `POST /voice/process` takes `multipart/form-data`:
     ```python
     async def process_voice(
         file: UploadFile = File(..., description="WAV/audio blob recorded from client microphone"),
         agent_type: Optional[str] = Form("interview"),
         session_id: Optional[str] = Form(None),
         conversation_history: Optional[str] = Form(None),
     ) -> VoiceProcessResponse
     ```
   - Payloads < 12 bytes (`voice.py:67`) return safe fallback:
     ```python
     if not content or len(content) < 12:
         return VoiceProcessResponse(
             transcript="",
             spoken_response=FALLBACK_STT_PROMPT,
             audio_base64=None,
             session_id=session_id,
         )
     ```
   - `audio_base64` is returned as `Optional[str]` (base64-encoded WAV). If TTS is unavailable, `audio_base64=None` with note at `voice.py:118`:
     `logger.info("TTS returned None; frontend will utilize Web Speech API fallback.")`

2. **Backend Interview Router (`backend/app/routers/interview.py:45-83`)**:
   - `InterviewStartRequest` (`interview.py:45-60`):
     ```python
     class InterviewStartRequest(BaseModel):
         candidate_name: str
         role: str
         experience_level: str
         interview_type: str  # 'hr' or 'technical'
         user_id: Optional[str] = Field(None)
     ```
   - `InterviewStartResponse` (`interview.py:62-66`):
     `session_id: str`, `opening_message: str` (spoken intro + 1st question).
   - `InterviewRespondRequest` & `InterviewRespondResponse` (`interview.py:68-83`):
     Accepts `session_id: str, answer_text: str`.
     Returns: `spoken_response: str, is_complete: bool, follow_up_or_next: str, question_index: int, current_question_index: int, total_questions: int = 5`.
   - `InterviewEndRequest` & `InterviewEndResponse` (`interview.py:84-95`):
     Returns `session_id, status: "completed", message: str, report: Dict[str, Any]`.
   - `GET /interview/report/{session_id}` (`interview.py:255-289`):
     Returns `InterviewReport` payload.

3. **Backend Coach Router (`backend/app/routers/coach.py:42-88`)**:
   - `CoachStartRequest` (`coach.py:49-54`):
     ```python
     class CoachStartRequest(BaseModel):
         user_id: str = Field(..., min_length=1)
         mode: str = Field(...)  # 'conversation', 'answer_training', 'english_improvement'
     ```
   - `CoachCorrection` model (`coach.py:42-47`):
     ```python
     class CoachCorrection(BaseModel):
         original: str
         improved: str
         reason: str
     ```
   - `CoachRespondResponse` (`coach.py:68-73`):
     `coach_message: str`, `correction: Optional[CoachCorrection] = Field(None)`, `next_prompt: str`.
   - `CoachEndResponse` (`coach.py:80-88`):
     `session_id: str, status: str, summary: Dict[str, Any], profile_updated: Dict[str, Any]`.

4. **Interview Evaluation Report Model (`backend/app/models/report.py:9-35`)**:
   - `overall_score: float` (1.0 to 10.0 scale)
   - `dimension_scores: DimensionScores`:
     - `relevance: float` (1.0 to 10.0)
     - `clarity: float` (1.0 to 10.0)
     - `depth: float` (1.0 to 10.0)
     - `examples: float` (1.0 to 10.0)
   - `strengths: List[str]`
   - `areas_for_improvement: List[str]` (mirrored by `weaknesses`)
   - `action_items: List[str]` (mirrored by `improvement_tips`)
   - `coach_recommendation: Optional[str]`
   - `summary: Optional[str]`
   - `question_breakdown: List[QuestionBreakdownItem]`

5. **Existing Frontend Gaps (`frontend/store/useStore.ts`, `frontend/components/sections/InterviewAgent.tsx`, `CommunicationAgent.tsx`)**:
   - `useStore.ts:67-179`: Stores hardcoded mock resume, hardcoded fake 2026 sessions (`interviewHistory`, `coachHistory`), and fake user `user-101`.
   - `InterviewAgent.tsx`: Mounts a `ResumeUploadModal.tsx` and loads questions from resume, whereas the backend has no resume upload endpoint.
   - `CommunicationAgent.tsx:26`: Uses internal modes `"star" | "fluency" | "vocab"` instead of the exact backend mode values `"answer_training" | "conversation" | "english_improvement"`.
   - `frontend/app/api/parse-resume/route.ts`: A Next.js API route not backed by any backend endpoint, violating R1.

---

## 2. Logic Chain

1. **WebRTC & Preview (from Observation 1 & 2)**:
   - Candidate camera/mic streams must be captured via `navigator.mediaDevices.getUserMedia` in client components (`"use client"`).
   - The preview `<video>` element must be tagged with `autoPlay playsInline muted` to avoid acoustic feedback and mobile autoplay blocks.
   - Explicit cleanup `stream.getTracks().forEach(t => t.stop())` is mandatory in unmount hooks to prevent camera hardware locks.
2. **Audio & Turn-Taking Pipeline (from Observation 1, 2, and 3)**:
   - `POST /voice/process` operates as the speech-to-text bridge. It accepts `multipart/form-data` with a binary `file` field.
   - Because `POST /voice/process` does not manage the structured session state (it is a standalone STT -> LLM -> TTS pipeline), the candidate's turn-taking flow must submit the returned `transcript` to `POST /interview/respond` or `POST /coach/respond`.
   - Because the session routers return text strings (`spoken_response` and `coach_message + next_prompt`), spoken playback in the browser is executed via Web Speech API (`speakText()`), with fallback to `audio_base64` whenever returned from `POST /voice/process`.
3. **Coach Room Modes (from Observation 3)**:
   - Backend `VALID_COACH_MODES` are strictly `{"conversation", "answer_training", "english_improvement"}`.
   - Mode selector must expose these exact 3 keys without custom aliases.
   - `CoachCorrection` `{ original, improved, reason }` must be rendered directly as a refinement card when returned, with a positive status badge when `null`.
   - Live WPM and filler word detection can run client-side during recording via `SpeechRecognition` / `webkitSpeechRecognition`, reconciled upon recording stop.
4. **User Auth & State Flow (from Observation 2, 3, and 5)**:
   - `/interview` supports guest access directly because `user_id` is `Optional[str] = Field(None)`.
   - `/coach` requires `user_id: str = Field(..., min_length=1)`. To support guest access in `/coach`, a persistent guest ID (e.g. UUID) must be generated for unauthenticated visitors so the backend can initialize a baseline profile.
   - Zustand store (`useStore.ts`) must be stripped of all hardcoded mock resumes and historical sessions, storing only active session IDs and live report payloads.
5. **Score Normalization (from Observation 4)**:
   - The backend stores and returns scores strictly on a 1.0–10.0 scale.
   - The UI display formula `score <= 10 ? Math.round(score * 10) : score` accurately maps 1.0–10.0 scores to 0–100% percentages (e.g. `8.8 -> 88%`), while safely preserving values that are already 0–100.

---

## 3. Caveats

- **Web Speech API Browser Variance**: Browser support for `SpeechSynthesis` and `SpeechRecognition` varies (e.g. Chrome supports `webkitSpeechRecognition`, Firefox does not). The recommended implementation includes a fallback using elapsed recording time and post-STT token counting.
- **Backend Service Availability**: Live NVIDIA Parakeet and Nemotron NIM services depend on active environment API keys. If keys are mock or offline, the backend returns deterministic mock responses that follow identical schemas.
- **Database RLS Policies**: Backend uses permissive RLS policies for hackathon/development mode. Authenticated vs guest sessions do not require JWT authorization headers for read/write access.

---

## 4. Conclusion

The interaction rooms and analytics dashboards must be implemented strictly against the 9 backend endpoints:
1. `GET /health`
2. `POST /auth/register`
3. `POST /auth/login`
4. `POST /voice/process`
5. `POST /interview/start`
6. `POST /interview/respond`
7. `POST /interview/end`
8. `GET /interview/report/{session_id}`
9. `POST /coach/start`, `POST /coach/respond`, `POST /coach/end`

All UI mock bloat (resume upload, mock questions, pre-seeded historical sessions) must be removed. The interview room must use standard job/role configuration fields, the coach room must use the 3 backend modes, and all scores must be normalized using `score <= 10 ? Math.round(score * 10) : score`.

---

## 5. Verification Method

1. **Type Safety & Build Verification**:
   - `cd c:\Project\VoxPrep\frontend && npx tsc --noEmit` -> Must exit with code 0 and 0 errors.
   - `cd c:\Project\VoxPrep\frontend && npm run lint` -> Must exit with code 0 and 0 warnings.
   - `cd c:\Project\VoxPrep\frontend && npm run build` -> Clean production build.
2. **Schema & Contract Alignment**:
   - Inspect `frontend/lib/api.ts` to ensure exact type alignment with `backend/app/routers/` and `backend/app/models/report.py`.
   - Inspect `frontend/store/useStore.ts` to ensure zero mock data arrays or fake historical sessions.
3. **Score Normalization Unit Check**:
   - Test `normalizeScore(8.8)` -> `88`
   - Test `normalizeScore(9.2)` -> `92`
   - Test `normalizeScore(10.0)` -> `100`
   - Test `normalizeScore(85)` -> `85`
4. **Invalidation Conditions**:
   - If backend route definitions in `backend/app/routers/` or schemas in `backend/schema.sql` change, these contracts must be revised.
