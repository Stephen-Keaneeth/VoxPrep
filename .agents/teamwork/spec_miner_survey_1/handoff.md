# Handoff Report — Specification Mining for Member A (Backend MVP)

> **Agent:** `spec_miner_survey_1`  
> **Directory:** `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\spec_miner_survey_1`  
> **Target:** Orchestrator & Backend Engineering Agents  
> **Type:** Hard Handoff (Task Complete)

---

## 1. Observation

1. **Original Request:**
   - Evaluated `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\ORIGINAL_REQUEST.md` (lines 1–112), which dictates requirements for Member A across Phases 0–4:
     - Phase 0: Project setup, `.venv`, `backend/` directory structure, `requirements.txt`, `.env.example`, Supabase SQL schema (`users`, `interview_sessions`, `coach_sessions`).
     - Phase 1: NVIDIA Nemotron (`nvidia/llama-3.1-nemotron-70b-instruct`), Parakeet STT (`nvidia/parakeet-ctc-1.1b-asr`), Magpie TTS (`nvidia/magpie-tts-multilingual`), `POST /voice/process`, Supabase client, Supabase auth (`/auth/register`, `/auth/login`), error handling & fallbacks.
     - Phase 2: `InterviewSession`, prompts from `docs/08_AGENT_PROMPTS.md`, 4-dimension scoring (1–10), boundaries (<=5 questions, <=1 follow-up per question), `generate_report`, endpoints (`/interview/start`, `/interview/respond`, `/interview/end`, `/interview/report/{session_id}`).
     - Phase 3: `CoachSession` (modes: conversation, answer_training, english_improvement), prompts from `docs/08_AGENT_PROMPTS.md`, <=1–2 corrections per exchange, profile persistence, endpoints (`/coach/start`, `/coach/respond`, `/coach/end`).
     - Phase 4: Production hardening, global error handlers, README docs for Member B, Dockerfile, `railway.json`/Procfile.

2. **Project Documentation:**
   - `docs/00_PROJECT_OVERVIEW.md` (lines 25–32): Establishes the dual-agent architecture (Agent 1: AI Interviewer, Agent 2: AI Communication Coach).
   - `docs/01_ARCHITECTURE.md` (lines 48–77, 166–196): Documents voice pipeline (MediaRecorder -> STT -> LLM -> TTS -> Audio Playback) and database models for User, InterviewSession, and CoachSession.
   - `docs/02_TECH_STACK.md` (lines 11–26, 57–65, 112–136): Defines base URL `https://integrate.api.nvidia.com/v1`, models `nvidia/llama-3.1-nemotron-70b-instruct`, `nvidia/parakeet-ctc-1.1b-asr`, `nvidia/magpie-tts-multilingual`, and exact directory structure under `backend/`.
   - `docs/03_PHASE_PLAN.md` (lines 23–185): Details per-phase tasks, deliverables, and approval gates.
   - `docs/04_MVP_vs_EXTRA.md` (lines 11–75): Categorizes MVP features vs Post-MVP exclusions (no resume parsing, no emotion detection, no situational mode, no pronunciation scoring).
   - `docs/05_ACCEPTANCE_CRITERIA.md` (lines 8–103): Enumerates strict pass/fail criteria for Phases 0 through 4.
   - `docs/06_TASK_DIVISION.md` (lines 21–99): Delineates Member A (Backend / AI) and Member B (Frontend / UI) sync points and deliverables.
   - `docs/07_GUARDRAILS.md` (lines 10–102): Enforces strict AI rules: max 1 follow-up per question, max 5 questions, max 1–2 coach corrections, single LLM retry with friendly fallback, STT/TTS returning `None` gracefully, no tutor behavior during interviews.
   - `docs/08_AGENT_PROMPTS.md` (lines 8–228): Verbatim system prompts for HR interview, Technical interview, Report Generation, and Communication Coach across 3 modes.

