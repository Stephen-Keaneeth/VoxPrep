# VOXPREP Backend MVP — Authoritative Specification Mining Report

> **Target Architecture:** FastAPI Backend (Member A MVP)  
> **Integrations:** NVIDIA NIM (Nemotron 70B, Parakeet CTC 1.1B ASR, Magpie Multilingual TTS), Supabase (Auth & PostgreSQL)  
> **Specification Sources:** `ORIGINAL_REQUEST.md`, `docs/00_PROJECT_OVERVIEW.md` through `docs/08_AGENT_PROMPTS.md`, NVIDIA NIM API Catalog  
> **Integrity Mode:** Development  
> **Status:** Mining Complete & Verified

---

## 1. Executive Summary & Specification Scope

VOXPREP is a voice-first, dual-agent AI platform designed for realistic mock interviews and personalized communication coaching. Member A is solely responsible for the complete backend service built on FastAPI, wrapping NVIDIA NIM microservices via REST/OpenAI-compatible protocols, managing persistence and authentication in Supabase, and exposing clean, documented JSON/REST interfaces to Member B (Frontend Next.js).

This specification report aggregates and formalizes every technical requirement across Phases 0 through 4 into unambiguous engineering blueprints, complete with schema definitions, endpoint contracts, agent state models, prompt specifications, fallback strategies, and verification methods.

---

## 2. Phase 0: Project Setup, Environment, and Database Schema

### 2.1 Dedicated Virtual Environment (`.venv`)
- The Python virtual environment MUST be established inside `.venv` at project root or backend root (`d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.venv` or `backend/.venv`).
- Standard Python interpreter: Python 3.11+ (verified runtime: Python 3.12.10).
- All dependencies from `backend/requirements.txt` must be installed into this dedicated virtual environment without dependency conflicts.

### 2.2 Backend Directory Structure
Per `docs/02_TECH_STACK.md`, the backend code layout must match:
```
backend/
├── app/
│   ├── main.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── interview.py
│   │   ├── coach.py
│   │   └── voice.py
│   ├── agents/
│   │   ├── interviewer.py
│   │   └── coach.py
│   ├── services/
│   │   ├── llm.py
│   │   ├── stt.py
│   │   ├── tts.py
│   │   └── report.py
│   ├── models/
│   │   ├── user.py
│   │   ├── session.py
│   │   └── report.py
│   └── db/
│       └── supabase.py
├── requirements.txt
├── .env.example
├── Dockerfile
├── railway.json / Procfile
└── schema.sql (Supabase DDL script)
```

### 2.3 Package Manifest (`requirements.txt`)
Required dependencies:
```txt
fastapi>=0.110.0,<1.0.0
uvicorn[standard]>=0.28.0,<1.0.0
pydantic>=2.6.0,<3.0.0
pydantic-settings>=2.2.0,<3.0.0
openai>=1.14.0,<2.0.0
supabase>=2.3.0,<3.0.0
python-dotenv>=1.0.1
httpx>=0.27.0,<1.0.0
python-multipart>=0.0.9
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

### 2.4 Environment Configuration (`.env.example`)
Template for `backend/.env.example`:
```env
# NVIDIA NIM API Catalog (covers Nemotron LLM, Parakeet ASR, Magpie TTS)
NVIDIA_API_KEY=nvapi-your_nvidia_api_key_here

# Supabase Project Credentials
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_supabase_service_role_key
SUPABASE_ANON_KEY=your_supabase_anon_key

# Optional App Settings
ENVIRONMENT=development
PORT=8000
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### 2.5 Supabase PostgreSQL Database Schema (`schema.sql`)
The PostgreSQL schema defines three primary relational tables with JSONB flexibility for history, evaluations, profiles, and reports:

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Users Table (Profile & Communication Stats)
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    communication_profile JSONB DEFAULT '{
        "skill_level": "intermediate",
        "weak_areas": [],
        "strong_areas": [],
        "sessions_count": 0
    }'::jsonb NOT NULL
);

