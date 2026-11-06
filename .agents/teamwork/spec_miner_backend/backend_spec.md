# VOXPREP Authoritative Backend API & Contract Specification

This document is the absolute single source of truth for the VOXPREP FastAPI backend, database schemas, and integration contracts. It was mined directly from `backend/app/main.py`, `backend/app/routers/`, `backend/app/models/`, `backend/app/agents/`, `backend/app/db/`, `backend/app/services/`, `backend/schema.sql`, and `backend/tests/`.

---

## 1. Executive Summary & Architecture Overview

VOXPREP operates as a dual-agent voice AI platform:
- **Agent 1 (AI Interviewer)**: Conducts structured Technical and HR mock interviews (up to 5 questions, at most 1 follow-up per question), scoring candidate answers across 4 rubric dimensions (1.0–10.0 scale) and synthesizing an `InterviewReport`.
- **Agent 2 (AI Communication Coach)**: Conducts interactive voice coaching across 3 distinct pedagogical modes (`conversation`, `answer_training`, `english_improvement`), delivering supportive feedback, max 1–2 structured linguistic corrections (`{ original, improved, reason }`), and adaptive profile learning.
- **Voice Pipeline**: Full STT (NVIDIA Parakeet ASR) -> LLM (NVIDIA Nemotron 70B) -> TTS (NVIDIA Magpie TTS) loop with robust fallback to text + Web Speech API if TTS is unavailable.
- **Data Persistence**: PostgreSQL / Supabase with 3 core tables: `users`, `interview_sessions`, and `coach_sessions`.

---

## 2. Global Error Handling & Response Contracts

The backend enforces strict global exception middleware (`GlobalExceptionMiddleware`, `http_exception_handler`, `validation_exception_handler`, and `generic_exception_handler`) in `backend/app/main.py`.

### 2.1 Standard Error Envelope
All error responses conform to the uniform envelope:
```json
{
  "detail": "Descriptive error message string OR validation error list",
  "error_type": "http_error" | "validation_error" | "internal_server_error",
  "status_code": 400 | 401 | 404 | 422 | 500
}
```

- **HTTP 400 (`Bad Request`)**: `error_type: "http_error"`, `detail: string` (e.g. invalid mode, uncompleted session, invalid email format, empty text).
- **HTTP 401 (`Unauthorized`)**: `error_type: "http_error"`, `detail: "Invalid email or password"`.
- **HTTP 404 (`Not Found`)**: `error_type: "http_error"`, `detail: "Interview session not found"` or `"Coach session not found"` or `"User '{user_id}' not found"`.
- **HTTP 422 (`Unprocessable Entity`)**: `error_type: "validation_error"`, `detail: list` containing Pydantic field validation failures (`loc`, `msg`, `type`).
- **HTTP 500 (`Internal Server Error`)**: `error_type: "internal_server_error"`, `detail: "Internal server error occurred."` (Stack traces are sanitized; CORS headers preserved).

### 2.2 CORS Policy
Configured in `backend/app/main.py`:
- `allow_credentials: True`
- `allow_methods: ["*"]`
- `allow_headers: ["*"]`
- Origin: In development with wildcard `*`, reflects requesting `Origin` dynamically with `Vary: Origin` to satisfy W3C fetch specification with credentials. In production, accepts comma-separated origins from `ALLOWED_ORIGINS` or `CORS_ORIGINS`.

---

## 3. Database Schema Contract (`schema.sql`)

### 3.1 `users` Table
```sql
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    communication_profile JSONB NOT NULL DEFAULT '{
        "skill_level": "intermediate",
        "weak_areas": [],
        "strong_areas": [],
        "sessions_count": 0
    }'::jsonb,
    skill_level TEXT DEFAULT 'intermediate',
    weak_areas JSONB DEFAULT '[]'::jsonb,
    strong_areas JSONB DEFAULT '[]'::jsonb,
    CONSTRAINT chk_users_skill_level CHECK (
        communication_profile IS NULL OR
        communication_profile->>'skill_level' IS NULL OR
        communication_profile->>'skill_level' IN ('beginner', 'intermediate', 'advanced')
    )
);
```

