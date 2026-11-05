# VOXPREP Backend API Contract Reference (Frontend Integration Guide)
**Target Audience**: Member B (Frontend Lead / Fullstack Integration)  
**Base URL (Local)**: `http://localhost:8000`  
**Base URL (Production - Railway)**: `https://<your-railway-service>.up.railway.app`  
**API Specification Version**: 0.1.0  
**Framework**: FastAPI (OpenAPI 3.1 compatible, interactive docs at `/docs` or `/redoc`)

---

## 1. General Architecture & Client Guidelines

### 1.1 Content Types & Headers
- **JSON Endpoints**: All authentication, interview, and coach endpoints expect `Content-Type: application/json` and return `application/json`.
- **Voice Pipeline Endpoint (`/voice/process`)**: Expects `multipart/form-data` containing the recorded audio binary (`file`) and form data fields.
- **Authentication**: When authenticated, include the Bearer token in the `Authorization` header:
  ```http
  Authorization: Bearer <access_token>
  ```
  *(Note: For MVP development, session endpoints use `session_id` and optional `user_id` for state resolution; Authorization header is supported for user-scoped operations).*

### 1.2 Global Error Response Schema
All endpoints return structured JSON errors with standard HTTP status codes. The client can always inspect `response.data.detail`:

```json
{
  "detail": "Descriptive human-readable error message or validation breakdown",
  "error_type": "http_error",
  "status_code": 404
}
```

#### Status Code Meaning Matrix
| Status Code | Reason | Client Handling |
|---|---|---|
| **200 OK** | Request succeeded | Render response data |
| **201 Created** | Resource created (e.g., `/auth/register`) | Store auth token, redirect to dashboard |
| **400 Bad Request** | Business rule violation (e.g., duplicate email, empty text, invalid mode) | Display `detail` message in toast/alert |
| **401 Unauthorized** | Invalid credentials | Prompt user to re-enter email/password |
| **404 Not Found** | Invalid `session_id` or non-existent `user_id` | Redirect to setup page / show 404 state |
| **422 Unprocessable Entity** | Missing required JSON fields or type mismatch | Inspect field errors in form validation |
| **500 Internal Server Error** | Unexpected upstream failure (e.g. AI provider outage) | Show friendly error: "AI service temporarily unavailable. Please retry." |

---

## 2. Health & Service Metadata Endpoints

### 2.1 Health Heartbeat
- **Endpoint**: `GET /health`
- **Purpose**: Uptime check for Railway deployment, load balancers, and frontend service readiness.
- **Headers**: None required.
- **Request Body**: None.
- **Response (200 OK)**:
```json
{
  "status": "ok"
}
```
- **cURL Example**:
```bash
curl -X GET http://localhost:8000/health
```

---

### 2.2 Root Service Information
- **Endpoint**: `GET /`
- **Purpose**: Returns API title, version, documentation URLs, and service status.
- **Response (200 OK)**:
```json
{
  "title": "VOXPREP Backend API",
  "version": "0.1.0",
  "status": "online",
  "docs_url": "/docs",
  "health_check": "/health"
}
```
- **cURL Example**:
```bash
curl -X GET http://localhost:8000/
```

---

## 3. Authentication Endpoints