-- 2. Interview Sessions Table (Agent 1)
CREATE TABLE IF NOT EXISTS public.interview_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    candidate_name TEXT NOT NULL,
    interview_type TEXT NOT NULL CHECK (interview_type IN ('hr', 'technical', 'situational', 'resume')),
    role_applied TEXT NOT NULL,
    experience_level TEXT NOT NULL,
    questions JSONB DEFAULT '[]'::jsonb NOT NULL,
    answers JSONB DEFAULT '[]'::jsonb NOT NULL,
    scores JSONB DEFAULT '{}'::jsonb NOT NULL,
    report JSONB,
    current_question_index INT DEFAULT 0 NOT NULL,
    follow_up_count INT DEFAULT 0 NOT NULL,
    is_complete BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- 3. Coach Sessions Table (Agent 2)
CREATE TABLE IF NOT EXISTS public.coach_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('conversation', 'answer_training', 'english_improvement')),
    exchanges JSONB DEFAULT '[]'::jsonb NOT NULL,
    summary JSONB,
    is_complete BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_interview_sessions_user_id ON public.interview_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_coach_sessions_user_id ON public.coach_sessions(user_id);
```

### 2.6 Application Entry Point & Health Check (`main.py`)
- CORS Middleware configured for `ALLOWED_ORIGINS` (including `http://localhost:3000` for Next.js frontend).
- Standard ping endpoint:
  - `GET /health` -> HTTP 200 `{"status": "ok"}`
  - `GET /` -> HTTP 200 `{"message": "VOXPREP Backend API", "docs_url": "/docs"}`

---

## 3. Phase 1: NVIDIA AI Services, Voice Pipeline, and Authentication

### 3.1 NVIDIA Nemotron LLM Client (`services/llm.py`)
- **Model:** `nvidia/llama-3.1-nemotron-70b-instruct`
- **Base URL:** `https://integrate.api.nvidia.com/v1`
- **SDK Pattern:** OpenAI Python SDK compatible or direct `httpx.AsyncClient`.
- **Interface Contract:**
  `async def chat(messages: list[dict], system_prompt: str, temperature: float = 0.7, max_tokens: int = 1024) -> str`
- **Retry & Fallback Guardrail:**
  Execute primary API call. If a network timeout, HTTP 429 (rate limit), or 5xx occurs, wait with exponential backoff (e.g. 1.0s) and retry once. If the retry also fails, catch the exception, log detailed context, and return a friendly fallback response:
  `"I am temporarily experiencing high traffic. Could you please repeat or summarize your last thought?"`
  Never crash the application or let unhandled exceptions leak to HTTP 500.

### 3.2 NVIDIA Parakeet ASR Speech-to-Text (`services/stt.py`)
- **Model:** `nvidia/parakeet-ctc-1.1b-asr`
- **Base URL:** `https://integrate.api.nvidia.com/v1`
- **Endpoint:** `POST /v1/audio/transcriptions`
- **Payload Schema:** `multipart/form-data` with:
  - `file`: audio binary payload (Linear PCM 16kHz Mono `.wav`, or browser audio `.webm`/`.mp4`/`.ogg`)
  - `model`: `"nvidia/parakeet-ctc-1.1b-asr"`
  - `response_format`: `"json"`
- **Interface Contract:**
  `async def transcribe(audio_bytes: bytes, filename: str = "audio.wav") -> str | None`
- **Error Behavior:**
  If transcription fails, returns `None` and logs error message. Downstream callers handle `None` by prompting: `"Could not understand. Please try again."`

### 3.3 NVIDIA Magpie TTS Text-to-Speech (`services/tts.py`)
- **Model / Service:** `nvidia/magpie-tts-multilingual`
- **Base URL:** `https://integrate.api.nvidia.com/v1`
- **Endpoint:** `POST /v1/audio/synthesize`
- **Payload Schema:** `multipart/form-data` (or JSON per NIM gateway):
  - `text`: input text to speak
  - `language`: `"en-US"`
  - `voice`: `"Magpie-Multilingual.EN-US.Aria"`
  - `encoding`: `"LINEAR_PCM"`
  - `sample_rate_hz`: `44100` (or `24000`)
- **Interface Contract:**
  `async def synthesize(text: str, voice: str = "Magpie-Multilingual.EN-US.Aria") -> bytes | None`