### 3.2 `interview_sessions` Table
```sql
CREATE TABLE IF NOT EXISTS interview_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    candidate_name TEXT NOT NULL,
    role_applied TEXT NOT NULL,
    role TEXT,
    experience_level TEXT NOT NULL,
    interview_type TEXT NOT NULL CHECK (interview_type IN ('hr', 'technical')),
    status TEXT DEFAULT 'in_progress',
    is_complete BOOLEAN NOT NULL DEFAULT FALSE,
    question_count INT DEFAULT 0,
    current_question_index INT NOT NULL DEFAULT 0 CHECK (current_question_index >= 0),
    follow_up_count INT NOT NULL DEFAULT 0 CHECK (follow_up_count >= 0),
    questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    answers JSONB NOT NULL DEFAULT '[]'::jsonb,
    scores JSONB NOT NULL DEFAULT '{}'::jsonb,
    history JSONB DEFAULT '[]'::jsonb,
    report JSONB DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
    completed_at TIMESTAMPTZ DEFAULT NULL
);
```

### 3.3 `coach_sessions` Table
```sql
CREATE TABLE IF NOT EXISTS coach_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    mode TEXT NOT NULL CHECK (mode IN ('conversation', 'answer_training', 'english_improvement')),
    status TEXT DEFAULT 'in_progress',
    is_complete BOOLEAN NOT NULL DEFAULT FALSE,
    exchanges JSONB NOT NULL DEFAULT '[]'::jsonb,
    history JSONB DEFAULT '[]'::jsonb,
    corrections JSONB DEFAULT '[]'::jsonb,
    summary JSONB DEFAULT NULL,
    started_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
    completed_at TIMESTAMPTZ DEFAULT NULL
);
```

---

## 4. Authoritative Endpoint Specifications

### Endpoint 1: `GET /health`
- **Method & Route**: `GET /health`
- **Tags**: `Health`
- **Description**: Lightweight service liveness check.
- **Request Parameters / Body**: None.
- **Response Status**: `200 OK`
- **Response Schema**:
  ```json
  {
    "status": "ok"
  }
  ```

---

### Endpoint 2: `GET /`
- **Method & Route**: `GET /`
- **Tags**: `Root`
- **Description**: Service root metadata and documentation links.
- **Request Parameters / Body**: None.
- **Response Status**: `200 OK`
- **Response Schema**:
  ```json
  {
    "title": "VOXPREP Backend API",
    "version": "0.1.0",
    "status": "online",
    "docs_url": "/docs",
    "health_check": "/health"
  }
  ```

---

### Endpoint 3: `POST /auth/register`
- **Method & Route**: `POST /auth/register`
- **Tags**: `Authentication`
- **Description**: Registers a new user account with Supabase Auth and seeds a record in `users` with initial communication profile.
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
  ```typescript
  interface RegisterRequest {
    email: string;      // Required, non-empty, must contain '@'
    password: string;   // Required, min_length: 6
    name?: string;      // Optional, default: "Candidate"
  }
  ```
- **Response Status**: `201 Created`
- **Response Body**:
  ```typescript
  interface AuthResponse {
    user: {
      id: string;       // User UUID
      email: string;
      name: string;
    };
    access_token: string;
  }
  ```
- **Error Status Codes**:
  - `400 Bad Request`: `{"detail": "Invalid email format"}` or `{"detail": "User already registered with this email"}`
  - `422 Unprocessable Entity`: Missing fields or password shorter than 6 characters.

---

### Endpoint 4: `POST /auth/login`
- **Method & Route**: `POST /auth/login`
- **Tags**: `Authentication`
- **Description**: Authenticates user credentials against Supabase Auth.
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
  ```typescript
  interface LoginRequest {
    email: string;      // Required
    password: string;   // Required
  }
  ```
- **Response Status**: `200 OK`
- **Response Body**:
  ```typescript
  interface AuthResponse {
    user: {
      id: string;
      email: string;
      name: string;
    };
    access_token: string;
  }
  ```
- **Error Status Codes**:
  - `401 Unauthorized`: `{"detail": "Invalid email or password"}`
  - `422 Unprocessable Entity`: Missing email or password.

---