### 3.1 User Registration
- **Endpoint**: `POST /auth/register`
- **Purpose**: Creates a new user in Supabase Auth, provisions initial record in `users` table, and initializes the default `communication_profile`.
- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "email": "alex.candidate@example.com",
  "password": "StrongPassword123!",
  "name": "Alex Candidate"
}
```
- **Field Constraints**:
  * `email` (string, required): Valid email containing `@`.
  * `password` (string, required): Minimum length 6 characters.
  * `name` (string, optional): Full name (defaults to `"Candidate"`).
- **Response (201 Created)**:
```json
{
  "user": {
    "id": "e2a3c77d-b5df-4279-bfbe-d45091f04db5",
    "email": "alex.candidate@example.com",
    "name": "Alex Candidate"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```
- **Error Responses**:
  * `400 Bad Request`: `{"detail": "User already registered with this email"}`
  * `422 Unprocessable Entity`: `{"detail": [{"loc": ["body", "password"], "msg": "String should have at least 6 characters"}]}`
- **cURL Example**:
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alex.candidate@example.com",
    "password": "StrongPassword123!",
    "name": "Alex Candidate"
  }'
```

---

### 3.2 User Login
- **Endpoint**: `POST /auth/login`
- **Purpose**: Authenticates user credentials via Supabase Auth and returns user identity with access token.
- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "email": "alex.candidate@example.com",
  "password": "StrongPassword123!"
}
```
- **Response (200 OK)**:
```json
{
  "user": {
    "id": "e2a3c77d-b5df-4279-bfbe-d45091f04db5",
    "email": "alex.candidate@example.com",
    "name": "Alex Candidate"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```
- **Error Responses**:
  * `401 Unauthorized`: `{"detail": "Invalid email or password"}`
- **cURL Example**:
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alex.candidate@example.com",
    "password": "StrongPassword123!"
  }'
```

---

## 4. Voice Pipeline Endpoint

### 4.1 End-to-End Voice Loop (STT -> LLM -> TTS)
- **Endpoint**: `POST /voice/process`
- **Purpose**: Accepts binary microphone audio from frontend `VoiceRecorder`, transcribes it via NVIDIA Parakeet ASR, queries NVIDIA Nemotron LLM, synthesizes voice response via NVIDIA Magpie TTS, and returns base64 audio.
- **Headers**: `Content-Type: multipart/form-data`
- **Form Data Fields**:
  * `file` (binary, required): WAV audio blob recorded by client browser.
  * `agent_type` (string, optional): `"interview"` (default) or `"coach"`.
  * `session_id` (string, optional): Active interview or coach session UUID.
  * `conversation_history` (string, optional): Context string or serialized exchange history.
- **Response (200 OK)**:
```json
{
  "transcript": "In my previous project, we built a real-time event pipeline using Kafka and FastAPI.",
  "spoken_response": "That sounds like a robust setup. How did you ensure idempotency and handle message consumer backpressure?",
  "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQ...",
  "session_id": "f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9"
}
```
- **Frontend Fallback Handling**:
  * If audio is corrupt or empty: Returns HTTP 200 with `spoken_response: "Could not understand. Please try again."`, `transcript: ""`, `audio_base64: null`.
  * If TTS synthesis fails or credits are depleted: `audio_base64` will be `null`. Frontend should fall back immediately to `window.speechSynthesis` (Web Speech API) using `spoken_response`.
- **cURL Example**:
```bash
curl -X POST http://localhost:8000/voice/process \
  -F "file=@sample_recording.wav;type=audio/wav" \
  -F "agent_type=interview" \
  -F "session_id=f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9"
```

---

## 5. Agent 1: AI Interviewer Endpoints

### 5.1 Start Interview Session
- **Endpoint**: `POST /interview/start`
- **Purpose**: Creates an interview session in Supabase, configures the interview agent persona, and returns the opening question.
- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "candidate_name": "Alex Candidate",
  "role": "Senior Backend Engineer",
  "experience_level": "Mid-Senior (4 years)",
  "interview_type": "technical",
  "user_id": "e2a3c77d-b5df-4279-bfbe-d45091f04db5"
}
```
- **Field Constraints**:
  * `candidate_name` (string, required): Non-empty candidate full name.
  * `role` (string, required): Target job title.
  * `experience_level` (string, required): e.g. `"Junior (1-2 yrs)"`, `"Mid-Level (3-5 yrs)"`, `"Senior (5+ yrs)"`.
  * `interview_type` (string, required): Must be strictly `"hr"` or `"technical"` (case-insensitive).
  * `user_id` (string, optional): Authenticated Supabase user UUID.
- **Response (200 OK)**:
```json
{
  "session_id": "f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9",
  "opening_message": "Hello Alex Candidate, welcome to your Senior Backend Engineer technical interview. Let's start with your background: Could you walk me through the architecture of a high-traffic backend system you designed and scaled?"
}
```
- **cURL Example**:
```bash
curl -X POST http://localhost:8000/interview/start \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_name": "Alex Candidate",
    "role": "Senior Backend Engineer",
    "experience_level": "Mid-Senior (4 years)",
    "interview_type": "technical",
    "user_id": "e2a3c77d-b5df-4279-bfbe-d45091f04db5"
  }'
```

---

### 5.2 Submit Candidate Answer
- **Endpoint**: `POST /interview/respond`
- **Purpose**: Submits candidate's answer text, evaluates against the 4-dimension rubric (Relevance, Clarity, Depth, Examples), decides whether to ask 1 follow-up or advance to next question, and persists session state.
- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "session_id": "f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9",
  "answer_text": "In my previous project, we deployed FastAPI microservices behind an Nginx reverse proxy with Redis caching. We optimized database connection pools using asyncpg and achieved sub-50ms latency under 10,000 RPM."
}
```
- **Response (200 OK)**:
```json
{
  "spoken_response": "Thank you for detailing that architecture. How did you handle cache invalidation when database writes occurred?",
  "is_complete": false,
  "follow_up_or_next": "follow_up",
  "question_index": 0,
  "current_question_index": 0,
  "total_questions": 5
}
```
- **Progression Logic**:
  * `follow_up_or_next`: `"follow_up"` (probing deeper into current question) or `"next"` (advancing to new topic).
  * Boundary Rule: At most **1 follow-up** per question. Maximum **5 core questions** per interview.
  * When `is_complete: true` is returned, the frontend should notify the user and call `POST /interview/end` or redirect to `/interview/report`.
- **Error Responses**:
  * `404 Not Found`: `{"detail": "Interview session not found"}`
- **cURL Example**:
```bash
curl -X POST http://localhost:8000/interview/respond \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9",
    "answer_text": "We used a write-through cache invalidation strategy with Redis pub/sub to invalidate cached payloads on state updates."
  }'
```

---

### 5.3 Conclude Interview & Generate Report
- **Endpoint**: `POST /interview/end`
- **Purpose**: Finalizes session, triggers comprehensive evaluation report generation via Nemotron LLM, saves report to Supabase, and returns complete report data.
- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "session_id": "f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9"
}
```
- **Response (200 OK)**:
```json
{
  "session_id": "f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9",
  "status": "completed",
  "message": "Interview session ended successfully and report generated.",
  "report": {
    "overall_score": 8.5,
    "dimension_scores": {
      "relevance": 9.0,
      "clarity": 8.5,
      "depth": 8.0,
      "examples": 8.5
    },
    "strengths": [
      "Precise technical explanations with concrete architectural examples",
      "Clear articulation of Redis caching strategies"
    ],
    "areas_for_improvement": [
      "Include quantitative failure rate metrics",
      "Discuss fault tolerance under network partition"
    ],
    "question_breakdown": [
      {
        "question": "Could you walk me through the architecture of a high-traffic backend system you designed and scaled?",
        "answer_summary": "Explained FastAPI microservices, Nginx reverse proxy, and Redis caching.",
        "scores": {
          "relevance": 9.0,
          "clarity": 8.5,
          "depth": 8.0,
          "examples": 8.5
        },
        "feedback": "Comprehensive answer demonstrating practical scaling experience."
      }
    ],
    "action_items": [
      "Practice the STAR framework for behavioral and incident response questions",
      "Elaborate on database replication lag mitigations"
    ],
    "coach_recommendation": "Interview Answer Training",
    "summary": "Overall solid performance demonstrating mid-to-senior backend engineering competencies."
  }
}
```
- **cURL Example**:
```bash
curl -X POST http://localhost:8000/interview/end \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9"
  }'