- **Error Behavior & Fallback:**
  If Magpie TTS returns an error code or empty audio, returns `None` without crashing. The frontend receives `audio_url: null` or empty audio header, falling back to Web Speech API (`window.speechSynthesis`).

### 3.4 Voice Pipeline Router (`routers/voice.py`)
- **Endpoint:** `POST /voice/process`
- **Consumes:** `multipart/form-data`
  - `file: UploadFile` (audio recording)
  - `session_id: Optional[str]`
  - `agent_type: Optional[str]` (`"interview"` or `"coach"`)
- **Processing Flow:**
  1. Read `audio_bytes` from uploaded file.
  2. Call `stt.transcribe(audio_bytes)`. If STT fails, return `{ "transcript": "", "spoken_response": "Could not understand. Please try again.", "audio_base64": null }`.
  3. Route transcribed text to either Interviewer or Coach agent (or direct conversational LLM test).
  4. Call `tts.synthesize(spoken_response)`.
  5. Return composite response containing transcript, generated text response, and optional audio bytes (or Base64 / WAV audio stream).
- **Produces:** `application/json` (or `Response(content=audio_bytes, media_type="audio/wav")` with headers `X-Transcript` and `X-Response-Text`).

### 3.5 Supabase Client Singleton (`db/supabase.py`)
- Initializes `create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)`.
- If `SUPABASE_URL` or `SUPABASE_SERVICE_KEY` are unset in local test environments, client provides an in-memory/mock fallback dictionary to avoid startup crashes during offline testing.

### 3.6 Authentication Router (`routers/auth.py`)
- Uses Supabase Auth client to manage user credentials.
- **Endpoints:**
  - `POST /auth/register`:
    - Request Body: `{"email": "user@example.com", "password": "password123", "name": "Jane Doe"}`
    - Logic: Call Supabase Auth `sign_up`. Also insert corresponding profile row in `public.users` table with default `communication_profile`.
    - Response: `{ "user": { "id": "uuid", "email": "...", "name": "..." }, "access_token": "..." }`
  - `POST /auth/login`:
    - Request Body: `{"email": "user@example.com", "password": "password123"}`
    - Logic: Call Supabase Auth `sign_in_with_password`.
    - Response: `{ "user": { "id": "uuid", "email": "...", "name": "..." }, "access_token": "..." }`

### 3.7 Phase 1 Verification Curl Commands
```bash
# 1. Health check
curl -X GET http://localhost:8000/health

# 2. Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"candidate@test.com","password":"Password123!","name":"Alex Test"}'

# 3. Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"candidate@test.com","password":"Password123!"}'

# 4. Voice Process test (with wav file)
curl -X POST http://localhost:8000/voice/process \
  -F "file=@test_audio.wav;type=audio/wav" \
  -F "agent_type=interview"
```

---

## 4. Phase 2: Agent 1 (AI Interviewer) & Report Generation

### 4.1 `InterviewSession` Class & State Machine (`agents/interviewer.py`)
- **State Attributes:**
  - `session_id`: UUID string
  - `user_id`: Optional UUID string
  - `candidate_name`: str
  - `role`: str
  - `experience_level`: str (e.g., "Junior", "Mid-level", "Senior")
  - `interview_type`: str (`"hr"` or `"technical"`)
  - `questions`: list of question strings
  - `answers`: list of answer strings
  - `scores`: list of per-question rubric scores `[{"relevance": int, "clarity": int, "depth": int, "examples": int}]`
  - `current_question_index`: int (0 to 5)
  - `follow_up_count`: int (0 or 1 per question)
  - `is_complete`: bool (True once 5 core questions answered or candidate terminates)

### 4.2 Guardrails & Strict Session Boundaries
- **Question Limit:** Maximum 5 core questions per session.
- **Follow-up Limit:** Maximum 1 follow-up question per core question.
- **Single Question Rule:** Ask exactly ONE question at a time; wait for candidate answer before asking anything else.
- **No Answers/Hints Revealed:** Interviewer never reveals expected answers or hints before response.
- **No Repeated Questions:** Question history is tracked; duplicate questions must be rejected or regenerated.
- **No Tutor Behavior:** No coaching during the interview session; evaluations are internal.
- **Evaluation Rubric Dimensions (1–10 scale):**
  1. `Relevance`: Did the answer directly address the question?
  2. `Clarity`: Was the answer clear, coherent, and well-structured?
  3. `Depth`: Did the answer demonstrate deep understanding beyond superficial terms?
  4. `Examples`: Did the candidate provide concrete, real-world examples or STAR elements?

