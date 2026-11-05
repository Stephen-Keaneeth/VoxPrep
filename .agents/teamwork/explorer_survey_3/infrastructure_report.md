# VOXPREP Backend Infrastructure & Environment Survey Report

**Author:** explorer_survey_3  
**Date:** 2026-11-05  
**Working Directory:** `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer`  
**Target Milestone:** Milestone 1 / Phase 0 Initialization  

---

## 1. Current Workspace Directory Structure & Git Status

### 1.1 Filesystem Inspection
Direct inspection of the repository root (`d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer`) confirms the following directory layout:

```
AI-Interviewer/
├── .agents/                 # Teamwork agent metadata, briefings, and progress logs (untracked)
├── .git/                    # Git version control metadata (branch: main)
├── docs/                    # Architectural and specifications documentation (9 files)
│   ├── 00_PROJECT_OVERVIEW.md
│   ├── 01_ARCHITECTURE.md
│   ├── 02_TECH_STACK.md
│   ├── 03_PHASE_PLAN.md
│   ├── 04_MVP_vs_EXTRA.md
│   ├── 05_ACCEPTANCE_CRITERIA.md
│   ├── 06_TASK_DIVISION.md
│   ├── 07_GUARDRAILS.md
│   └── 08_AGENT_PROMPTS.md
└── README.md                # Project introduction, quickstart, and tech stack overview
```

### 1.2 State of Implementation Directories
- **`backend/` Directory:** Does NOT currently exist.
- **`frontend/` Directory:** Does NOT currently exist.
- **`.venv/` Virtual Environment:** Does NOT currently exist in root or subdirectories.
- **Git Status:** 
  - Working branch: `main`
  - Synced with: `origin/main`
  - Clean working tree except for `.agents/` directory (untracked).

---

## 2. Python Environment & Virtual Environment Management

### 2.1 Host Environment Details
- **Python Version:** `Python 3.12.10` (64-bit)
- **Binary Path:** `C:\Users\Stephen\AppData\Local\Programs\Python\Python312\python.exe`
- **Pip Version:** `pip 25.0.1`
- **Docker Engine:** `Docker 29.8.2` (Docker Desktop installed at `C:\Users\Stephen\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe`)
- **Railway CLI:** Not currently installed in system PATH (deployment configuration files `Dockerfile`, `railway.json`, and `Procfile` are required for automated build on git push).

### 2.2 Virtual Environment Setup Protocol
To satisfy Requirement R1 and Phase 0 Acceptance Criteria ("Dedicated Python virtual environment (`.venv`) is created, and all packages in `backend/requirements.txt` are installed into `.venv`"), the virtual environment setup commands are:

