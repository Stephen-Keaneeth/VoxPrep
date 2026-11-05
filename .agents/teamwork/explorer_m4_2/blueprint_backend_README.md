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
│   ├── main.py                     # FastAPI application entrypoint & middleware
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
├── tests/                          # 314+ automated unit & integration tests
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_services.py
│   ├── test_voice.py
│   ├── test_auth.py
│   ├── test_interview.py
│   ├── test_coach.py
│   └── test_errors.py
├── requirements.txt                # Pinned production Python dependencies
├── .env.example                    # Template environment variables
├── schema.sql                      # Idempotent Supabase PostgreSQL schema
├── Dockerfile                      # Production container specification
├── railway.json                    # Railway deployment manifest
└── Procfile                        # ASGI process runner for PaaS
```

---

## 🚀 Step-by-Step Local Setup Guide

Follow these exact steps to set up and run the backend locally in an isolated virtual environment.

### 1. Prerequisites
- **Python**: 3.11 or 3.12 (Python 3.12 recommended). Verify with:
  ```bash
  python --version
  ```
- **NVIDIA NIM API Key**: Free key from [build.nvidia.com](https://build.nvidia.com) (includes ~1,000 free credits covering full development and hackathon runs).
- **Supabase Account**: Free project from [supabase.com](https://supabase.com).

---

### 2. Create and Activate Virtual Environment (`.venv`)

A dedicated virtual environment ensures zero package contamination across your local machine.

#### Windows (PowerShell):
```powershell
# Navigate to project root or backend folder
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

VOXPREP includes comprehensive automated tests covering all routers, services, agent state machines, and error conditions.

```bash
# Run all tests with clean summary output:
pytest backend/tests -v

# Run with test execution time profiling:
pytest backend/tests --durations=10

# Run specific domain test modules:
pytest backend/tests/test_interview.py
pytest backend/tests/test_coach.py
pytest backend/tests/test_voice.py
pytest backend/tests/test_auth.py
```

---

## 📡 Complete API Reference for Member B (Frontend Lead)

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

> 📘 **Full Request/Response JSON Schemas & cURL Commands**:  
> See the dedicated guide: [`.agents/teamwork/explorer_m4_2/api_contract_reference.md`](../.agents/teamwork/explorer_m4_2/api_contract_reference.md) for full details on payload shapes, status codes, and copy-pasteable curl test commands.

---

## 🛡️ Guardrails & Error Status Codes

VOXPREP backend never crashes silently. All exceptions produce consistent JSON error payloads:

```json
{
  "detail": "Descriptive message",
  "error_type": "validation_error | http_error | internal_server_error",
  "status_code": 400
}
```

- **HTTP 400 (Bad Request)**: Business logic violation (e.g. empty answer submitted, invalid coach mode, interview report requested before session completion).
- **HTTP 401 (Unauthorized)**: Incorrect email or password on login.
- **HTTP 404 (Not Found)**: Invalid `session_id` or `user_id`.
- **HTTP 422 (Unprocessable Entity)**: Missing required JSON keys or invalid data types.
- **HTTP 500 (Internal Server Error)**: Upstream service failure; logged safely with stack trace, returning safe error message to client.

---

## 🚢 Production Deployment (Railway)

VOXPREP backend is containerized with a production-ready `Dockerfile` and configured for [Railway.app](https://railway.app):

```bash
# Build and verify local Docker container:
docker build -t voxprep-backend backend/
docker run -p 8000:8000 --env-file backend/.env voxprep-backend
```

On Railway:
1. Connect your GitHub repository to Railway.
2. Set the root directory to `backend/`.
3. Add the environment variables from `backend/.env.example` in Railway Project Settings.
4. Railway automatically detects `Dockerfile` / `railway.json` and deploys the service with a live public URL.