### 4.3 Internal Evaluation & LLM Decision Loop
After each answer, LLM evaluates and returns internal JSON:
```json
{
  "question": "Tell me about a challenging bug you fixed.",
  "answer": "I had a race condition in Redis caching...",
  "scores": {
    "relevance": 9,
    "clarity": 8,
    "depth": 8,
    "examples": 9
  },
  "follow_up": "How did you verify that the race condition was fully resolved in production?" or null,
  "next_question": "Can you explain how database indexing impacts read versus write performance?" or null
}
```

### 4.4 Report Generation Service (`services/report.py`)
When `POST /interview/end` is invoked or question 5 concludes:
- Compiles the full `session_json` (questions, candidate answers, and rubric scores).
- Calls Nemotron LLM with the authoritative Report Generation Prompt from `docs/08_AGENT_PROMPTS.md`.
- Generates JSON matching schema:
```json
{
  "overall_score": 8.1,
  "dimension_scores": {
    "relevance": 8.4,
    "clarity": 8.0,
    "depth": 7.8,
    "examples": 8.2
  },
  "strengths": [
    "Clear explanation of Redis caching mechanisms in question 2.",
    "Strong use of concrete metrics when describing throughput improvements."
  ],
  "weaknesses": [
    "Did not elaborate on trade-offs when discussing microservices architecture.",
    "Hesitation when asked about disaster recovery strategies."
  ],
  "improvement_tips": [
    "Structure situational answers using the STAR method (Situation, Task, Action, Result).",
    "Quantify business impact alongside technical details."
  ],
  "coach_recommendation": "Interview Answer Training",
  "summary": "Alex demonstrated solid technical competence and clear communication. With more structured STAR examples, their interview performance will be exceptional."
}
```

### 4.5 Interview Endpoints Contract (`routers/interview.py`)

#### `POST /interview/start`
- **Request Body:**
  ```json
  {
    "candidate_name": "Alex Johnson",
    "role": "Backend Engineer",
    "experience_level": "Mid-level",
    "interview_type": "technical",
    "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "session_id": "8b5a1928-86d7-463f-9173-196b05423851",
    "opening_message": "Hello Alex, welcome to your technical interview for the Backend Engineer position. Let's start with a warm-up: could you tell me about yourself and your primary technical stack?"
  }
  ```

#### `POST /interview/respond`
- **Request Body:**
  ```json
  {
    "session_id": "8b5a1928-86d7-463f-9173-196b05423851",
    "answer_text": "I have been working with Python and FastAPI for three years..."
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "spoken_response": "Thank you for sharing that. Could you describe a challenging distributed systems problem you recently resolved?",
    "is_complete": false,
    "follow_up_or_next": "next",
    "current_question_index": 1,
    "total_questions": 5
  }
  ```

#### `POST /interview/end`
- **Request Body:**
  ```json
  {
    "session_id": "8b5a1928-86d7-463f-9173-196b05423851"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "session_id": "8b5a1928-86d7-463f-9173-196b05423851",
    "status": "completed",
    "report": {
      "overall_score": 8.1,
      "dimension_scores": { "relevance": 8.4, "clarity": 8.0, "depth": 7.8, "examples": 8.2 },
      "strengths": ["..."],
      "weaknesses": ["..."],
      "improvement_tips": ["..."],
      "coach_recommendation": "Interview Answer Training",
      "summary": "..."
    }
  }
  ```

#### `GET /interview/report/{session_id}`
- **Response (200 OK):**
  Returns stored report JSON matching the above report schema.