#### Windows (PowerShell / Command Prompt):
```powershell
# In project root or backend directory:
python -m venv .venv

# PowerShell activation:
.\.venv\Scripts\Activate.ps1

# If PowerShell script execution policy blocks activation:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

# Direct execution without activating shell:
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

#### Linux / macOS (Cross-Platform / CI / Railway):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

---

## 3. Supabase SQL Schema Design

The backend uses Supabase (PostgreSQL) for persistence and authentication. In accordance with `01_ARCHITECTURE.md`, `02_TECH_STACK.md`, and `08_AGENT_PROMPTS.md`, the database must store user profiles, mock interview sessions (Agent 1), and coaching sessions (Agent 2).

### 3.1 Table Schema Breakdown

#### Table 1: `users`
Stores user profile information and communication tracking metrics.
- `id` (`UUID`, Primary Key): References `auth.users(id) ON DELETE CASCADE` if Supabase Auth is enabled, with default `gen_random_uuid()` to support development/testing.
- `email` (`TEXT`, Unique, Not Null): User login identifier.
- `communication_profile` (`JSONB`, Not Null): Stores user coaching metrics:
  ```json
  {
    "skill_level": "intermediate",
    "weak_areas": [],
    "strong_areas": [],
    "sessions_count": 0
  }
  ```
- `created_at` (`TIMESTAMPTZ`, Not Null, Default `now()`)
- `updated_at` (`TIMESTAMPTZ`, Not Null, Default `now()`)

#### Table 2: `interview_sessions`
Stores full state and history for Agent 1 (AI Interviewer).
- `id` (`UUID`, Primary Key, Default `gen_random_uuid()`)
- `user_id` (`UUID`, Nullable, Foreign Key `REFERENCES users(id) ON DELETE SET NULL`): Allows guest interviews as well as registered user interviews.
- `candidate_name` (`TEXT`, Not Null)
- `role` (`TEXT`, Not Null)
- `experience_level` (`TEXT`, Not Null): e.g., 'entry', 'mid', 'senior'.
- `interview_type` (`TEXT`, Not Null): Constrained to `'hr'` or `'technical'`.
- `questions` (`JSONB`, Not Null, Default `'[]'::jsonb`): Array of questions and follow-ups asked during the session.
  ```json
  [
    {
      "question_number": 1,
      "question": "Tell me about a time you resolved a technical conflict.",
      "answer": "...",
      "follow_up": "What was the final outcome?",
      "follow_up_answer": "..."
    }
  ]
  ```
- `scores` (`JSONB`, Not Null, Default `'{}'::jsonb`): Dimension scores evaluated by the LLM:
  ```json
  {
    "question_1": { "relevance": 8, "clarity": 7, "depth": 7, "examples": 9 },
    "question_2": { "relevance": 9, "clarity": 8, "depth": 8, "examples": 8 }
  }
  ```
- `report` (`JSONB`, Nullable): Final generated report from `services/report.py` adhering to `08_AGENT_PROMPTS.md`:
  ```json
  {
    "overall_score": 8.0,
    "dimension_scores": {
      "relevance": 8.5,
      "clarity": 7.5,
      "depth": 7.5,
      "examples": 8.5
    },
    "strengths": ["Clear STAR structure used", "Strong technical vocabulary"],
    "weaknesses": ["Occasionally brief on edge cases"],
    "improvement_tips": ["Elaborate on trade-offs during system design answers"],
    "coach_recommendation": "Interview Answer Training",
    "summary": "Solid candidate performance with clear communication."
  }
  ```
- `is_complete` (`BOOLEAN`, Not Null, Default `FALSE`)
- `created_at` (`TIMESTAMPTZ`, Not Null, Default `now()`)
- `updated_at` (`TIMESTAMPTZ`, Not Null, Default `now()`)

#### Table 3: `coach_sessions`
Stores live coaching interactions and corrections for Agent 2 (AI Communication Coach).
- `id` (`UUID`, Primary Key, Default `gen_random_uuid()`)
- `user_id` (`UUID`, Nullable, Foreign Key `REFERENCES users(id) ON DELETE CASCADE`)
- `mode` (`TEXT`, Not Null): Constrained to `'conversation'`, `'answer_training'`, or `'english_improvement'`.
- `exchanges` (`JSONB`, Not Null, Default `'[]'::jsonb`): Array of turn-by-turn interactions:
  ```json
  [
    {
      "turn": 1,
      "coach_message": "Tell me about your favorite project.",
      "user_response_text": "I was make a web app with react.",
      "correction": {
        "original": "I was make",
        "improved": "I made",
        "reason": "Past simple tense is preferred when referring to a completed action in the past."
      },
      "next_prompt": "That's wonderful! What was the app designed to do?",
      "timestamp": "2026-11-05T16:00:00Z"
    }
  ]
  ```
- `created_at` (`TIMESTAMPTZ`, Not Null, Default `now()`)
- `updated_at` (`TIMESTAMPTZ`, Not Null, Default `now()`)

### 3.2 Complete PostgreSQL DDL Script (`supabase_schema.sql`)

```sql
-- =============================================================================
-- VOXPREP Supabase Database Schema Definition
-- Target: PostgreSQL 15+ (Supabase)
-- =============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Clean existing tables if needed (for fresh setup)
-- DROP TABLE IF EXISTS coach_sessions CASCADE;
-- DROP TABLE IF EXISTS interview_sessions CASCADE;
-- DROP TABLE IF EXISTS users CASCADE;

-- 1. USERS TABLE
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    communication_profile JSONB NOT NULL DEFAULT '{
        "skill_level": "intermediate",
        "weak_areas": [],
        "strong_areas": [],
        "sessions_count": 0
    }'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 2. INTERVIEW SESSIONS TABLE
CREATE TABLE IF NOT EXISTS public.interview_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    candidate_name TEXT NOT NULL,
    role TEXT NOT NULL,
    experience_level TEXT NOT NULL DEFAULT 'entry',
    interview_type TEXT NOT NULL CHECK (interview_type IN ('hr', 'technical')),
    questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    scores JSONB NOT NULL DEFAULT '{}'::jsonb,
    report JSONB DEFAULT NULL,
    is_complete BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 3. COACH SESSIONS TABLE
CREATE TABLE IF NOT EXISTS public.coach_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    mode TEXT NOT NULL CHECK (mode IN ('conversation', 'answer_training', 'english_improvement')),
    exchanges JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- =============================================================================
