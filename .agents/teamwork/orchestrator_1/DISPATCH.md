# Dispatch History

## 2026-11-05T15:54:39Z
Sender: 0e2f8978-8aea-4506-99df-3d2b69760286
Content:
Build the backend MVP for VOXPREP — an AI-powered voice interview and communication coaching hackathon platform (Member A tasks) using FastAPI, NVIDIA NIM APIs (Nemotron LLM, Parakeet STT, Magpie TTS), and Supabase for persistence and authentication.

Working directory: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer
Integrity mode: development

Documentation references:
- docs/00_PROJECT_OVERVIEW.md
- docs/02_TECH_STACK.md
- docs/03_PHASE_PLAN.md
- docs/04_MVP_vs_EXTRA.md
- docs/05_ACCEPTANCE_CRITERIA.md
- docs/06_TASK_DIVISION.md
- docs/07_GUARDRAILS.md
- docs/08_AGENT_PROMPTS.md

## Requirements

### R1. Phase 0: Project Initialization, Environment, and Setup
- Set up and use a dedicated Python virtual environment (`.venv`) for all package installations, development, testing, and service execution.
- Initialize the `backend/` directory structure matching the specification:
  - `backend/app/main.py` with CORS middleware configured and `GET /health` returning `{"status": "ok"}`.
  - `backend/requirements.txt` containing all required packages (FastAPI, uvicorn, openai, supabase, python-dotenv, httpx, pydantic, pytest, etc.) installed into `.venv`.
  - `backend/.env.example` documenting required environment variables: `NVIDIA_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`.
  - Supabase SQL schema script defining `users`, `interview_sessions`, and `coach_sessions` tables.
- Do not build frontend code, do not build post-MVP features, and do not commit real API keys.

### R2. Phase 1: AI Services, Voice Pipeline, and Authentication
- NVIDIA API configuration: Verify the current Parakeet STT and Magpie TTS endpoint URLs, request formats, and model identifiers before implementation. Do not assume all NVIDIA NIM services use identical REST formats.
- Implement `backend/app/services/llm.py`: Async wrapper around NVIDIA Nemotron (`nvidia/llama-3.1-nemotron-70b-instruct`) using the OpenAI-compatible SDK with base URL `https://integrate.api.nvidia.com/v1`, exposing `async def chat(messages: list, system_prompt: str) -> str`. Retry once on failure, then return a friendly error.
- Implement `backend/app/services/stt.py`: NVIDIA Parakeet ASR REST API integration exposing `async def transcribe(audio_bytes: bytes) -> str | None`. On failure, return `None` and log the error.
- Implement `backend/app/services/tts.py`: NVIDIA Magpie TTS REST API integration exposing `async def synthesize(text: str) -> bytes | None`. On failure, return `None` (frontend falls back to Web Speech API).
- Implement `backend/app/routers/voice.py`: `POST /voice/process` endpoint accepting an audio blob, executing STT -> LLM -> TTS, and returning audio bytes.
- Implement `backend/app/routers/auth.py`: `POST /auth/register` and `POST /auth/login` using the Supabase Auth SDK.
- Implement `backend/app/db/supabase.py`: Supabase client singleton.
- Provide sample curl commands to test each endpoint.

### R3. Phase 2: AI Interviewer Agent and Session Management
- Implement `backend/app/agents/interviewer.py`:
  - `InterviewSession` class with `session_id`, user info, `interview_type` (`hr` or `technical`), question history, and dimension scores.
  - System prompts and logic adhering to `docs/08_AGENT_PROMPTS.md` and `docs/07_GUARDRAILS.md`.
  - Methods: `start_session(candidate_name, role, experience, interview_type) -> opening_message` and `process_answer(session_id, answer_text) -> {"spoken_response": str, "is_complete": bool}`.
  - Evaluate answers on 4 dimensions: Relevance, Clarity, Depth, Examples (1–10 scale).
  - Enforce session boundaries: maximum 5 questions per session, maximum 1 follow-up per question.
  - Session persistence: Supabase must be the persistent source of truth for session state; load and update session data as requests arrive.
- Implement `backend/app/services/report.py`: `generate_report(session_data) -> dict` generating structured JSON report per `docs/08_AGENT_PROMPTS.md`.
- Implement `backend/app/routers/interview.py`:
  - `POST /interview/start`: body `{candidate_name, role, experience_level, interview_type}`, returns `{session_id, opening_message}`.
  - `POST /interview/respond`: body `{session_id, answer_text}`, returns `{spoken_response, is_complete, follow_up_or_next}`.
  - `POST /interview/end`: body `{session_id}`, triggers report generation, persists completed session and report to Supabase `interview_sessions`.
  - `GET /interview/report/{session_id}`: returns full JSON report.
- Save complete sessions (questions, answers, scores, report) to Supabase `interview_sessions`.
- Document exact request and response shapes for all endpoints so Member B can connect the frontend.

### R4. Phase 3: AI Communication Coach Agent
- Implement `backend/app/agents/coach.py`:
  - `CoachSession` class with `session_id`, `user_id`, `mode`, and exchange history.
  - Supported modes: `"conversation"`, `"answer_training"`, `"english_improvement"`.
  - System prompts and rules adhering to `docs/08_AGENT_PROMPTS.md` and `docs/07_GUARDRAILS.md`.
  - Methods: `start_session(user_id, mode) -> opening_message` (loading user communication profile from Supabase) and `process_response(session_id, user_text) -> {"coach_message": str, "correction": {original, improved, reason} | None, "next_prompt": str}`.
  - Correct at most 1–2 items per exchange; maintain supportive tone, never interrupt.
  - On session end: update user communication profile (`skill_level`, `weak_areas`, `strong_areas`) in Supabase.
- Implement `backend/app/routers/coach.py`:
  - `POST /coach/start`: body `{user_id, mode}`, returns `{session_id, opening_message}`.
  - `POST /coach/respond`: body `{session_id, user_text}`, returns `{coach_message, correction, next_prompt}`.
  - `POST /coach/end`: body `{session_id}`, saves session exchanges to Supabase `coach_sessions` and updates user profile.
- Save session exchanges to Supabase `coach_sessions` table.
- Document exact request and response shapes for all coach endpoints.

### R5. Phase 4: Production Hardening, Error Handling, and Deployment
- Global error handling: all endpoints return meaningful JSON errors with appropriate HTTP status codes, never crashing silently.
- Provide comprehensive backend documentation in `README.md` (setup steps including `.venv` activation, required environment variables, execution instructions, API contract reference for Member B).
- Deployment to Railway:
  - Provide containerization/deployment configuration files (`Dockerfile`, `railway.json` / `Procfile`).
  - If Railway CLI and credentials are authenticated in the environment, execute live deployment to Railway and confirm `GET /health` on the production URL. Otherwise, document the exact Railway deployment steps and verify production startup locally.