### 4.6 Phase 2 Verification Curl Commands
```bash
# 1. Start interview
curl -X POST http://localhost:8000/interview/start \
  -H "Content-Type: application/json" \
  -d '{"candidate_name":"Alex","role":"Full Stack Engineer","experience_level":"Mid","interview_type":"technical"}'

# 2. Respond
curl -X POST http://localhost:8000/interview/respond \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<SESSION_ID>","answer_text":"I have built REST APIs with FastAPI and databases using PostgreSQL."}'

# 3. End interview and get report
curl -X POST http://localhost:8000/interview/end \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<SESSION_ID>"}'

# 4. Fetch saved report
curl -X GET http://localhost:8000/interview/report/<SESSION_ID>
```

---

## 5. Phase 3: Agent 2 (AI Communication Coach) & Profile Tracking

### 5.1 `CoachSession` Class & Supported Modes (`agents/coach.py`)
- **State Attributes:**
  - `session_id`: UUID string
  - `user_id`: UUID string
  - `mode`: `"conversation"`, `"answer_training"`, or `"english_improvement"`
  - `exchanges`: list of `{ "coach_message": str, "user_response_text": str, "correction": dict | None, "next_prompt": str, "timestamp": str }`
  - `user_profile`: dict containing `skill_level`, `weak_areas`, `strong_areas`, `sessions_count`

### 5.2 Coach Guardrails & Behavioral Constraints
- **Supportive Tone:** Patient, warm, encouraging, never condescending or sarcastic.
- **No Interruptions:** Never cut in mid-sentence.
- **Max 1–2 Corrections:** Never overwhelm the candidate; correct at most 1–2 high-impact items per exchange.
- **Strict Correction Format:**
  `"[Acknowledge what they said]. One small improvement: instead of saying '[their phrase]', you could say '[better alternative]'. This sounds more natural because [brief reason]. Want to try it?"`
- **Adaptive Difficulty:** Automatically scale complexity based on `user_profile.skill_level` (beginner, intermediate, advanced).
- **No Emotion/Confidence Claims:** Never claim to detect emotions or confidence from voice.
- **STAR Methodology:** In `"answer_training"`, guide responses using Situation, Task, Action, Result.
- **Profile Updates on End:** Identify recurring patterns, update `weak_areas`, `strong_areas`, increment `sessions_count`, and adjust `skill_level` in `public.users`.

### 5.3 Coach Endpoints Contract (`routers/coach.py`)

#### `POST /coach/start`
- **Request Body:**
  ```json
  {
    "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "mode": "conversation"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "session_id": "e4b3e4f2-9011-4091-8f55-7cf0b932de01",
    "opening_message": "Hi Alex! I'm your AI Communication Coach. Today we're going to practice natural everyday conversation. How was your weekend? Did you do anything fun?"
  }
  ```

#### `POST /coach/respond`
- **Request Body:**
  ```json
  {
    "session_id": "e4b3e4f2-9011-4091-8f55-7cf0b932de01",
    "user_text": "I was go to cinema with my friend and we watch very good movie."
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "coach_message": "That sounds like a fun weekend! One small improvement: instead of saying 'I was go to cinema and we watch', you could say 'I went to the cinema and we watched a great movie'. This sounds more natural because in the past tense, we use 'went' and 'watched'. Want to try using that in your next sentence?",
    "correction": {
      "original": "I was go to cinema and we watch",
      "improved": "I went to the cinema and we watched a great movie",
      "reason": "Past tense verbs 'went' and 'watched' are used for completed past events."
    },
    "next_prompt": "What movie did you watch, and what was your favorite part about it?"
  }
  ```

#### `POST /coach/end`
- **Request Body:**
  ```json
  {
    "session_id": "e4b3e4f2-9011-4091-8f55-7cf0b932de01"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "session_id": "e4b3e4f2-9011-4091-8f55-7cf0b932de01",
    "status": "completed",
    "summary": {
      "exchanges_count": 5,
      "key_learnings": [
        "Practiced simple past tense irregular verbs (went, saw, made).",
        "Improved transition words when explaining movie plots."
      ],
      "encouragement": "Great progress today Alex! Your fluency is improving visibly."
    },
    "updated_profile": {
      "skill_level": "intermediate",
      "weak_areas": ["past tense verb agreement"],
      "strong_areas": ["vocabulary breadth", "enthusiasm"],
      "sessions_count": 4
    }
  }
  ```