### Endpoint 5: `POST /voice/process`
- **Method & Route**: `POST /voice/process`
- **Tags**: `Voice Pipeline`
- **Description**: Complete voice processing cycle: STT transcription -> LLM dialog response generation -> TTS audio synthesis.
- **Request Headers**: `Content-Type: multipart/form-data`
- **Form Data Parameters**:
  - `file`: `UploadFile` (Required binary audio, e.g. WAV blob recorded from microphone)
  - `agent_type`: `string` (Optional, default: `"interview"`. Options: `"interview"` | `"coach"`)
  - `session_id`: `string` (Optional active session UUID)
  - `conversation_history`: `string` (Optional context)
- **Response Status**: `200 OK`
- **Response Body**:
  ```typescript
  interface VoiceProcessResponse {
    transcript: string;           // Transcribed user speech
    spoken_response: string;      // Agent verbal response text
    audio_base64: string | null;  // Base64 encoded WAV audio bytes, or null if TTS fallback
    session_id: string | null;
  }
  ```
- **Guardrails & Fallback Behavior**:
  - 0-byte or corrupted audio: Returns HTTP 200 with `transcript: ""`, `spoken_response: "Could not understand. Please try again."`, and `audio_base64: null`.
  - STT failure: Returns HTTP 200 with fallback retry message and `audio_base64: null`.
  - TTS failure: Sets `audio_base64: null`; frontend safely plays synthesized voice via Web Speech API (`window.speechSynthesis`).

---

### Endpoint 6: `POST /interview/start`
- **Method & Route**: `POST /interview/start`
- **Tags**: `Interviewer Agent`
- **Description**: Initializes a structured mock interview session (HR or Technical), instantiates persona, selects opening question, and persists session to database.
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
  ```typescript
  interface InterviewStartRequest {
    candidate_name: string;             // Required, min_length: 1
    role: string;                       // Required, min_length: 1 (Target job title)
    experience_level: string;           // Required, min_length: 1 (e.g. "Junior", "Mid-level", "Senior")
    interview_type: "hr" | "technical"; // Required, track selection
    user_id?: string | null;            // Optional Supabase user UUID (null for guest access)
  }
  ```
- **Response Status**: `200 OK`
- **Response Body**:
  ```typescript
  interface InterviewStartResponse {
    session_id: string;        // UUID of the created interview session
    opening_message: string;   // Warm verbal greeting and first core interview question
  }
  ```
- **Guest Access**: `user_id` is strictly optional (`Optional[str] = None`). Guest users start interviews without authentication; `user_id` is stored as `null`.
- **Error Status Codes**:
  - `422 Unprocessable Entity`: Missing fields or `interview_type` not in `["hr", "technical"]`.

---

### Endpoint 7: `POST /interview/respond`
- **Method & Route**: `POST /interview/respond`
- **Tags**: `Interviewer Agent`
- **Description**: Processes candidate's verbal/text answer, scores answer against 4 rubric dimensions (1.0–10.0), and determines whether to ask 1 follow-up or move to next question.
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
  ```typescript
  interface InterviewRespondRequest {
    session_id: string;   // Required, UUID of active interview session
    answer_text: string;  // Required, candidate's spoken or text answer
  }
  ```
- **Response Status**: `200 OK`
- **Response Body**:
  ```typescript
  interface InterviewRespondResponse {
    spoken_response: string;              // Interviewer's next question or concluding message
    is_complete: boolean;                 // True if interview session has concluded (5 questions reached)
    follow_up_or_next: "follow_up" | "next"; // Progression state
    question_index: number;               // 0-indexed current question number (0 to 5)
    current_question_index: number;       // Alias for backward compatibility
    total_questions: number;              // Total core questions (5)
  }
  ```
- **Core Progression Guardrails**:
  - Maximum 1 follow-up per question (`follow_up_count` cannot exceed 1).
  - Maximum 5 core questions per interview (`MAX_QUESTIONS = 5`).
  - 1-word answer: prompts for elaboration once (`"Could you please elaborate a bit more on that?"`).
  - Evasive / "I don't know": acknowledged politely (`"Understood, let's move forward."`) and advances to next question.
  - Calling `/respond` on completed interview: returns `is_complete: true` idempotently without error.
- **Error Status Codes**:
  - `404 Not Found`: `{"detail": "Interview session not found"}`
  - `422 Unprocessable Entity`: Missing `session_id` or `answer_text`.

---

