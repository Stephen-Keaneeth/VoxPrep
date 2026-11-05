# VOXPREP Backend 🎙️⚡
### FastAPI Service for AI Voice Interviews, Communication Coaching & NVIDIA NIM Integration

Welcome to the backend service for **VOXPREP** — an AI-powered voice interview and communication coaching platform built for high-throughput, voice-first interaction using **FastAPI**, **NVIDIA NIM APIs** (Nemotron LLM, Parakeet STT, Magpie TTS), and **Supabase** (PostgreSQL + Auth).

---

## 🏗️ Architecture Overview

```
                                ┌──────────────────────────────────────────────┐
                                │          VOXPREP Client (Next.js)           │
                                └───────▲──────────────────────────────▲───────┘
                                        │ Voice Audio                  │ REST JSON
                                        ▼                              ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│ FastAPI Application (`backend/app/main.py`)                                           │
│ CORS Middleware (W3C credentials compliant) | Global Error Handling (400,404,422,500) │
├───────────────────────────────────────────────────────────────────────────────────────┤
│                                   ROUTERS                                             │
│  • `/auth`       : User Registration & Login (Supabase Auth SDK)                      │
│  • `/voice`      : End-to-End Voice Processing Loop                                  │
│  • `/interview`  : Agent 1 (Mock Interview Lifecycle & Report Generation)            │
│  • `/coach`      : Agent 2 (Communication Coaching & Profile Learning)                │
├───────────────────────────────────────────────────────────────────────────────────────┤
│                             AGENT & SERVICE LAYER                                     │
│  ┌───────────────────────┐  ┌────────────────────────┐  ┌─────────────────────────┐  │
│  │ InterviewerAgent      │  │ CoachAgent             │  │ ReportService           │  │
│  │ • 4-Dimension Rubric  │  │ • 3 Practice Modes     │  │ • Structured JSON Eval  │  │
│  │ • Max 1 Follow-up     │  │ • Max 1-2 Corrections  │  │ • Actionable Feedback   │  │
│  │ • Max 5 Questions     │  │ • Adaptive Profiles    │  │ • Coach Recommendation  │  │
│  └──────────┬────────────┘  └───────────┬────────────┘  └────────────┬────────────┘  │
│             └───────────────────────────┼────────────────────────────┘                │
│                                         ▼                                             │
│                                  AI SERVICES                                          │
│  ┌──────────────────────────┬──────────────────────────┬───────────────────────────┐  │
│  │ LLM Client (`llm.py`)    │ STT Client (`stt.py`)    │ TTS Client (`tts.py`)     │  │
│  │ NVIDIA Nemotron 70B      │ NVIDIA Parakeet CTC 1.1B │ NVIDIA Magpie Multilingual│  │
│  │ Base: OpenAI Async Client│ REST Audio Transcriptions│ REST Speech Synthesis     │  │
│  │ Auto-Retry & Fallbacks   │ Corrupt/Empty Safe       │ Web Speech API Fallback   │  │
│  └──────────┬───────────────┴──────────┬───────────────┴───────────┬───────────────┘  │
└─────────────┼──────────────────────────┼───────────────────────────┼──────────────────┘
              ▼                          ▼                           ▼
┌────────────────────────────────────────────────────────┐ ┌───────────────────────────┐
│             NVIDIA NIM Cloud APIs                      │ │    Supabase PostgreSQL    │
│  https://integrate.api.nvidia.com/v1                   │ │  • `users`                │
│  (Single NVIDIA_API_KEY for LLM, STT, and TTS)         │ │  • `interview_sessions`   │
└────────────────────────────────────────────────────────┘ │  • `coach_sessions`       │
                                                           └───────────────────────────┘
```

---

## 📁 Backend Directory Layout