### 5.4 Phase 3 Verification Curl Commands
```bash
# 1. Start coach session
curl -X POST http://localhost:8000/coach/start \
  -H "Content-Type: application/json" \
  -d '{"user_id":"<USER_ID>","mode":"conversation"}'

# 2. Respond to coach
curl -X POST http://localhost:8000/coach/respond \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<COACH_SESSION_ID>","user_text":"I like programming because it make me feel creative."}'

# 3. End coach session
curl -X POST http://localhost:8000/coach/end \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<COACH_SESSION_ID>"}'
```

---

## 6. Phase 4: Production Hardening, Error Handling, and Deployment

### 6.1 Standardized Global Error Handling
FastAPI global exception handlers must intercept:
1. `RequestValidationError`: Returns HTTP 422 with structured field validation errors:
   `{"detail": "Validation error", "errors": [{"loc": ["body", "email"], "msg": "field required", "type": "missing"}]}`
2. `HTTPException`: Returns uniform JSON error object:
   `{"detail": "Session not found", "error_code": "NOT_FOUND"}`
3. `Exception` (catch-all): Logs internal traceback on server, returns HTTP 500:
   `{"detail": "An internal server error occurred. Please try again later.", "error_code": "INTERNAL_SERVER_ERROR"}`

### 6.2 Deployment Artifacts
- **`backend/Dockerfile`**:
  ```dockerfile
  FROM python:3.12-slim
  WORKDIR /app
  RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential && rm -rf /var/lib/apt/lists/*
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  EXPOSE 8000
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```
- **`backend/Procfile`**:
  ```procfile
  web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
  ```
- **`railway.json`**:
  ```json
  {
    "$schema": "https://railway.app/railway.schema.json",
    "build": {
      "builder": "DOCKERFILE",
      "dockerfilePath": "backend/Dockerfile"
    },
    "deploy": {
      "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
      "healthcheckPath": "/health",
      "healthcheckTimeout": 100,
      "restartPolicyType": "ON_FAILURE"
    }
  }
  ```

---

## 7. Comprehensive Discovered Features Table