### Endpoint 8: `POST /interview/end`
- **Method & Route**: `POST /interview/end`
- **Tags**: `Interviewer Agent`
- **Description**: Concludes an interview session prematurely or naturally, triggers full report generation, and finalizes database record in `interview_sessions`.
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
  ```typescript
  interface InterviewEndRequest {
    session_id: string;  // Required, session UUID
  }
  ```
- **Response Status**: `200 OK`
- **Response Body**:
  ```typescript
  interface InterviewEndResponse {
    session_id: string;
    status: "completed";
    message: string;
    report: InterviewReport; // Fully generated evaluation report
  }
  ```
- **Error Status Codes**:
  - `404 Not Found`: `{"detail": "Interview session not found"}`
  - `422 Unprocessable Entity`: Missing `session_id`.

---

### Endpoint 9: `GET /interview/report/{session_id}`
- **Method & Route**: `GET /interview/report/{session_id}`
- **Tags**: `Interviewer Agent`
- **Description**: Retrieves the comprehensive evaluation report for a completed interview.
- **Path Parameter**: `session_id: string` (UUID)
- **Response Status**: `200 OK`
- **Response Body**:
  ```typescript
  interface DimensionScores {
    relevance: number; // Float 1.0 to 10.0
    clarity: number;   // Float 1.0 to 10.0
    depth: number;     // Float 1.0 to 10.0
    examples: number;  // Float 1.0 to 10.0
  }

  interface QuestionBreakdownItem {
    question: string;
    answer_summary: string;
    scores: DimensionScores;
    feedback: string;
  }

  interface InterviewReport {
    overall_score: number;                     // Float 1.0 to 10.0 (composite average)
    dimension_scores: DimensionScores;         // Averages across 4 dimensions (1.0-10.0)
    strengths: string[];                       // 1 to 5 observed strengths
    areas_for_improvement: string[];           // 1 to 5 constructive targets
    weaknesses: string[];                      // Alias mirroring areas_for_improvement
    question_breakdown: QuestionBreakdownItem[];// Per-question scores and feedback
    action_items: string[];                    // Concrete next steps
    improvement_tips: string[];                // Alias mirroring action_items
    coach_recommendation: string;              // e.g. "Interview Answer Training"
    summary: string;                           // Executive evaluation summary
  }
  ```
- **Error Status Codes**:
  - `400 Bad Request`: `{"detail": "Interview session is not yet completed. Complete the interview before retrieving the report."}` (Returned if session is in progress)
  - `404 Not Found`: `{"detail": "Interview session not found"}`

---

### Endpoint 10: `POST /coach/start`
- **Method & Route**: `POST /coach/start`
- **Tags**: `coach`
- **Description**: Initializes an AI Communication Coach session for a user in one of three modes, loading or auto-provisioning the communication profile.
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
  ```typescript
  interface CoachStartRequest {
    user_id: string; // Required, non-empty UUID or string (guest or registered)
    mode: "conversation" | "answer_training" | "english_improvement"; // Required
  }
  ```
- **Response Status**: `200 OK`
- **Response Body**:
  ```typescript
  interface CoachStartResponse {
    session_id: string;       // Unique coach session UUID
    opening_message: string;  // Warm, supportive mode-specific opening greeting
    mode: "conversation" | "answer_training" | "english_improvement";
  }
  ```
- **Guest Access Handling**: `user_id` is required as a string. However, if an unauthenticated / guest user starts a coaching session, the frontend supplies a client-generated UUID or guest ID. When `get_user_profile(user_id)` encounters an unseeded ID, it **automatically provisions and persists a baseline profile** (`Alex Candidate`, `intermediate`, `weak_areas: []`, `strong_areas: []`, `sessions_count: 0`), allowing guest coaching to function flawlessly.
- **Error Status Codes**:
  - `400 Bad Request`: `{"detail": "user_id must not be empty"}`
  - `400 Bad Request`: `{"detail": "Invalid coach mode '{mode}'. Valid modes: answer_training, conversation, english_improvement"}`
  - `422 Unprocessable Entity`: Missing `user_id` or `mode`.

---

### Endpoint 11: `POST /coach/respond`
- **Method & Route**: `POST /coach/respond`
- **Tags**: `coach`
- **Description**: Processes user speech in the coach session, returns supportive feedback, at most 1–2 constructive linguistic corrections, and the next practice challenge.
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
  ```typescript
  interface CoachRespondRequest {
    session_id: string; // Required active session UUID
    user_text: string;  // Required non-empty response text
  }
  ```
