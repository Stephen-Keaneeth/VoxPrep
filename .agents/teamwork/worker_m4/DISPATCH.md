## 2026-11-05T22:41:24Z

You are `worker_m4`, the Milestone 4 Implementation Worker.
Working directory: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\worker_m4
Project root: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer
Original request: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\PROJECT.md

Read the 3 Explorer blueprints before beginning:
- Explorer 1 (Global Error Handling): `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m4_1\handoff.md` (and `proposed_main.py`, `proposed_test_errors.py`)
- Explorer 2 (Backend Documentation & API Contract): `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m4_2\handoff.md` (and `blueprint_backend_README.md`, `blueprint_root_README.md`)
- Explorer 3 (Containerization & Deployment): `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m4_3\handoff.md`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your exclusive write ownership covers:
- `backend/app/main.py`
- `backend/tests/test_errors.py`
- `README.md`
- `backend/README.md`
- `Dockerfile` & `backend/Dockerfile`
- `railway.json` & `backend/railway.json`
- `Procfile` & `backend/Procfile`
- `.dockerignore` & `backend/.dockerignore`

Implementation requirements:
1. Global Error Handling in `backend/app/main.py`:
   - Apply the pure ASGI middleware and exception handlers designed by `explorer_m4_1` (`StarletteHTTPException`, `RequestValidationError`, `GlobalExceptionMiddleware`, `Exception`).
   - Format: `{"detail": ..., "error_type": "...", "status_code": ...}` preserving CORS headers and existing test compatibility.
2. Error Handling Tests:
   - Create `backend/tests/test_errors.py` (10 tests) verifying 400, 404, 422, 500, CORS header preservation, and backward compatibility using `LocalClient` and `run_sync`.
3. Comprehensive Documentation:
   - Apply `blueprint_backend_README.md` to `backend/README.md`.
   - Apply `blueprint_root_README.md` to root `README.md`.
   - Ensure all setup instructions (.venv activation, env vars, run commands, complete API contract with exact request/response shapes and curl examples for Member B) are present.
4. Containerization & Deployment:
   - Create `backend/Dockerfile` and root `Dockerfile` using `python:3.12-slim`, non-root user `appuser`, dynamic `$PORT` support, and `curl` healthcheck.
   - Create `backend/railway.json` and root `railway.json` (builder DOCKERFILE, healthcheck `/health`).
   - Create `backend/Procfile` and root `Procfile` (`web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
   - Create `backend/.dockerignore` and root `.dockerignore`.
5. Testing & Verification:
   - Run `.\.venv\Scripts\pytest.exe backend/tests/test_errors.py -v`
   - Run `.\.venv\Scripts\pytest.exe backend/tests -v`
   - Verify that 100% of tests pass across the entire repository with 0 regressions.
   - Verify production startup locally with uvicorn and confirm `GET /health` returns HTTP 200 `{"status": "ok"}`.
6. Deliver a 5-component handoff report (Observation, Logic Chain, Caveats, Conclusion, Verification Method) to:
   `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\worker_m4\handoff.md`
7. When complete, send a message to the orchestrator.
