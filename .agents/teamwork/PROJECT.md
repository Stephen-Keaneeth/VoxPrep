# Project: VOXPREP Backend MVP

## Architecture
- **Framework**: FastAPI (Python 3.12)
- **External AI Provider**: NVIDIA NIM APIs (`https://integrate.api.nvidia.com/v1`)
  - LLM: `nvidia/llama-3.1-nemotron-70b-instruct` (OpenAI-compatible async client)
  - STT: `nvidia/parakeet-ctc-1.1b-asr` (REST audio transcriptions endpoint)
  - TTS: `nvidia/magpie-tts-multilingual` (REST speech synthesis endpoint)
- **Database & Auth**: Supabase (PostgreSQL with JSONB + Supabase Auth SDK)
- **Design Pattern**: Clean Architecture with Router -> Agent/Service -> Database/External Provider separation.
- **Dual Track Orchestration**: Implementation Track (Milestones 0–4 -> Final) + E2E Testing Track.

## Code Layout
```
backend/
├── app/
│   ├── main.py
│   ├── db/
│   │   ├── __init__.py
│   │   └── supabase.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm.py
│   │   ├── stt.py
│   │   ├── tts.py
│   │   └── report.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── interviewer.py
│   │   └── coach.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── session.py
│   │   └── report.py
│   └── routers/
│       ├── __init__.py
│       ├── auth.py
│       ├── voice.py
│       ├── interview.py
│       └── coach.py
├── tests/
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_services.py
│   ├── test_voice.py
│   ├── test_auth.py
│   ├── test_interview.py
│   └── test_coach.py
├── requirements.txt
├── .env.example
├── schema.sql
├── Dockerfile
├── railway.json
└── Procfile
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Virtual Environment (`.venv`) | Dedicated environment for Python dependencies and execution | M0 | `ORIGINAL_REQUEST.md` R1 |
| 2 | Health Check (`GET /health`) | Service heartbeat and uptime validation | M0 | `ORIGINAL_REQUEST.md` R1 |
| 3 | CORS Configuration | Configured for frontend origins | M0 | `ORIGINAL_REQUEST.md` R1 |
| 4 | Supabase DDL Schema | Schema creation for users, interview_sessions, coach_sessions | M0 | `ORIGINAL_REQUEST.md` R1 |
| 5 | LLM Client (`services/llm.py`) | Wrapper for NVIDIA Nemotron 70B with retry fallback | M1 | `ORIGINAL_REQUEST.md` R2 |
| 6 | STT Client (`services/stt.py`) | Parakeet CTC 1.1B ASR REST transcription | M1 | `ORIGINAL_REQUEST.md` R2 |
| 7 | TTS Client (`services/tts.py`) | Magpie Multilingual TTS REST synthesis | M1 | `ORIGINAL_REQUEST.md` R2 |
| 8 | Voice Process (`POST /voice/process`) | End-to-end voice loop: audio -> STT -> LLM -> TTS | M1 | `ORIGINAL_REQUEST.md` R2 |
| 9 | User Registration (`POST /auth/register`) | Register user with Supabase Auth | M1 | `ORIGINAL_REQUEST.md` R2 |
| 10 | User Login (`POST /auth/login`) | Authenticate user credentials via Supabase | M1 | `ORIGINAL_REQUEST.md` R2 |
| 11 | Supabase Client Singleton | Unified singleton client for database queries & auth | M1 | `ORIGINAL_REQUEST.md` R2 |
| 12 | Start Interview (`POST /interview/start`) | Initializes InterviewSession, seeds prompt, returns opening | M2 | `ORIGINAL_REQUEST.md` R3 |
| 13 | Interview Respond (`POST /interview/respond`) | Evaluates answer, enforces 1 follow-up / 5 question boundaries | M2 | `ORIGINAL_REQUEST.md` R3 |
| 14 | 4-Dimension Rubric Scoring | Internal scoring on Relevance, Clarity, Depth, Examples (1-10) | M2 | `ORIGINAL_REQUEST.md` R3 |
| 15 | End Interview (`POST /interview/end`) | Terminates session, triggers report generation, persists state | M2 | `ORIGINAL_REQUEST.md` R3 |
| 16 | Report Generation (`services/report.py`) | Compiles complete evaluation report via Nemotron | M2 | `ORIGINAL_REQUEST.md` R3 |
| 17 | Fetch Report (`GET /interview/report/{session_id}`) | Retrieves persisted interview performance report | M2 | `ORIGINAL_REQUEST.md` R3 |
| 18 | Start Coach Session (`POST /coach/start`) | Loads profile, seeds coach mode, returns greeting | M3 | `ORIGINAL_REQUEST.md` R4 |
| 19 | Coach Respond (`POST /coach/respond`) | Acknowledges, supplies max 1-2 corrections with alternative | M3 | `ORIGINAL_REQUEST.md` R4 |
| 20 | End Coach Session (`POST /coach/end`) | Finalizes session, updates communication profile | M3 | `ORIGINAL_REQUEST.md` R4 |
| 21 | Profile Learning Updater | Analyzes session corrections to update weak/strong areas | M3 | `ORIGINAL_REQUEST.md` R4 |
| 22 | Global Exception Handlers | Uniform error formatting for validation, 404, and 500 errors | M4 | `ORIGINAL_REQUEST.md` R5 |
| 23 | Containerization (`Dockerfile`) | Slim Python container recipe for Railway deploy | M4 | `ORIGINAL_REQUEST.md` R5 |
| 24 | Railway Deployment Manifest | Configuration for automated Railway cloud deployment | M4 | `ORIGINAL_REQUEST.md` R5 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M0 | Phase 0 Setup & Environment | `.venv`, `requirements.txt`, `.env.example`, `schema.sql`, `main.py` skeleton with `GET /health` | none | DONE |
| M1 | Phase 1 AI Services & Voice Pipeline | `services/llm.py`, `services/stt.py`, `services/tts.py`, `db/supabase.py`, `routers/voice.py`, `routers/auth.py`, test mocks & curl commands | M0 | DONE |
| M2 | Phase 2 Interviewer Agent & Sessions | `agents/interviewer.py`, `services/report.py`, `routers/interview.py`, session management & persistence, rubric scoring, report retrieval | M1 | PLANNED |
| M3 | Phase 3 Communication Coach Agent | `agents/coach.py`, `routers/coach.py`, profile management, session persistence, 3 coach modes | M1 | PLANNED |
| M4 | Phase 4 Hardening & Deployment | Global error handlers, README backend docs, Dockerfile, railway.json, Procfile, local/live deployment verification | M2, M3 | PLANNED |
| M-Final | Final Acceptance & Adversarial Hardening | Phase 1: 100% E2E test pass (Tiers 1–4). Phase 2: Tier 5 adversarial coverage hardening | M4, E2E | PLANNED |

## Interface Contracts

### 1. Supabase Singleton (`db/supabase.py`)
```python
def get_supabase_client() -> Client:
    """Returns thread-safe singleton Supabase client or in-memory mock fallback."""