- **Response Status**: `200 OK`
- **Response Body**:
  ```typescript
  interface CoachCorrection {
    original: string; // Phrase that could be improved
    improved: string; // Better alternative phrase or suggestion
    reason: string;   // Simple pedagogical explanation
  }

  interface CoachRespondResponse {
    coach_message: string;              // Supportive, encouraging conversational response
    correction: CoachCorrection | null; // Constructive correction or null if utterance was clear
    next_prompt: string;                // Next exercise question or prompt
  }
  ```
- **Guardrails & Constraints**:
  - Max 1–2 corrections per exchange: Coach never overwhelms candidate with laundry lists of errors.
  - Fluent utterance: `correction` is `null`.
  - Terse answer (1 word): Prompt gently asks candidate to expand without negative penalization.
  - "I don't know" / skip: Coach reassures user and switches to an easier conversational topic.
- **Error Status Codes**:
  - `400 Bad Request`: `{"detail": "session_id must not be empty"}`
  - `400 Bad Request`: `{"detail": "user_text cannot be empty"}`
  - `400 Bad Request`: `{"detail": "Coach session is already completed."}`
  - `404 Not Found`: `{"detail": "Coach session not found"}`
  - `422 Unprocessable Entity`: Missing required fields.

---

### Endpoint 12: `POST /coach/end`
- **Method & Route**: `POST /coach/end`
- **Tags**: `coach`
- **Description**: Concludes coach session, compiles summary, runs profile learning to update user communication profile in Supabase, and finalizes session state.
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
  ```typescript
  interface CoachEndRequest {
    session_id: string; // Required session UUID
  }
  ```
- **Response Status**: `200 OK`
- **Response Body**:
  ```typescript
  interface CoachSessionSummary {
    exchanges_count: number;     // Number of practice turns
    corrections_count: number;   // Number of corrections delivered
    mode: string;
    key_learnings: string[];     // Bullet points of practiced techniques
    encouragement: string;       // Positive concluding encouragement
  }

  interface UserCommunicationProfile {
    skill_level: "beginner" | "intermediate" | "advanced";
    weak_areas: string[];        // Up to 5 tags
    strong_areas: string[];      // Up to 5 tags
    sessions_count: number;      // Incremented session counter
    last_mode?: string;
    last_session_id?: string;
    last_updated?: string;
  }

  interface CoachEndResponse {
    session_id: string;
    status: "completed";
    summary: CoachSessionSummary;
    profile_updated: UserCommunicationProfile;
    updated_profile: UserCommunicationProfile; // Backward-compatible alias
  }
  ```
- **Idempotency**: Repeated calls to `POST /coach/end` return HTTP 200 with the already finalized summary and profile.
- **Error Status Codes**:
  - `400 Bad Request`: `{"detail": "session_id must not be empty"}`
  - `404 Not Found`: `{"detail": "Coach session not found"}`
  - `422 Unprocessable Entity`: Missing `session_id`.

---

## 5. Scoring Metrics, Scales & Taxonomy

### 5.1 Interview Scoring Scale (1.0 – 10.0)
- **Backend Model**: `InterviewReport` uses float values with minimum `1.0` and maximum `10.0` across:
  - `overall_score`
  - `dimension_scores.relevance`
  - `dimension_scores.clarity`
  - `dimension_scores.depth`
  - `dimension_scores.examples`
  - `question_breakdown[].scores.*`
- **UI Normalization Formula**: Per R4 and Acceptance Criteria, the frontend normalizes scores for percentage progress display:
  ```typescript
  export function normalizeScore(score: number): number {
    if (score <= 10) {
      return Math.round(score * 10);
    }
    return Math.round(score);
  }
  ```

### 5.2 Coach Communication Profile Learning & Taxonomy
The coach maps linguistic corrections into 7 canonical communication tags:
1. `filler words`: e.g. "um", "uh", "like", "you know" -> deliberate pauses
2. `STAR structure`: Situation, Task, Action, Result frameworks
3. `conciseness`: brevity, eliminating rambling
4. `grammar & syntax`: past tense agreement, irregular verbs, uncountable nouns
5. `professional vocabulary`: formal phrasing, idioms, tone
6. `clarity`: eliminating ambiguity and vagueness
7. `concrete examples`: quantifiable data points, metrics, benchmarks