## Features Discovered
| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Phase 0 Setup | Virtual Environment (`.venv`) | Dedicated environment for Python dependencies and execution | Python 3.11/3.12 binary | Isolated `.venv` directory | Aborts on invalid python binary | `ORIGINAL_REQUEST.md` R1 |
| 2 | Phase 0 Setup | Health Check (`GET /health`) | Service heartbeat and uptime validation | None | `{"status": "ok"}` (HTTP 200) | 500 if server degraded | `docs/03_PHASE_PLAN.md`, `ORIGINAL_REQUEST.md` |
| 3 | Phase 0 Setup | CORS Configuration | Allows Next.js frontend to interact with backend | HTTP headers (`Origin`, etc.) | CORS response headers | 403 / blocked if disallowed | `docs/02_TECH_STACK.md`, `ORIGINAL_REQUEST.md` |
| 4 | Phase 0 Setup | Supabase DDL Schema | Schema creation for users, interview_sessions, coach_sessions | SQL script execution | Tables & indexes created | SQL execution error on duplicate/invalid syntax | `docs/01_ARCHITECTURE.md`, `ORIGINAL_REQUEST.md` |
| 5 | Phase 1 Voice | LLM Client (`services/llm.py`) | Wrapper for NVIDIA Nemotron 70B OpenAI-compatible endpoint | messages list, system prompt | response string | Single retry on error; returns friendly fallback | `docs/02_TECH_STACK.md`, `docs/07_GUARDRAILS.md` |
| 6 | Phase 1 Voice | STT Client (`services/stt.py`) | Parakeet CTC 1.1B ASR REST transcription | audio bytes (WAV/PCM) | transcript string or None | Returns None on failure, logs error | `docs/02_TECH_STACK.md`, `docs/07_GUARDRAILS.md` |
| 7 | Phase 1 Voice | TTS Client (`services/tts.py`) | Magpie Multilingual TTS REST synthesis | text string, voice identifier | audio bytes (WAV) or None | Returns None on failure (browser fallback) | `docs/02_TECH_STACK.md`, `docs/07_GUARDRAILS.md` |
| 8 | Phase 1 Voice | Voice Process (`POST /voice/process`) | End-to-end voice loop: audio -> STT -> LLM -> TTS | Multipart audio file, agent_type | Transcribed text, LLM text, audio bytes | Graceful message if audio unparseable | `docs/03_PHASE_PLAN.md`, `ORIGINAL_REQUEST.md` |
| 9 | Phase 1 Auth | User Registration (`POST /auth/register`) | Register user with Supabase Auth and seed profile | email, password, name | user object, access token | 400 on duplicate email or weak password | `docs/03_PHASE_PLAN.md`, `docs/06_TASK_DIVISION.md` |
| 10 | Phase 1 Auth | User Login (`POST /auth/login`) | Authenticate user credentials via Supabase | email, password | user object, access token | 401 on invalid credentials | `docs/03_PHASE_PLAN.md`, `docs/06_TASK_DIVISION.md` |
| 11 | Phase 1 DB | Supabase Client Singleton | Unified singleton client for database queries & auth | Env vars: URL, SERVICE_KEY | Client instance | Raises configuration error or uses memory fallback | `docs/02_TECH_STACK.md`, `ORIGINAL_REQUEST.md` |
| 12 | Phase 2 Interview | Start Interview (`POST /interview/start`) | Initializes InterviewSession, seeds prompt, returns opening greeting | candidate_name, role, experience_level, interview_type | session_id, opening_message | 400 on missing or invalid role/type | `docs/03_PHASE_PLAN.md`, `docs/08_AGENT_PROMPTS.md` |
| 13 | Phase 2 Interview | Interview Respond (`POST /interview/respond`) | Evaluates answer, enforces 1 follow-up / 5 question boundaries | session_id, answer_text | spoken_response, is_complete, follow_up_or_next | 404 if session not found; 400 if ended | `docs/03_PHASE_PLAN.md`, `docs/08_AGENT_PROMPTS.md` |
| 14 | Phase 2 Interview | 4-Dimension Rubric Scoring | Internal scoring on Relevance, Clarity, Depth, Examples (1-10) | Candidate answer text | Score mapping `{relevance: 1-10, ...}` | Clamps scores between 1 and 10 | `docs/08_AGENT_PROMPTS.md`, `docs/07_GUARDRAILS.md` |
| 15 | Phase 2 Interview | End Interview (`POST /interview/end`) | Terminates session, triggers report generation, persists state | session_id | session_id, status: completed, report object | 404 if session not found | `docs/03_PHASE_PLAN.md`, `ORIGINAL_REQUEST.md` |
| 16 | Phase 2 Interview | Report Generation (`services/report.py`) | Compiles complete evaluation report via Nemotron | session_json data | Structured report JSON | Fallback calculation if LLM format fails | `docs/08_AGENT_PROMPTS.md`, `ORIGINAL_REQUEST.md` |
| 17 | Phase 2 Interview | Fetch Report (`GET /interview/report/{session_id}`) | Retrieves persisted interview performance report | session_id (path parameter) | Structured report JSON | 404 if session or report not found | `docs/03_PHASE_PLAN.md`, `ORIGINAL_REQUEST.md` |
| 18 | Phase 3 Coach | Start Coach Session (`POST /coach/start`) | Loads user profile, seeds coach mode, returns greeting | user_id, mode (conversation/answer_training/english_improvement) | session_id, opening_message | 400 on invalid mode; default profile if not found | `docs/03_PHASE_PLAN.md`, `docs/08_AGENT_PROMPTS.md` |
| 19 | Phase 3 Coach | Coach Respond (`POST /coach/respond`) | Acknowledges, supplies max 1-2 corrections with better alternative | session_id, user_text | coach_message, correction object, next_prompt | 404 if session not found | `docs/03_PHASE_PLAN.md`, `docs/08_AGENT_PROMPTS.md` |
| 20 | Phase 3 Coach | End Coach Session (`POST /coach/end`) | Finalizes session, updates communication profile in Supabase | session_id | session_id, summary, updated_profile | 404 if session not found | `docs/03_PHASE_PLAN.md`, `ORIGINAL_REQUEST.md` |
| 21 | Phase 3 Coach | Profile Learning Updater | Analyzes session corrections to update weak/strong areas & skill | session exchanges list | Updated communication profile JSON | Retains previous profile if analysis fails | `docs/07_GUARDRAILS.md`, `ORIGINAL_REQUEST.md` |
| 22 | Phase 4 Hardening | Global Exception Handlers | Uniform error formatting for validation, 404, and 500 errors | Request exceptions | Standardized JSON `{"detail": ..., "error_code": ...}` | Handled gracefully without crash | `docs/07_GUARDRAILS.md`, `ORIGINAL_REQUEST.md` |
| 23 | Phase 4 Deployment| Containerization (`Dockerfile`) | Slim Python container recipe for Railway deploy | Docker build context | Production container image | Build failure on missing dependencies | `docs/02_TECH_STACK.md`, `ORIGINAL_REQUEST.md` |
| 24 | Phase 4 Deployment| Railway Deployment Manifest | Configuration for automated Railway cloud deployment | `railway.json` / `Procfile` | Production service binding | Deployment error on invalid startCommand | `docs/02_TECH_STACK.md`, `ORIGINAL_REQUEST.md` |