3. **External Verification of NVIDIA NIM Services:**
   - Web search on `integrate.api.nvidia.com/v1` confirmed:
     - Parakeet CTC 1.1B ASR REST endpoint: `POST /v1/audio/transcriptions` (OpenAI-compatible multipart form-data, model `nvidia/parakeet-ctc-1.1b-asr`).
     - Magpie Multilingual TTS REST endpoint: `POST /v1/audio/synthesize` (multipart form-data with `text`, `language="en-US"`, `voice="Magpie-Multilingual.EN-US.Aria"`, `encoding="LINEAR_PCM"`, `sample_rate_hz=44100`).

4. **Repository State:**
   - Verified Python runtime: Python 3.12.10 installed on system.
   - The directory `backend/` does not yet exist; greenfield implementation is ready to commence in order from Phase 0.

---

## 2. Logic Chain

1. From `ORIGINAL_REQUEST.md` and `docs/06_TASK_DIVISION.md`, Member A is responsible for the entire backend implementation, AI client integrations, database persistence, and API contracts.
2. `docs/02_TECH_STACK.md` and `docs/07_GUARDRAILS.md` lock the tech stack to FastAPI, Supabase, and NVIDIA NIM (`https://integrate.api.nvidia.com/v1`).
3. External API inspection shows NVIDIA NIM models follow OpenAI-compatible endpoints (`/v1/chat/completions`, `/v1/audio/transcriptions`) and standard REST endpoints (`/v1/audio/synthesize`).
4. To allow Member B to develop the Next.js frontend concurrently, every backend endpoint contract must have explicit request and response JSON schemas, status codes, and error formats.
5. Guardrails in `docs/07_GUARDRAILS.md` require resilient error recovery:
   - LLM: Retry once on failure, then fallback message.
   - STT: Return `None` on transcription failure, frontend/router prompts user to repeat.
   - TTS: Return `None` on synthesis failure, fallback to browser Web Speech API.
   - Interview Session: Max 5 questions, max 1 follow-up, 4 rubric dimensions (1–10).
   - Coach Session: Max 1–2 corrections per exchange, specific correction format with reasoning and better alternative.
6. The comprehensive specification report in `spec_report.md` captures all 24 discovered features, 11 edge cases, exact endpoint contracts, DDL schemas, and deployment recipes.

---

## 3. Caveats

1. **Live NVIDIA NIM API Key Availability:** Live invocation of NVIDIA NIM services requires a valid `NVIDIA_API_KEY` with available credits. In testing and offline environments, service wrappers must provide mock fallbacks to enable CI/automated tests without network calls.
2. **Supabase Connectivity:** If live Supabase credentials (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`) are not provided during local testing, an in-memory repository or mock DB client must be provided to avoid blocking unit tests.
3. **Audio File Formats:** While Parakeet CTC ASR handles WAV/Linear PCM natively, browser recordings may arrive as WebM/Opus. The backend should accept binary audio or standard formats supported by multipart uploads.

---

## 4. Conclusion

The specification mining for VOXPREP Member A (Backend MVP) is 100% complete. All authoritative project documents and NVIDIA NIM requirements have been probed, verified, and synthesized into `spec_report.md`. The specifications are unambiguous and directly actionable for implementing Phases 0 through 4.

---

## 5. Verification Method

To independently verify this specification report:
1. Inspect the generated report:
   ```powershell
   Get-Content -Path ".agents/teamwork/spec_miner_survey_1/spec_report.md" -TotalCount 100
   ```
2. Verify cross-references against authoritative docs:
   - Check schema matches `docs/01_ARCHITECTURE.md` §5.
   - Check agent prompts match `docs/08_AGENT_PROMPTS.md`.
   - Check guardrails match `docs/07_GUARDRAILS.md`.
   - Check phase milestones match `docs/03_PHASE_PLAN.md` and `docs/05_ACCEPTANCE_CRITERIA.md`.
3. Invalidation conditions: Any addition of post-MVP features (resume upload, situational mode, emotion detection) or deviations from the 4 scoring dimensions or single follow-up limit violates the specification.
