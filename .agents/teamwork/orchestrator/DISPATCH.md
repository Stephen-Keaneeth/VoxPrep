# Dispatch Instructions

## 2026-11-06T09:11:48Z

Rebuild the Next.js frontend (`frontend/`) from the ground up as a capability showcase for VoxPrep, using the existing FastAPI backend (`backend/`) and database schema (`backend/schema.sql`) as the absolute single source of truth. Divide and execute the rebuild using the following specialized sub-agents: Agent A: API Client & State Architect, Agent B: Core Interaction Rooms (Interview & Coach), Agent C: Analytics Dashboards & Auth, Agent D: Quality, Build & Integration Lead.

Working directory: c:\Project\VoxPrep
Integrity mode: development

## Requirements

### R1. Single Source of Truth & Backend Contract Alignment
- Rebuild the Next.js frontend (`frontend/`) from the ground up, using the existing FastAPI backend (`backend/`) and database schema (`backend/schema.sql`) as the absolute single source of truth.
- Build ONLY what the backend requires and defines—no extra dummy features, no superfluous tabs, and no mocked bloat. Every UI element, form, and dashboard card must directly map to an active backend route, model, or database field across `backend/app/main.py`, `backend/app/routers/auth.py`, `backend/app/routers/voice.py`, `backend/app/routers/interview.py`, `backend/app/routers/coach.py`, `backend/app/models/report.py`, and `backend/schema.sql`.
- Do NOT create features not backed by backend endpoints, and do NOT modify backend route definitions or database schemas.

### R2. API Client and Application State
- Implement `frontend/lib/api.ts` with 100% strict TypeScript types matching the Pydantic schemas in `backend/app/routers/` and `backend/app/models/`.
- Provide typed client methods for all 9 backend endpoints (`auth`, `voice`, `interview`, `coach`, `health`).
- Implement clean Zustand state in `frontend/store/useStore.ts` storing only live user sessions, current active session IDs, and report payloads.

### R3. Core Interaction Rooms (Interview and Coach)
- **Technical/HR Interview Room (`/interview`)**:
  - WebRTC video/audio stream for candidate preview.
  - Automatically call `POST /interview/start` to obtain `session_id` and verbal opening greeting. Support guest access with optional `user_id` or active authenticated user ID.
  - Voice recording component capturing audio, posting to `POST /voice/process` and `POST /interview/respond`.
  - Spoken audio playback of interviewer's response with natural turn-taking.
  - "End Interview" trigger calling `POST /interview/end` and redirecting directly to `/analytics/interview`.
- **Communication Coach Room (`/coach`)**:
  - Mode selector with the exact 3 backend modes: `conversation`, `answer_training`, and `english_improvement`.
  - Dynamically display `opening_message` and `next_prompt`.
  - Real-time linguistic refinement card displaying `correction: { original, improved, reason }` when returned by `POST /coach/respond`.
  - Voice recording with live WPM calculation and filler word detection.
  - "Conclude Session" trigger calling `POST /coach/end`.

### R4. Analytics Dashboards and Authentication
- **Interview Report (`/analytics/interview`)**: Render the exact `InterviewReport` model with normalized overall score (0–100%), 4 dimension scores (`relevance`, `clarity`, `depth`, `examples`), summary, coach recommendation with CTA, strengths, weaknesses, action items, and per-question breakdown table.
- **Communication Report (`/analytics/communication`)**: Render session summary including WPM, filler word count, grammar score, fluency tier, key learnings, and logged linguistic corrections.
- **Auth Pages (`/login`, `/register`)**: Simple, clean forms calling `POST /auth/login` and `POST /auth/register`. Interaction rooms allow guest / unauthenticated access where the backend accepts optional `user_id`.
- **Score Normalization**: All scores on the 1.0–10.0 backend scale must be cleanly normalized for UI percentage display (`score <= 10 ? Math.round(score * 10) : score`).

### R5. Styling, Quality, Build & Verification
- Enforce strict styling: dark palette (`#0B1120`, `#111A2E`, `#2563EB`), responsive layouts, zero video caption clutter.
- Verification mechanism: Ensure clean build, zero TypeScript type errors (`npx tsc --noEmit`), zero ESLint errors/warnings (`npm run lint`), and automated scripted integration verification against the running FastAPI backend on `http://127.0.0.1:8000`.