---

## 8. Edge Cases and Resilience Behaviors

## Edge Cases
| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | Parakeet STT | Empty audio or corrupt audio bytes | `transcribe()` logs error, returns `None`; `/voice/process` returns friendly message: "Could not understand. Please try again." |
| 2 | Nemotron LLM | API timeout or HTTP 429/503 | Retries once after backoff; on second failure returns: "I am temporarily experiencing high traffic. Could you please repeat or summarize your last thought?" |
| 3 | Magpie TTS | Rate limit or API failure | `synthesize()` returns `None`; response payload returns text with `audio_url: null`; frontend falls back to Web Speech API |
| 4 | Interviewer Loop | Candidate says "I don't know" or remains silent | Notes lack of knowledge, awards low rubric score for depth/examples, acknowledges politely, and asks next question without scolding |
| 5 | Interviewer Loop | Candidate provides extremely brief 1-word answer | Asks maximum one follow-up: "Could you elaborate on that?", then advances to next question regardless of answer length |
| 6 | Interviewer Loop | Candidate goes completely off-topic | Acknowledges politely, redirects focus, and advances to the next structured question |
| 7 | Interviewer Boundary| Candidate attempts to answer beyond 5 questions | System detects `current_question_index >= 5`, sets `is_complete = True`, concludes: "We've covered all our questions. Let me prepare your report." |
| 8 | Coach Correction | User makes 5+ grammatical and vocabulary mistakes | Coach strictly limits feedback to the 1-2 most impactful corrections; does not overwhelm or embarrass user |
| 9 | Coach Profile | User has no existing communication profile in DB | Automatically initializes default beginner profile `{"skill_level": "intermediate", "weak_areas": [], "strong_areas": [], "sessions_count": 0}` |
| 10 | Report Generation | LLM fails to return valid JSON format | Backend regex/parser extracts JSON or falls back to computing exact mathematical averages of stored rubric scores and generates default structure |
| 11 | Database Outage | Supabase unreachable during session update | Returns HTTP 503 / 500 with clear message: "Database connection failed"; does not crash server process |

---

## 9. Non-Goals and Explicit Post-MVP Exclusions

Per `docs/04_MVP_vs_EXTRA.md` and `docs/07_GUARDRAILS.md`, the backend MUST NOT implement the following features during the MVP sprint:
1. **Resume Parsing / Upload (`Phase 5`)**: No PDF parsing, OCR, or file uploads for resume-based questions.
2. **Situational Interview Mode (`Phase 6`)**: Only HR and Technical modes are active for MVP.
3. **Voice Audio Emotion / Confidence Detection (`Phase 7`)**: No audio acoustic feature extraction, pitch analysis, or claims of detecting feelings.
4. **Pronunciation Audio Scoring (`Phase 7`)**: STT operates on transcription accuracy only; no phoneme scoring.
5. **Debate & Discussion Mode (`Phase 8`)**: Only Conversation, Answer Training, and English Improvement modes.
6. **Spaced Repetition / Flashcard Engine (`Phase 9`)**: Basic profile counters only.
7. **Streaming gRPC / WebSockets VoiceChat**: Standard REST audio pipeline (`/voice/process`) is the MVP implementation.
