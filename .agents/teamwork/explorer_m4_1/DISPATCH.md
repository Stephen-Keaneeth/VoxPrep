## 2026-11-05T22:30:33Z
You are `explorer_m4_1`, the Global Error Handling & Exception Middleware Architect.
Working directory: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m4_1
Project root: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer
Original request: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\PROJECT.md

Your mission is read-only technical investigation and blueprint authoring for Milestone 4 (Phase 4: Production Hardening, Error Handling, and Deployment):
Specifically for Global Error Handling in `backend/app/main.py`:
1. Read `ORIGINAL_REQUEST.md`, `PROJECT.md`, `backend/app/main.py`, and inspect all current routers (`auth.py`, `voice.py`, `interview.py`, `coach.py`).
2. Design custom global exception handlers in `backend/app/main.py`:
   - `RequestValidationError` (HTTP 422): return clean, uniform JSON structure `{"detail": ..., "error_type": "validation_error", "status_code": 422}` while maintaining compatibility with standard FastAPI/Pydantic `detail` expectations in tests.
   - `HTTPException` (HTTP 4xx / 5xx): return uniform JSON structure `{"detail": ..., "error_type": "http_error", "status_code": ...}` without breaking standard Starlette/FastAPI `detail` key access.
   - Generic unhandled `Exception` (HTTP 500): catch all unexpected exceptions, log traceback securely with Python logger, and return clean JSON response `{"detail": "Internal server error occurred.", "error_type": "internal_server_error", "status_code": 500}` — preventing silent crashes, hanging sockets, or raw stack leaks to clients.
   - Verify that all existing 314 tests in `backend/tests` remain 100% passing and do not break assertions expecting `response.json()["detail"]`.
3. Design test scenarios for `backend/tests/test_errors.py` covering:
   - 404 Not Found handling on invalid routes.
   - 422 Unprocessable Entity handling on malformed JSON bodies.
   - 400 Bad Request handling on route validation errors.
   - 500 Internal Server Error handling on unexpected server exceptions.
4. Deliver your complete 5-component handoff report (Observation, Logic Chain, Caveats, Conclusion, Verification Method) to:
   `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m4_1\handoff.md`
5. Send a completion message to parent orchestrator.
Do NOT write code to the codebase directly — you are a read-only explorer.
