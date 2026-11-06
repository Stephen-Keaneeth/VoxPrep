# Project: VoxPrep Frontend Ground-Up Rebuild

## Architecture
- Framework: Next.js 14 App Router, TypeScript, Tailwind CSS, Zustand.
- Single Source of Truth: FastAPI Backend (`http://127.0.0.1:8000`) & Database Schema (`backend/schema.sql`).
- Contract Architecture:
  - All network traffic flows through typed functions in `frontend/lib/api.ts`.
  - State management in `frontend/store/useStore.ts` stores only live user sessions, active session IDs (`interviewSessionId`, `coachSessionId`), and fetched report payloads.
  - No client-side database access (no Supabase SDK), no unbacked features (no resume parsing route or modal).
  - Score normalization uniformly converts backend 1.0–10.0 scale to 0–100% via `score <= 10 ? Math.round(score * 10) : score`.
  - Dark theme tokens: Canvas `#0B1120`, Surface `#111A2E`, Brand `#2563EB`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | API Client Types & Endpoints | Strictly typed client methods for all 9 backend endpoints matching Pydantic schemas | M1 | Survey (`spec_miner_backend`) |
| 2 | Zustand Application State | Minimal store for user auth, session IDs, and report payloads without mock bloat | M1 | Survey (`explorer_frontend`) |
| 3 | Purge Unbacked Features | Remove resume parser route, PDF parser, and Supabase client bypass | M1 | Survey (`explorer_frontend`) |
| 4 | WebRTC Preview & Video Room | Camera/audio candidate preview with stream cleanup and mute controls | M2 | Survey (`explorer_contracts`) |
| 5 | Interview Lifecycle Flow | `POST /interview/start`, `POST /voice/process`, `POST /interview/respond`, `POST /interview/end` | M2 | Survey (`backend_spec.md`) |
| 6 | Spoken Audio Playback | Natural turn-taking with audio playback of interviewer responses | M2 | Survey (`explorer_contracts`) |
| 7 | Coach Mode Selector | Mode selection with exact backend modes (`conversation`, `answer_training`, `english_improvement`) | M2 | Survey (`backend_spec.md`) |
| 8 | Coach Refinement & Metrics | Display `CoachCorrection` card (`original`, `improved`, `reason`), live WPM & filler word detection | M2 | Survey (`explorer_contracts`) |
| 9 | Interview Report Dashboard | `/analytics/interview` rendering `InterviewReport` with normalized scores, dimension breakdown, strengths/weaknesses/actions | M3 | Survey (`backend_spec.md`) |
| 10 | Communication Report Dashboard | `/analytics/communication` rendering WPM, filler word count, grammar, fluency tier, key learnings, corrections | M3 | Survey (`backend_spec.md`) |
| 11 | Authentication Pages | `/login` & `/register` calling `POST /auth/login` and `POST /auth/register` with guest access support | M3 | Survey (`backend_spec.md`) |
| 12 | Score Normalization Utility | `score <= 10 ? Math.round(score * 10) : score` across all cards, badges, and progress rings | M3 | Survey (`contracts_analysis.md`) |
| 13 | Styling & Responsive Layout | Dark palette (`#0B1120`, `#111A2E`, `#2563EB`), responsive layouts, zero video caption clutter | M4 | Survey (`explorer_frontend`) |
| 14 | Quality Checks & Build | Zero type errors (`npx tsc --noEmit`), zero ESLint errors (`npm run lint`), clean production build (`npm run build`) | M4 | Survey (`explorer_frontend`) |
| 15 | Integration Verification | Scripted automated verification against live running FastAPI backend (`http://127.0.0.1:8000`) | M4 | Survey (`spec_miner_backend`) |
| 16 | Independent Review & Audit | Independent Reviewer, Challenger stress tests, and Forensic Integrity Audit | M5 | Project Pattern Gate |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Agent A: API Client & State Architect | `frontend/lib/api.ts`, `frontend/store/useStore.ts`, removal of unbacked files | Survey | DONE |
| M2 | Agent B: Core Interaction Rooms | `/interview`, `/coach`, WebRTC preview, voice turn-taking, WPM/filler metrics | M1 | DONE |
| M3 | Agent C: Analytics Dashboards & Auth | `/analytics/interview`, `/analytics/communication`, `/login`, `/register`, score normalization | M1 | DONE |
| M4 | Agent D: Quality, Build & Integration | Styling pass, navigation, `tsc`, `lint`, `build`, scripted integration against FastAPI | M2, M3 | DONE |
| M5 | Quality & Integrity Verification Gate | Reviewers, Challengers, and Forensic Auditor | M4 | DONE |

