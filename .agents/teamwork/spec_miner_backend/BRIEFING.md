# BRIEFING — 2026-11-06T09:28:30Z

## Mission
Thoroughly analyze backend codebase to discover, probe, and document the authoritative specification and contract for all backend endpoints, scoring metrics, scales, coach modes, correction structures, and report models.

## 🔒 My Identity
- Archetype: teamwork_spec_miner
- Roles: Specification Investigator, Backend Contract Miner
- Working directory: c:\Project\VoxPrep\.agents\teamwork\spec_miner_backend\
- Original parent: 55e0bf3f-dbbe-407b-930a-d465c34fe1ef
- Milestone: Backend Specification Extraction

## 🔒 Key Constraints
- Read-only on application codebase; do NOT implement or alter backend code.
- Write only to `.agents/teamwork/spec_miner_backend/`.
- Prioritize authoritative source code over prior assumptions.
- Must document all endpoints, schemas, error behaviors, metric scales, coach modes, corrections, and database interactions.

## Current Parent
- Conversation ID: 55e0bf3f-dbbe-407b-930a-d465c34fe1ef
- Updated: 2026-11-06T09:28:30Z

## Task Summary
- **What to build**: Comprehensive backend specification document (`backend_spec.md`) and handoff report (`handoff.md`).
- **Success criteria**: Complete contract documentation for all 9 core backend endpoints (+ 2 health/root), with request/response schemas, error handling, auth/guest user_id behavior, database models/queries, scoring metrics (scale ranges), coach modes, correction object shapes, and report models.
- **Interface contracts**: `c:\Project\VoxPrep\.agents\teamwork\ORIGINAL_REQUEST.md`, backend router files.
- **Code layout**: Backend is in `backend/app/`.

## Key Decisions Made
- Fully documented all 12 backend endpoints (2 Auth, 1 Voice, 4 Interview, 3 Coach, 1 Health, 1 Root).
- Clarified scoring scale: backend uses 1.0–10.0 float scale (`ge=1.0, le=10.0`), normalized to 0–100% on frontend using `score <= 10 ? Math.round(score * 10) : score`.
- Clarified guest user_id behavior: optional for `/interview/start`, auto-provisioned default baseline profile in `/coach/start`.
- Documented 7 canonical coach taxonomy tags and 3 coach modes: `conversation`, `answer_training`, `english_improvement`.
- Completed `backend_spec.md` and `handoff.md`.

## Artifact Index
- `backend_spec.md` — Authoritative backend API specification and data contracts.
- `handoff.md` — Self-contained 5-component handoff report.
- `progress.md` — Liveness and status heartbeat.
- `DISPATCH.md` — Record of assignment.

## Loaded Skills
- None
