## 2026-11-05T22:58:04Z
You are `worker_m4_iter2`, the Milestone 4 Iteration 2 Remediation Worker.
Working directory: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\worker_m4_iter2
Project root: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer
Original request: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\PROJECT.md
Reviewer report: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\reviewer_m4_1\handoff.md
Challenger report: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\challenger_m4_1\handoff.md
Deployment reviewer report: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\reviewer_m4_2\handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Context:
In Milestone 4 Gate 1, both `reviewer_m4_1` and `challenger_m4_1` independently isolated an empirical CORS defect on unhandled HTTP 500 errors:
In `backend/app/main.py`, `GlobalExceptionMiddleware` was registered *after* `CORSMiddleware`. Because Starlette's `app.add_middleware` prepends to the middleware stack (`insert(0, ...)`), `GlobalExceptionMiddleware` wrapped outside `CORSMiddleware`. When an unhandled exception occurs, `GlobalExceptionMiddleware` emits a 500 JSONResponse directly, which bypasses `CORSMiddleware` and drops `access-control-allow-origin` and `access-control-allow-credentials`. This caused 3 failures in `backend/tests/test_adversarial_errors.py`.
Additionally, `reviewer_m4_2` noted that root `railway.json` should point to `"Dockerfile"` and `"uvicorn app.main:app --host 0.0.0.0 --port $PORT"` for monorepo root deployments.

Your write ownership:
- `backend/app/main.py`
- `backend/tests/test_errors.py`
- `railway.json`

Your tasks:
1. In `backend/app/main.py`:
   - Adjust the middleware registration order: register `GlobalExceptionMiddleware` BEFORE `CORSMiddleware` so `CORSMiddleware` is added last and becomes the outermost layer.
   - Add defense-in-depth: In `GlobalExceptionMiddleware.__call__`, check `scope.get("headers")` for `b"origin"` or `"origin"`. If present, attach CORS headers directly to the 500 `JSONResponse` (`Access-Control-Allow-Origin: <origin>`, `Access-Control-Allow-Credentials: true`, `Vary: Origin`).
2. In `backend/tests/test_errors.py`:
   - Add a test verifying CORS headers are present on HTTP 500 unhandled errors when an Origin header is sent.
3. In root `railway.json`:
   - Update config to point to `"Dockerfile"` and `"uvicorn app.main:app --host 0.0.0.0 --port $PORT"`.
4. Run verification tests in powershell:
   `.\.venv\Scripts\pytest.exe backend/tests/test_adversarial_errors.py -v`
   `.\.venv\Scripts\pytest.exe backend/tests/test_errors.py -v`
   `.\.venv\Scripts\pytest.exe backend/tests -v`
5. Confirm that all 45 tests in `test_adversarial_errors.py` pass and all tests in `backend/tests` pass with 0 failures and 0 regressions.
6. Deliver a 5-component handoff report (Observation, Logic Chain, Caveats, Conclusion, Verification Method) to:
   `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\worker_m4_iter2\handoff.md`
7. Send a completion message to the parent orchestrator.