## Key Outputs
- M1 outputs:
  - `frontend/lib/api.ts`: 100% strictly typed API client mapping to all 9 FastAPI endpoints + health check + ApiError envelope.
  - `frontend/store/useStore.ts`: Clean Zustand store holding only live user sessions, active session IDs, and report payloads. Purged fake candidate "Anish", fake resume, and pre-baked mock history.
  - Deleted `frontend/app/api/parse-resume/route.ts` and `frontend/lib/resumeParser.ts`. Stripped direct Supabase client DB operations.
  - Verified: `tsc` exit 0, `lint` exit 0, `build` exit 0, `verify_agent_a.mjs` all passed.
- M2 outputs:
  - `frontend/app/interview/page.tsx` & `frontend/components/sections/InterviewAgent.tsx`: WebRTC preview, MediaRecorder audio capture, POST /voice/process + POST /interview/respond, text entry fallback, natural spoken audio turn-taking, POST /interview/end with redirect to /analytics/interview, purged all fake Kafka questions and ResumeUploadModal.
  - `frontend/app/coach/page.tsx` & `frontend/components/sections/CommunicationAgent.tsx`: 3 backend modes (`conversation`, `answer_training`, `english_improvement`), dynamic prompts, real-time linguistic refinement cards (`{ original, improved, reason }`), live WPM & filler word detection, POST /coach/end redirecting to /analytics/communication.
  - Verified: `tsc` exit 0, `lint` exit 0, `build` exit 0, `verify_agent_b.mjs` all passed.
- M3 outputs:
  - `frontend/lib/normalization.ts`: Authoritative `normalizeScore` helper formula (`score <= 10 ? Math.round(score * 10) : score`).
  - `frontend/app/analytics/interview/page.tsx` & `frontend/components/sections/InterviewDashboard.tsx`: Interview evaluation dashboard with normalized scores, 4 dimensions, question breakdown table, coach CTA, and clean empty state.
  - `frontend/app/analytics/communication/page.tsx` & `frontend/components/sections/CommunicationDashboard.tsx`: Communication report dashboard with WPM, filler word count, grammar score, fluency tier, key learnings, and logged linguistic corrections list.
  - `frontend/app/(auth)/login/page.tsx` & `frontend/app/(auth)/register/page.tsx`: Full auth flow with Zustand token storage, ApiError display, and guest access links.
  - Verified: `tsc` exit 0, `lint` exit 0, `build` exit 0, `verify_agent_c.mjs` all passed.
- M4 outputs:
  - `frontend/components/Sidebar.tsx` & `frontend/components/Header.tsx`: Clean navigation mapped directly to all active routes (`/interview`, `/coach`, `/analytics/interview`, `/analytics/communication`, `/login`, `/register`).
  - `frontend/components/sections/HomeDashboard.tsx`: Purged unbacked resume banner and fake fallback statistics.
  - `frontend/tests/verify_integration_e2e.mjs`: Automated integration test suite verifying all 11 endpoints and contracts against running FastAPI backend.
  - Verified: `tsc` exit 0, `lint` exit 0, `build` exit 0 (11 routes), `verify_agent_a`, `verify_agent_b`, `verify_agent_c`, `verify_integration_e2e`, and `pytest` (487/487) all passed 100%.
- M5 outputs:
  - `GATE_STATUS.md`: All gate checks PASS.
  - Reviewer 1 (Rep): APPROVE.
  - Reviewer 2: APPROVE.
  - Challenger 1: APPROVE (68 assertions passed).
  - Challenger 2: APPROVE (36 tests passed against live FastAPI on port 8000).
  - Forensic Auditor: CLEAN (Zero mock bloat, genuine logic verified).