```

---

### 5.4 Retrieve Interview Performance Report
- **Endpoint**: `GET /interview/report/{session_id}`
- **Purpose**: Fetches the finalized evaluation report for display on the `/interview/report` page.
- **Path Parameter**: `session_id` (UUID string).
- **Response (200 OK)**: Full report JSON matching the schema above.
- **Error Responses**:
  * `404 Not Found`: `{"detail": "Interview session not found"}`
  * `400 Bad Request`: `{"detail": "Interview session is not yet completed. Complete the interview before retrieving the report."}`
- **cURL Example**:
```bash
curl -X GET http://localhost:8000/interview/report/f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9
```

---

## 6. Agent 2: AI Communication Coach Endpoints

### 6.1 Start Coach Session
- **Endpoint**: `POST /coach/start`
- **Purpose**: Initializes a coach session, loads the user's communication profile (skill level, weak areas, strong areas) from Supabase, seeds the coach mode, and returns a warm opening greeting.
- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "user_id": "e2a3c77d-b5df-4279-bfbe-d45091f04db5",
  "mode": "answer_training"
}
```
- **Field Constraints**:
  * `user_id` (string, required): UUID of the registered user.
  * `mode` (string, required): Must be one of:
    - `"conversation"`: Everyday casual conversation and fluency practice.
    - `"answer_training"`: Structuring concise, high-impact interview answers.
    - `"english_improvement"`: Grammar, vocabulary, and phrasing refinement.
- **Response (200 OK)**:
```json
{
  "session_id": "c1f8e2a3-9b4d-4567-89ab-cdef01234567",
  "opening_message": "Hello Alex! I'm your AI Communication Coach. In this Answer Training session, we'll practice structuring your responses with clarity and confidence. Let's start with a classic: Tell me about a time you led a challenging technical project.",
  "mode": "answer_training"
}
```
- **Error Responses**:
  * `400 Bad Request`: `{"detail": "Invalid coach mode 'behavioral'. Valid modes: answer_training, conversation, english_improvement"}`
  * `404 Not Found`: `{"detail": "User '...' not found"}`