```

### 2. AI Services
```python
# services/llm.py
async def chat(messages: list[dict], system_prompt: str) -> str:
    """Invokes Nemotron 70B via AsyncOpenAI with single retry. Returns string or fallback."""

# services/stt.py
async def transcribe(audio_bytes: bytes) -> str | None:
    """Invokes Parakeet ASR REST API. Returns transcript or None."""

# services/tts.py
async def synthesize(text: str) -> bytes | None:
    """Invokes Magpie TTS REST API. Returns audio bytes (WAV) or None."""

# services/report.py
async def generate_report(session_data: dict) -> dict:
    """Generates structured JSON evaluation report."""
```

### 3. Interviewer Agent (`agents/interviewer.py`)
```python
class InterviewSession:
    def __init__(self, session_id: str, candidate_name: str, role: str, experience_level: str, interview_type: str): ...
    async def start_session(self) -> str: ...
    async def process_answer(self, answer_text: str) -> dict:
        """Returns {"spoken_response": str, "is_complete": bool, "follow_up_or_next": str}"""
```

### 4. Coach Agent (`agents/coach.py`)
```python
class CoachSession:
    def __init__(self, session_id: str, user_id: str, mode: str): ...
    async def start_session(self) -> str: ...
    async def process_response(self, user_text: str) -> dict:
        """Returns {"coach_message": str, "correction": dict | None, "next_prompt": str}"""
```