### 5.3 Adaptive Skill Level Transitions
- `beginner` -> `intermediate`: when correction rate <= 34% over >= 2 exchanges.
- `intermediate` -> `advanced`: when correction rate is 0.0% over >= 3 exchanges and sessions_count >= 1.
- `intermediate` -> `beginner`: when correction rate >= 75% over >= 3 exchanges.
- `advanced` -> `intermediate`: when correction rate >= 50% over >= 3 exchanges.

### 5.4 Weak Area Graduation
When a user completes a session with 0 corrections across >= 2 exchanges:
- In `conversation`: `conversational fluency` and `natural phrasing` graduate from `weak_areas` to `strong_areas`.
- In `answer_training`: `STAR structure`, `answer structure`, and `conciseness` graduate to `strong_areas`.
- In `english_improvement`: `grammar & syntax`, `filler words`, and `professional vocabulary` graduate to `strong_areas`.

---

## 6. Comprehensive Discovery & Feature Matrix

### Features Discovered
| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Health | `GET /health` | Service liveness probe | None | `{"status": "ok"}` | None (always 200) | `main.py`, `test_health.py` |
| 2 | Root | `GET /` | Root service metadata | None | `{"title", "version", "status", "docs_url", "health_check"}` | None (always 200) | `main.py`, `test_health.py` |
| 3 | Auth | `POST /auth/register` | Register new user account | `RegisterRequest: { email, password, name? }` | `AuthResponse: { user, access_token }` | 400 Bad Request (duplicate or bad email), 422 (validation) | `routers/auth.py`, `test_auth.py` |
| 4 | Auth | `POST /auth/login` | Authenticate existing user | `LoginRequest: { email, password }` | `AuthResponse: { user, access_token }` | 401 Unauthorized (bad credentials), 422 (missing fields) | `routers/auth.py`, `test_auth.py` |
| 5 | Voice | `POST /voice/process` | End-to-end voice loop: STT -> LLM -> TTS | Multipart form: `file: UploadFile`, `agent_type?`, `session_id?`, `conversation_history?` | `VoiceProcessResponse: { transcript, spoken_response, audio_base64, session_id }` | Never 500s; returns friendly prompt and null audio on corrupt audio or STT/TTS drop | `routers/voice.py`, `test_voice.py` |
| 6 | Interview | `POST /interview/start` | Initialize mock interview | `InterviewStartRequest: { candidate_name, role, experience_level, interview_type, user_id? }` | `InterviewStartResponse: { session_id, opening_message }` | 422 Unprocessable Entity (missing fields or invalid interview_type) | `routers/interview.py`, `test_interview.py` |
| 7 | Interview | `POST /interview/respond` | Submit answer & evaluate rubric | `InterviewRespondRequest: { session_id, answer_text }` | `InterviewRespondResponse: { spoken_response, is_complete, follow_up_or_next, question_index, current_question_index, total_questions }` | 404 Not Found (bad session_id), 422 (missing fields) | `routers/interview.py`, `test_interview.py` |
| 8 | Interview | `POST /interview/end` | Terminate interview & generate report | `InterviewEndRequest: { session_id }` | `InterviewEndResponse: { session_id, status, message, report }` | 404 Not Found, 422 | `routers/interview.py`, `test_interview.py` |
| 9 | Interview | `GET /interview/report/{session_id}` | Retrieve generated interview report | Path: `session_id: str` | `InterviewReport: { overall_score, dimension_scores, strengths, areas_for_improvement, weaknesses, question_breakdown, action_items, improvement_tips, coach_recommendation, summary }` | 400 Bad Request (if interview still in progress), 404 Not Found | `routers/interview.py`, `models/report.py` |
| 10 | Coach | `POST /coach/start` | Start communication coach session | `CoachStartRequest: { user_id, mode }` | `CoachStartResponse: { session_id, opening_message, mode }` | 400 Bad Request (empty user_id or invalid mode), 422 | `routers/coach.py`, `test_coach.py` |
| 11 | Coach | `POST /coach/respond` | Submit user speech & get correction | `CoachRespondRequest: { session_id, user_text }` | `CoachRespondResponse: { coach_message, correction: { original, improved, reason } or null, next_prompt }` | 400 Bad Request (empty text or already completed), 404 Not Found | `routers/coach.py`, `test_coach.py` |
| 12 | Coach | `POST /coach/end` | End coach session & update profile | `CoachEndRequest: { session_id }` | `CoachEndResponse: { session_id, status, summary, profile_updated, updated_profile }` | 400 Bad Request (empty session_id), 404 Not Found | `routers/coach.py`, `test_coach.py` |