```
backend/
├── app/
│   ├── main.py                     # FastAPI application entrypoint & ASGI error middleware
│   ├── db/
│   │   ├── __init__.py
│   │   ├── supabase.py             # Supabase client singleton & mock fallback
│   │   ├── session_persistence.py  # Interview session persistence & retrieval
│   │   └── coach_persistence.py    # Coach session persistence & profile learning
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm.py                  # NVIDIA Nemotron 70B LLM client with retry
│   │   ├── stt.py                  # NVIDIA Parakeet CTC 1.1B ASR client
│   │   ├── tts.py                  # NVIDIA Magpie multilingual TTS client
│   │   └── report.py               # Structured interview report generator
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── interviewer.py          # Agent 1 Interviewer state machine & rubric scoring
│   │   └── coach.py                # Agent 2 Communication coach state machine
│   ├── models/
│   │   ├── __init__.py
│   │   ├── session.py              # Pydantic persistence models
│   │   └── report.py               # Interview evaluation report schema
│   └── routers/
│       ├── __init__.py
│       ├── auth.py                 # POST /auth/register, POST /auth/login
│       ├── voice.py                # POST /voice/process
│       ├── interview.py            # POST /interview/start, respond, end, GET report
│       └── coach.py                # POST /coach/start, respond, end
├── tests/                          # 324+ automated unit & integration tests
│   ├── conftest.py                 # In-memory ASGI LocalClient test fixture
│   ├── test_health.py              # Health check & CORS tests
│   ├── test_services.py            # LLM, STT, TTS unit tests with mock fallbacks
│   ├── test_voice.py               # Voice pipeline audio processing tests
│   ├── test_auth.py                # Authentication registration and login tests
│   ├── test_interview.py           # Interviewer agent state machine tests
│   ├── test_coach.py               # Coach agent state machine tests
│   └── test_errors.py              # 400, 404, 422, 500 & CORS error handling tests
├── requirements.txt                # Pinned production Python dependencies
├── .env.example                    # Template environment variables
├── schema.sql                      # Idempotent Supabase PostgreSQL schema
├── Dockerfile                      # Production container specification (Python 3.12-slim)
├── railway.json                    # Railway deployment manifest
├── Procfile                        # ASGI process runner for PaaS
└── .dockerignore                   # Docker build context exclusions
```

---

## 🚀 Step-by-Step Local Setup Guide

Follow these exact steps to set up and run the backend locally in an isolated virtual environment.

### 1. Prerequisites
- **Python**: 3.11 or 3.12 (Python 3.12 recommended). Verify with:
  ```bash
  python --version
  ```