-- INDEXES FOR PERFORMANCE
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_user_id ON public.interview_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_created_at ON public.interview_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_complete ON public.interview_sessions(is_complete);
CREATE INDEX IF NOT EXISTS idx_coach_sessions_user_id ON public.coach_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_coach_sessions_created_at ON public.coach_sessions(created_at DESC);

-- Composite indexes for user dashboard queries
CREATE INDEX IF NOT EXISTS idx_interview_user_created ON public.interview_sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_coach_user_created ON public.coach_sessions(user_id, created_at DESC);

-- =============================================================================
-- AUTOMATIC updated_at TRIGGER FUNCTION
-- =============================================================================
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_users_updated_at ON public.users;
CREATE TRIGGER set_users_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_interview_sessions_updated_at ON public.interview_sessions;
CREATE TRIGGER set_interview_sessions_updated_at
    BEFORE UPDATE ON public.interview_sessions
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_coach_sessions_updated_at ON public.coach_sessions;
CREATE TRIGGER set_coach_sessions_updated_at
    BEFORE UPDATE ON public.coach_sessions
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

-- =============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =============================================================================
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.interview_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coach_sessions ENABLE ROW LEVEL SECURITY;

-- Allow full access to backend service role (SUPABASE_SERVICE_KEY)
CREATE POLICY "Service role full access on users" 
    ON public.users FOR ALL 
    TO service_role 
    USING (true) 
    WITH CHECK (true);

CREATE POLICY "Service role full access on interview_sessions" 
    ON public.interview_sessions FOR ALL 
    TO service_role 
    USING (true) 
    WITH CHECK (true);

CREATE POLICY "Service role full access on coach_sessions" 
    ON public.coach_sessions FOR ALL 
    TO service_role 
    USING (true) 
    WITH CHECK (true);

-- Allow authenticated users to view/manage their own records
CREATE POLICY "Users can view own profile" 
    ON public.users FOR SELECT 
    TO authenticated 
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" 
    ON public.users FOR UPDATE 
    TO authenticated 
    USING (auth.uid() = id);

CREATE POLICY "Users can view own interview sessions" 
    ON public.interview_sessions FOR SELECT 
    TO authenticated 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own interview sessions" 
    ON public.interview_sessions FOR INSERT 
    TO authenticated 
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view own coach sessions" 
    ON public.coach_sessions FOR SELECT 
    TO authenticated 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own coach sessions" 
    ON public.coach_sessions FOR INSERT 
    TO authenticated 
    WITH CHECK (auth.uid() = user_id);
```

---

## 4. FastAPI Layout & Dependencies

### 4.1 Required Directory Structure
In alignment with `02_TECH_STACK.md`, the backend will be structured as:

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI instance, CORS middleware, /health, router includes
│   ├── config.py                # Pydantic BaseSettings for NVIDIA_API_KEY, SUPABASE_*, PORT
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py              # POST /auth/register, POST /auth/login
│   │   ├── voice.py             # POST /voice/process
│   │   ├── interview.py         # POST /interview/start, /respond, /end, GET /report/{id}
│   │   └── coach.py             # POST /coach/start, /respond, /end
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── interviewer.py       # InterviewSession manager, rubric scoring, question limits
│   │   └── coach.py             # CoachSession manager, corrections engine, profile updates
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm.py               # Async NVIDIA Nemotron 70B wrapper (OpenAI SDK)
│   │   ├── stt.py               # Async NVIDIA Parakeet ASR REST client
│   │   ├── tts.py               # Async NVIDIA Magpie TTS REST client
│   │   └── report.py            # Report generator service (evaluates scores, strengths)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py              # Pydantic schemas: UserRegister, UserLogin, Profile
│   │   ├── session.py           # Pydantic schemas: StartInterviewRequest, AnswerRequest, CoachRequest
│   │   └── report.py            # Pydantic schemas: PerformanceReport, DimensionScores
│   └── db/
│       ├── __init__.py
│       └── supabase.py          # Supabase Client singleton (create_client)
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Test client, mock fixtures for LLM/STT/TTS/Supabase
│   ├── test_health.py           # GET /health test
│   ├── test_auth.py             # Auth endpoints test
│   ├── test_voice.py            # Audio processing endpoint test
│   ├── test_interview.py        # Interview session flow and rubric test
│   └── test_coach.py            # Coaching session and correction test
├── requirements.txt             # Pinned python dependencies
├── .env.example                 # Example configuration for local dev
├── Dockerfile                   # Production container definition
├── Procfile                     # Heroku/Railway process definition
├── railway.json                 # Railway deployment descriptor
└── supabase_schema.sql          # Database initialization DDL
```