- **cURL Example**:
```bash
curl -X POST http://localhost:8000/coach/start \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "e2a3c77d-b5df-4279-bfbe-d45091f04db5",
    "mode": "answer_training"
  }'
```

---

### 6.2 Submit User Speech to Coach
- **Endpoint**: `POST /coach/respond`
- **Purpose**: Processes candidate response, provides positive reinforcement, offers at most 1–2 constructive corrections with clearer alternatives and explanations, and presents the next prompt.
- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "session_id": "c1f8e2a3-9b4d-4567-89ab-cdef01234567",
  "user_text": "I am working as backend engineer since 4 years and I do python coding very good."
}
```
- **Response (200 OK)**:
```json
{
  "coach_message": "You clearly communicated your experience and strong background! Here is a minor phrasing polish that will sound more natural and professional.",
  "correction": {
    "original": "I am working as backend engineer since 4 years and I do python coding very good.",
    "improved": "I have been working as a backend engineer for four years, and I am highly proficient in Python development.",
    "reason": "Uses present perfect continuous ('have been working for four years') and replaces colloquial 'do coding very good' with 'proficient in Python development'."
  },
  "next_prompt": "Could you now describe a specific technical challenge you overcame while building a Python service?"
}
```
- **Coach Guardrails**:
  * `correction` can be `null` if the candidate spoke clearly with no major errors.
  * Maximum 1–2 corrections per exchange (never overwhelms or lectures the user).
  * Tone is always encouraging and constructive.
- **Error Responses**:
  * `400 Bad Request`: `{"detail": "user_text cannot be empty"}` or `{"detail": "Coach session is already completed."}`
  * `404 Not Found`: `{"detail": "Coach session not found"}`
- **cURL Example**:
```bash
curl -X POST http://localhost:8000/coach/respond \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "c1f8e2a3-9b4d-4567-89ab-cdef01234567",
    "user_text": "I am working as backend engineer since 4 years and I do python coding very good."
  }'
```

---

### 6.3 Conclude Coach Session & Update Profile
- **Endpoint**: `POST /coach/end`
- **Purpose**: Finalizes coach session, summarizes practice metrics, updates user's persistent communication profile in Supabase (`users.communication_profile`), and saves session history to `coach_sessions`.
- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "session_id": "c1f8e2a3-9b4d-4567-89ab-cdef01234567"
}
```
- **Response (200 OK)**:
```json
{
  "session_id": "c1f8e2a3-9b4d-4567-89ab-cdef01234567",
  "status": "completed",
  "summary": {
    "exchanges_count": 4,
    "corrections_count": 2,
    "encouragement": "Great job! Keep practicing regularly to build your conversational fluency."
  },
  "profile_updated": {
    "skill_level": "intermediate",
    "weak_areas": ["tense consistency"],
    "strong_areas": ["technical vocabulary", "answer structure"],
    "sessions_count": 2
  },
  "updated_profile": {
    "skill_level": "intermediate",
    "weak_areas": ["tense consistency"],
    "strong_areas": ["technical vocabulary", "answer structure"],
    "sessions_count": 2
  }
}
```
- **cURL Example**:
```bash
curl -X POST http://localhost:8000/coach/end \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "c1f8e2a3-9b4d-4567-89ab-cdef01234567"
  }'
```

---

## 7. Complete Frontend Integration Checklist (Member B)

- [ ] **Auth Token Storage**: Store `access_token` returned by `/auth/login` and `/auth/register` in localStorage/session cookie.
- [ ] **Voice Recording Format**: Client MediaRecorder should record in standard WAV (or WebM converted to WAV) before posting to `POST /voice/process`.
- [ ] **TTS Fallback**: If `audio_base64` in `POST /voice/process` is null, trigger browser Web Speech API:
  ```javascript
  if (!data.audio_base64 && window.speechSynthesis) {
    const utterance = new SpeechSynthesisUtterance(data.spoken_response);
    window.speechSynthesis.speak(utterance);
  }
  ```
- [ ] **Interview Session Boundary**: When `/interview/respond` returns `is_complete: true`, display interview completion banner and invoke `POST /interview/end`.
- [ ] **Coach Correction Card**: On `/coach/session`, if `correction` is non-null, display side-by-side comparison (`original` vs `improved`) with `reason`.
- [ ] **Error Toast Interceptor**: Capture any non-2xx status code and display `response.data.detail`.