- **NVIDIA NIM API Key**: Free key from [build.nvidia.com](https://build.nvidia.com) (includes ~1,000 free credits covering full development runs).
- **Supabase Account**: Free project from [supabase.com](https://supabase.com).

---

### 2. Create and Activate Virtual Environment (`.venv`)

A dedicated virtual environment ensures zero package contamination across your local machine.

#### Windows (PowerShell):
```powershell
# Navigate to project root
cd "d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer"

# Create .venv
python -m venv .venv

# Activate .venv
.\.venv\Scripts\Activate.ps1
```
*(If PowerShell blocks script execution, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

#### Windows (Command Prompt - CMD):
```cmd
cd "d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer"
python -m venv .venv
.\.venv\Scripts\activate.bat
```

#### Linux / macOS (bash / zsh):
```bash
cd AI-Interviewer
python3 -m venv .venv
source .venv/bin/activate
```

---

### 3. Install Python Dependencies

With `.venv` activated, install the locked production dependencies:

```bash
pip install --upgrade pip
pip install -r backend/requirements.txt
```
*(If working directly inside the `backend/` directory, run `pip install -r requirements.txt`).*

---

### 4. Configure Environment Variables (`.env`)

Copy the environment template and configure your credentials:

```bash
# From the backend directory:
cp .env.example .env
```

Edit `backend/.env` with your preferred editor:

```ini
# ==============================================================================
# VOXPREP Backend Environment Variables
# ==============================================================================

# Server Configuration
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development

# CORS Configuration (comma-separated origins or * for dev)
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# NVIDIA NIM API Configuration
# Get your free key at https://build.nvidia.com
NVIDIA_API_KEY=nvapi-your_nvidia_api_key_here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_LLM_MODEL=nvidia/llama-3.1-nemotron-70b-instruct
NVIDIA_STT_MODEL=nvidia/parakeet-ctc-1.1b-asr
NVIDIA_TTS_MODEL=nvidia/magpie-tts-multilingual

# Supabase Configuration
# Found in: Supabase Dashboard -> Project Settings -> API
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_public_key_here
SUPABASE_SERVICE_KEY=your_supabase_service_role_secret_key_here
```

> **Note on Mock Fallback**: If `NVIDIA_API_KEY` or `SUPABASE_URL` is omitted during local development, the backend automatically operates in **mock fallback mode**, returning simulated intelligent responses and in-memory persistence so you and Member B can develop frontend components without blocker.

---

### 5. Initialize Supabase Database Schema

1. Open your project on [Supabase Dashboard](https://supabase.com/dashboard).
2. Click **SQL Editor** on the left menu.
3. Paste the contents of `backend/schema.sql` and click **Run**.
4. This idempotently provisions:
   - `users` (with JSONB `communication_profile`)
   - `interview_sessions` (with question history and 4-dimension scores)
   - `coach_sessions` (with practice exchanges and corrections)
   - Indexes and Row-Level Security (RLS) policies.

---

### 6. Run the Backend Server

Start the FastAPI application with auto-reload:

```bash
# From project root:
uvicorn app.main:app --reload --app-dir backend --host 0.0.0.0 --port 8000

# OR if your terminal is in the backend/ directory:
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify the server is running:
- **API Root**: [http://localhost:8000/](http://localhost:8000/)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Reference**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

### 7. Run Automated Test Suite

VOXPREP includes comprehensive automated tests covering all routers, services, agent state machines, and error conditions:

```bash
# Run all tests with clean summary output:
pytest backend/tests -v

# Run with test execution time profiling:
pytest backend/tests --durations=10

# Run specific domain test modules:
pytest backend/tests/test_errors.py
pytest backend/tests/test_interview.py
pytest backend/tests/test_coach.py
pytest backend/tests/test_voice.py
pytest backend/tests/test_auth.py
```

---

## 🛡️ Global Error Handling & Uniform Error Envelope

All exceptions (Starlette HTTP exceptions, Pydantic validation errors, and unhandled server errors) produce a consistent JSON envelope with CORS headers preserved:

```json
{
  "detail": "Descriptive message or validation breakdown",
  "error_type": "http_error | validation_error | internal_server_error",
  "status_code": 400
}
```

### Status Code Matrix
| Status Code | Error Type | Cause | Client Action |
|---|---|---|---|
| **200 OK** | - | Successful request | Parse response body |
| **201 Created** | - | Successful resource creation (`/auth/register`) | Store JWT token, proceed |
| **400 Bad Request** | `http_error` | Domain constraint violation (e.g. invalid coach mode, premature report) | Display `detail` in toast alert |
| **401 Unauthorized** | `http_error` | Invalid email or password | Prompt user to retry login |
| **404 Not Found** | `http_error` | Resource or route not found | Show 404 state or redirect |
| **422 Unprocessable** | `validation_error` | Missing required fields or invalid types | Display field error highlights |
| **500 Internal Error** | `internal_server_error` | Unhandled backend exception (sanitized, zero leak) | Display "AI service temporarily unavailable" |

---

## 📡 Complete API Contract Reference for Member B (Frontend Lead)

**Local Base URL**: `http://localhost:8000`  
**Production Base URL**: `https://<your-railway-domain>.up.railway.app`  

### Endpoint Summary Table
| HTTP Method | Route | Description | Expected Payload |
|---|---|---|---|
| `GET` | `/health` | Service uptime and heartbeat | None |
| `GET` | `/` | Service metadata and doc links | None |
| `POST` | `/auth/register` | Register new user + init profile | `{ email, password, name? }` |
| `POST` | `/auth/login` | Login user, get JWT token | `{ email, password }` |
| `POST` | `/voice/process` | Audio in -> STT -> LLM -> TTS -> Audio out | `multipart/form-data`: `file`, `agent_type?`, `session_id?` |
| `POST` | `/interview/start` | Start interview, returns opening | `{ candidate_name, role, experience_level, interview_type, user_id? }` |
| `POST` | `/interview/respond` | Submit answer, rubric eval, follow-up | `{ session_id, answer_text }` |
| `POST` | `/interview/end` | End interview, generate evaluation report | `{ session_id }` |
| `GET` | `/interview/report/{id}` | Fetch full performance report JSON | Path parameter `session_id` |
| `POST` | `/coach/start` | Start coaching session in selected mode | `{ user_id, mode }` |
| `POST` | `/coach/respond` | Evaluate answer, return max 1-2 corrections | `{ session_id, user_text }` |
| `POST` | `/coach/end` | End coaching session & update profile | `{ session_id }` |

---

### Detailed Endpoint Specifications with cURL Examples

#### 1. `GET /health` (Health Check)
- **Response (200 OK)**:
  ```json
  {"status": "ok"}
  ```
- **cURL**:
  ```bash
  curl -X GET http://localhost:8000/health
  ```

#### 2. `GET /` (Service Information)
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
- **cURL**:
  ```bash
  curl -X GET http://localhost:8000/
  ```

#### 3. `POST /auth/register` (User Registration)
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "email": "alex.candidate@example.com",
    "password": "StrongPassword123!",
    "name": "Alex Candidate"
  }
  ```
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
- **cURL**:
  ```bash
  curl -X POST http://localhost:8000/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"alex.candidate@example.com","password":"StrongPassword123!","name":"Alex Candidate"}'
  ```

#### 4. `POST /auth/login` (User Login)
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "email": "alex.candidate@example.com",
    "password": "StrongPassword123!"
  }
  ```
- **Response (200 OK)**: Same structure as register response.
- **cURL**:
  ```bash
  curl -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"alex.candidate@example.com","password":"StrongPassword123!"}'
  ```

#### 5. `POST /voice/process` (Voice Pipeline)
- **Headers**: `Content-Type: multipart/form-data`
- **Form Fields**:
  - `file` (binary, required): WAV audio file recorded by client browser.
  - `agent_type` (string, optional): `"interview"` (default) or `"coach"`.
  - `session_id` (string, optional): Active session UUID.
- **Response (200 OK)**:
  ```json
  {
    "transcript": "I built a real-time event pipeline using FastAPI and Kafka.",
    "spoken_response": "That sounds robust. How did you handle consumer backpressure?",
    "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQ...",
    "session_id": "f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9"
  }
  ```
- **Fallback**: If `audio_base64` is null, frontend uses `window.speechSynthesis` with `spoken_response`.
- **cURL**:
  ```bash
  curl -X POST http://localhost:8000/voice/process \
    -F "file=@sample.wav;type=audio/wav" \
    -F "agent_type=interview" \
    -F "session_id=f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9"
  ```

#### 6. `POST /interview/start` (Start Interview)
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
- **Response (200 OK)**:
  ```json
  {
    "session_id": "f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9",
    "opening_message": "Hello Alex Candidate, welcome to your Senior Backend Engineer technical interview. Let's begin: Could you describe the architecture of a high-concurrency API you designed?"
  }
  ```
- **cURL**:
  ```bash
  curl -X POST http://localhost:8000/interview/start \
    -H "Content-Type: application/json" \
    -d '{"candidate_name":"Alex Candidate","role":"Senior Backend Engineer","experience_level":"Mid-Senior (4 years)","interview_type":"technical"}'
  ```

#### 7. `POST /interview/respond` (Submit Answer)
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "session_id": "f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9",
    "answer_text": "We deployed FastAPI microservices with Redis caching and achieved sub-50ms latency."
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "spoken_response": "How did you ensure cache consistency across instances?",
    "is_complete": false,
    "follow_up_or_next": "follow_up",
    "question_index": 0,
    "current_question_index": 0,
    "total_questions": 5
  }
  ```
- **cURL**:
  ```bash
  curl -X POST http://localhost:8000/interview/respond \
    -H "Content-Type: application/json" \
    -d '{"session_id":"f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9","answer_text":"We deployed FastAPI microservices with Redis caching."}'
  ```

#### 8. `POST /interview/end` (Conclude Interview & Generate Report)
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
      "strengths": ["Clear articulation of caching architecture"],
      "areas_for_improvement": ["Include quantitative latency percentiles"],
      "question_breakdown": [
        {
          "question": "Could you describe the architecture of a high-concurrency API you designed?",
          "answer_summary": "Explained FastAPI microservices and Redis caching.",
          "scores": {"relevance": 9.0, "clarity": 8.5, "depth": 8.0, "examples": 8.5},
          "feedback": "Strong answer demonstrating practical experience."
        }
      ],
      "action_items": ["Practice STAR framework for behavioral questions"],
      "coach_recommendation": "Interview Answer Training",
      "summary": "Solid overall performance demonstrating senior competencies."
    }
  }
  ```
- **cURL**:
  ```bash
  curl -X POST http://localhost:8000/interview/end \
    -H "Content-Type: application/json" \
    -d '{"session_id":"f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9"}'
  ```

#### 9. `GET /interview/report/{session_id}` (Retrieve Report)
- **Response (200 OK)**: Returns the structured report JSON object.
- **cURL**:
  ```bash
  curl -X GET http://localhost:8000/interview/report/f8a4e1d2-7c3b-419a-9e2e-8367a12b45e9
  ```

#### 10. `POST /coach/start` (Start Coach Session)
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "user_id": "e2a3c77d-b5df-4279-bfbe-d45091f04db5",
    "mode": "answer_training"
  }
  ```
  *(Modes: `"conversation"`, `"answer_training"`, `"english_improvement"`)*
- **Response (200 OK)**:
  ```json
  {
    "session_id": "c1f8e2a3-9b4d-4567-89ab-cdef01234567",
    "opening_message": "Hello! In this Answer Training session, we'll practice structuring your responses with clarity and confidence. Tell me about a challenging project you delivered.",
    "mode": "answer_training"
  }
  ```
- **cURL**:
  ```bash
  curl -X POST http://localhost:8000/coach/start \
    -H "Content-Type: application/json" \
    -d '{"user_id":"e2a3c77d-b5df-4279-bfbe-d45091f04db5","mode":"answer_training"}'
  ```

#### 11. `POST /coach/respond` (Coach Feedback Turn)
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
    "coach_message": "You clearly communicated your experience! Here is a minor phrasing polish that will sound more professional.",
    "correction": {
      "original": "I am working as backend engineer since 4 years and I do python coding very good.",
      "improved": "I have been working as a backend engineer for four years, and I am highly proficient in Python development.",
      "reason": "Uses present perfect continuous ('have been working') and professional phrasing."
    },
    "next_prompt": "Could you now describe a specific technical challenge you overcame?"
  }
  ```
- **cURL**:
  ```bash
  curl -X POST http://localhost:8000/coach/respond \
    -H "Content-Type: application/json" \
    -d '{"session_id":"c1f8e2a3-9b4d-4567-89ab-cdef01234567","user_text":"I am working as backend engineer since 4 years."}'
  ```

#### 12. `POST /coach/end` (Conclude Coaching & Update Profile)
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
- **cURL**:
  ```bash
  curl -X POST http://localhost:8000/coach/end \
    -H "Content-Type: application/json" \
    -d '{"session_id":"c1f8e2a3-9b4d-4567-89ab-cdef01234567"}'
  ```

---

## 🚢 Production Deployment (Railway)

VOXPREP backend is containerized with a production-ready `Dockerfile` and configured for [Railway.app](https://railway.app):

### 1. Build and Run Container Locally
```bash
# Build Docker image
docker build -t voxprep-backend -f backend/Dockerfile ./backend

# Run container locally on port 8000
docker run --rm -d -p 8000:8000 --env-file backend/.env voxprep-backend

# Check health endpoint
curl http://localhost:8000/health
```

### 2. Deploy to Railway via GitHub Integration
1. Push your repository to GitHub.
2. Sign in to [Railway.app](https://railway.app) and click **+ New Project** -> **Deploy from GitHub repo**.
3. Select this repository.
4. In service **Settings**:
   - Set **Root Directory** to `backend`.
   - Verify **Builder** is `Dockerfile` (using `backend/Dockerfile` and `backend/railway.json`).
   - In **Networking**, click **Generate Domain**.
5. In service **Variables**, add the keys from `backend/.env.example` (`NVIDIA_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ALLOWED_ORIGINS`). *(Do NOT set `PORT` — Railway sets it dynamically).*
6. Railway automatically builds the container, executes `/health` checks, and serves the application live.