### 4.2 Dependency Analysis & `requirements.txt` Specification

The dependencies must support Python 3.12 without C-extension compile errors and run cleanly on both Windows development machines and Linux container environments.

```text
# Web Framework & Server
fastapi>=0.110.0,<0.116.0
uvicorn[standard]>=0.28.0,<0.33.0

# Settings & Validation
pydantic>=2.6.0,<3.0.0
pydantic-settings>=2.2.0,<3.0.0

# AI & HTTP Integrations
openai>=1.14.0,<2.0.0           # NVIDIA Nemotron LLM via OpenAI-compatible API
httpx>=0.27.0,<0.29.0           # Asynchronous REST calls for Parakeet STT & Magpie TTS
python-multipart>=0.0.9          # Multipart form support for audio blob uploads

# Database & Auth
supabase>=2.3.0,<2.13.0
python-dotenv>=1.0.0

# Testing
pytest>=8.0.0,<9.0.0
pytest-asyncio>=0.23.0,<0.25.0
```

#### Package Compatibility Verification:
- **`fastapi` & `pydantic` v2:** Fully compatible with Python 3.12. Pydantic core utilizes pre-compiled wheels for Windows AMD64 and Linux AMD64/ARM64.
- **`openai` SDK:** Used specifically with `base_url="https://integrate.api.nvidia.com/v1"` and `api_key=NVIDIA_API_KEY`.
- **`httpx`:** Pure Python + `h11` async HTTP client, zero build dependencies, native timeout and streaming support.
- **`supabase`:** Uses `postgrest-py`, `gotrue-py`, and `storage3`—fully operational in Python 3.12.
- **`python-multipart`:** Necessary for FastAPI `UploadFile` / `File(...)` in `POST /voice/process`.

### 4.3 Environment Configuration (`backend/.env.example`)

```ini
# =============================================================================
# VOXPREP Backend Environment Variables
# =============================================================================

# Server Binding
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development

# NVIDIA NIM AI Services
# Obtain free API key (~1000 credits) at https://build.nvidia.com
NVIDIA_API_KEY=nvapi-your_nvidia_api_key_here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_LLM_MODEL=nvidia/llama-3.1-nemotron-70b-instruct
NVIDIA_STT_MODEL=nvidia/parakeet-ctc-1.1b-asr
NVIDIA_TTS_MODEL=nvidia/magpie-tts-multilingual

# Supabase Persistence & Auth
# Obtain project credentials at https://supabase.com/dashboard
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your-supabase-service-role-key
SUPABASE_ANON_KEY=your-supabase-anon-key

# CORS Origins (Comma-separated)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://voxprep.vercel.app
```

---

## 5. Deployment Configuration (Railway & Docker)

### 5.1 Railway Execution Model
Railway injects a dynamic `$PORT` environment variable during container deployment (e.g., `PORT=5678` or `PORT=8000`).
The backend application must:
1. Bind to host `0.0.0.0` (not `127.0.0.1` or `localhost`), allowing ingress routing.
2. Read the dynamic `$PORT` environment variable, defaulting to `8000` when running locally.

### 5.2 Production Dockerfile (`backend/Dockerfile`)
The Dockerfile uses a lean multi-stage or slim Python 3.12 image, ensures non-root security, installs dependencies, and launches uvicorn with shell parameter expansion for `$PORT`:

```dockerfile
# Use official lightweight Python 3.12 slim image
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Set working directory
WORKDIR /app

# Install system dependencies (curl for health check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose default port
EXPOSE 8000

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Launch uvicorn with dynamic PORT binding
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
```

### 5.3 Railway Configuration Descriptor (`backend/railway.json`)
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### 5.4 Heroku / Alternative Procfile (`backend/Procfile`)
```text
web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

---

## 6. Implementation Readiness Assessment

| Requirement Item | Status | Action Item for Phase 0 Implementation |
|---|---|---|
| **Python venv** | Ready | Run `python -m venv .venv` in repository root, activate, and upgrade pip |
| **Backend Directory** | Ready | Scaffold `backend/` and `app/` subdirectories per Section 4.1 |
| **Database DDL** | Ready | Apply `supabase_schema.sql` via Supabase SQL Editor |
| **Dependencies** | Ready | Install `backend/requirements.txt` into `.venv` |
| **Deployment Files**| Ready | Place `Dockerfile`, `railway.json`, and `Procfile` in `backend/` |
| **Health Endpoint** | Ready | Implement `app/main.py` with `GET /health` returning `{"status": "ok"}` |