---

## 7. Edge Cases & Boundary Conditions

### Edge Cases
| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | `POST /voice/process` | 0-byte or < 12 byte audio payload | Returns HTTP 200 with `transcript=""`, `spoken_response="Could not understand. Please try again."`, and `audio_base64=null`. |
| 2 | `POST /voice/process` | Corrupted non-audio bytes | Returns HTTP 200 with fallback retry prompt without raising HTTP 500. |
| 3 | `POST /voice/process` | TTS synthesis returns None | Returns HTTP 200 with `spoken_response` populated and `audio_base64=null`, enabling browser Web Speech API fallback. |
| 4 | `POST /interview/start` | Unsupported interview type (e.g. "debate") | Returns HTTP 422 with validation error explaining track must be 'hr' or 'technical'. |
| 5 | `POST /interview/start` | Unauthenticated guest user (`user_id=null` or omitted) | Succeeds with HTTP 200, generating `session_id` and saving `user_id=null` in database. |
| 6 | `POST /interview/respond` | Candidate gives 1-word answer (e.g. "React.") | Prompts for elaboration: `"Could you please elaborate a bit more on that?"` with `follow_up_or_next="follow_up"`. |
| 7 | `POST /interview/respond` | Candidate gives evasive answer / "I don't know" | Acknowledges with `"Understood, let's move forward."` and skips follow-up, directly advancing to next question. |
| 8 | `POST /interview/respond` | Maximum follow-ups per question reached | When `follow_up_count == 1`, forces next response to advance to next question (`follow_up_or_next="next"`), resetting `follow_up_count=0`. |
| 9 | `POST /interview/respond` | Reaching 5th question boundary | Sets `is_complete=true`, returns professional closing message, and records completion timestamp. |
| 10 | `POST /interview/respond` | Responding after interview already completed | Returns `is_complete=true` with completion message idempotently without mutating question indices. |
| 11 | `GET /interview/report/{session_id}` | Fetching report for session that is still in progress | Returns HTTP 400 Bad Request: `"Interview session is not yet completed. Complete the interview before retrieving the report."`. |
| 12 | `POST /coach/start` | New or unauthenticated guest `user_id` | Backend automatically provisions and persists default baseline profile (`Alex Candidate`, `intermediate`, `weak_areas: []`, `strong_areas: []`, `sessions_count: 0`), returning HTTP 200. |
| 13 | `POST /coach/start` | Invalid mode string (e.g. "hostile_cross_examination") | Returns HTTP 400 Bad Request with allowed modes listed: `conversation`, `answer_training`, `english_improvement`. |
| 14 | `POST /coach/respond` | Utterance contains multiple errors | Restricts corrections to at most 1–2 items (`MAX_CORRECTIONS_PER_EXCHANGE = 2`) to maintain supportive pedagogical framing. |
| 15 | `POST /coach/respond` | Responding to already completed session | Returns HTTP 400 Bad Request: `"Coach session is already completed."`. |
| 16 | `POST /coach/end` | Repeated calls on same session | Idempotently returns HTTP 200 with previously compiled summary and updated profile. |
| 17 | Global Error Handling | Unhandled internal exception in any route | Returns uniform HTTP 500 JSON (`{"detail": "Internal server error occurred.", "error_type": "internal_server_error", "status_code": 500}`) and reflects CORS origin header. |
| 18 | Global Error Handling | Requesting non-existent route | Returns uniform HTTP 404 JSON (`{"detail": "Not Found", "error_type": "http_error", "status_code": 404}`). |
| 19 | Global Error Handling | Pydantic validation failure (missing body or type mismatch) | Returns uniform HTTP 422 JSON (`{"detail": [...], "error_type": "validation_error", "status_code": 422}`). |
