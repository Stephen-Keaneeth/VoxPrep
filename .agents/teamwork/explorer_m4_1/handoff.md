# Handoff Report: Global Error Handling & Exception Middleware Architecture

**Agent**: `explorer_m4_1` (Global Error Handling & Exception Middleware Architect)  
**Milestone**: Milestone 4 (Phase 4: Production Hardening, Error Handling, and Deployment)  
**Date**: 2026-11-05T22:35:00Z  
**Target Codebase Paths**:
- `backend/app/main.py`
- `backend/tests/test_errors.py`

---

## 1. Observation

### 1.1 Existing Codebase & Error Surface Analysis
- **`backend/app/main.py` (lines 8–70, 95–110)**:
  Currently initializes `FastAPI(...)`, adds `CORSMiddleware`, defines `/health` and `/`, and mounts routers:
  - `auth.router` (`/auth`)
  - `voice.router` (`/voice`)
  - `interview.router` (`/interview`)
  - `coach.router` (`/coach`)
  No custom exception handlers or error-catching middlewares currently exist on `app`.
- **Router Error Emission**:
  - `backend/app/routers/auth.py`: Raises `fastapi.HTTPException(status_code=400, detail="Invalid email format")`, `HTTPException(400, detail="User already registered with this email")`, and `HTTPException(401, detail="Invalid email or password")`.
  - `backend/app/routers/interview.py`: Raises `fastapi.HTTPException(status_code=404, detail="Interview session not found")` and `HTTPException(status_code=400, detail="Interview session is not yet completed...")`. Validates `interview_type` with Pydantic field validator (emitting HTTP 422).
  - `backend/app/routers/coach.py`: Raises `fastapi.HTTPException(status_code=400, detail="user_id must not be empty")`, `HTTPException(status_code=400, detail="Invalid coach mode...")`, `HTTPException(status_code=404, detail="Coach session not found")`, and `HTTPException(status_code=400, detail="Coach session is already completed.")`.
  - `backend/app/routers/voice.py`: Gracefully intercepts STT/TTS empty/corrupted payloads and returns fallback models without crashing.
- **Existing Test Suite Baseline**:
  Running `.venv\Scripts\pytest -v` executed 314 tests across `backend/tests/`:
  ```
  collected 314 items
  ======================= 314 passed, 1 warning in 2.12s ========================
  ```
  Assertions on error responses across existing tests:
  - Status code checks: `assert res.status_code == 422`, `assert res.status_code in [400, 422]`, `assert resp.status_code == 404`, `assert res.status_code == 400`.
  - `detail` key checks: Exactly 46 occurrences in `backend/tests/` accessing `res.json().get("detail", "")`, `resp.json()["detail"].lower()`, or `assert "detail" in data`.
  - In `backend/tests/test_adversarial_auth.py:96`, `assert detail == "Invalid email or password"`.
  - In `backend/tests/test_adversarial_auth.py:63`, `assert "email" in res.json().get("detail", "").lower()`.
  - In `backend/tests/test_interview.py:331`, `assert "not yet completed" in report_resp.json()["detail"].lower()`.
- **ASGI & Starlette Error Lifecycle Discoveries**:
  - Starlette's `ServerErrorMiddleware` is placed at the outermost layer of the application. In `starlette/middleware/errors.py`:
    ```python
    except Exception as exc:
        ...
        if not response_started:
            await response(scope, receive, send)
        raise exc  # Always re-raises!
    ```
    If an unexpected exception escapes, `ServerErrorMiddleware` calls the 500 handler, sends the HTTP response, and **always re-raises `exc`**.
  - `backend/tests/conftest.py` implements `LocalClient` as an in-memory ASGI driver that advances the coroutine stack using synchronous `coro.send(None)`. If `ServerErrorMiddleware` re-raises `exc`, `LocalClient.request` receives the uncaught exception directly and crashes before reading `http.response.start`.
  - Furthermore, Starlette's `@app.middleware("http")` relies on `starlette.middleware.base.BaseHTTPMiddleware`, which calls `anyio.create_task_group()`. Inside `LocalClient` (which runs without an active event loop), `BaseHTTPMiddleware` fails with `NoEventLoopError: Not currently running on any asynchronous event loop`.
  - In contrast, a **pure ASGI middleware** `class GlobalExceptionMiddleware: async def __call__(self, scope, receive, send): ...` executes synchronously and cooperatively with `LocalClient` and production `uvicorn`, catching all unhandled exceptions, logging the stack trace securely, and sending a clean HTTP 500 response without re-raising.

---

## 2. Logic Chain

1. **Uniform Error Response Schema Definition**:
   To satisfy both Milestone 4 requirements and preserve 100% test compatibility:
   - For `HTTPException` (4xx/5xx):
     ```json
     {
       "detail": "<error message string or data>",
       "error_type": "http_error",
       "status_code": <integer status code>
     }
     ```
   - For `RequestValidationError` (HTTP 422):
     ```json
     {
       "detail": [<pydantic error dictionaries>],
       "error_type": "validation_error",
       "status_code": 422
     }
     ```
   - For Generic Unhandled `Exception` (HTTP 500):
     ```json
     {
       "detail": "Internal server error occurred.",
       "error_type": "internal_server_error",
       "status_code": 500
     }
     ```

2. **Backward Compatibility Preservation**:
   - Because `"detail"` is retained as a top-level key matching exact existing string and list formats, all 46 existing assertions in `backend/tests/` (e.g. `res.json()["detail"]`, `res.json().get("detail")`) continue to evaluate identically without `KeyError` or string manipulation errors.
   - The extra keys `"error_type"` and `"status_code"` supply structured contract guarantees for frontend clients without colliding with any existing assertions.

3. **Exception Routing Architecture**:
   - Registering `@app.exception_handler(StarletteHTTPException)` intercepts both Starlette HTTP exceptions (such as built-in 404 Not Found for non-existent routes and 405 Method Not Allowed) and `fastapi.HTTPException` (since `fastapi.HTTPException` subclasses `StarletteHTTPException`). Any custom headers (such as `WWW-Authenticate` on 401) are preserved via `headers=getattr(exc, "headers", None)`.
   - Registering `@app.exception_handler(RequestValidationError)` intercepts FastAPI/Pydantic validation errors before they reach the router, serializing `exc.errors()` via `jsonable_encoder(...)`.
   - Registering `@app.exception_handler(Exception)` ensures standard FastAPI 500 handling.
   - Implementing `GlobalExceptionMiddleware` at the ASGI layer inside `CORSMiddleware` guarantees that any unexpected exception escaping routers/services is intercepted, logged with `voxprep.errors` (recording full stack trace with `exc_info=True`), and converted into an HTTP 500 JSON response without re-raising out of the ASGI pipeline.
   - By adding `GlobalExceptionMiddleware` after `CORSMiddleware`, Starlette's reverse wrapping puts `CORSMiddleware` on the outside, ensuring CORS headers (`Access-Control-Allow-Origin`) are attached even to HTTP 500 error responses, preventing browser client CORS masking.

4. **Live Validation of Existing Test Suite**:
   When this exact architecture was dynamically mounted to `app` in memory, all 314 tests in `backend/tests/` passed in 1.20s with 0 failures:
   ```
   314 passed, 1 warning in 1.20s
   Pytest exit code with handlers applied: 0
   ```

---

## 3. Caveats

1. **No Direct Code Modifications Performed**:
   In strict accordance with the explorer archetype and read-only protocol, no source files under `backend/app/` or `backend/tests/` were modified. Complete proposed replacement files and unified diff patches have been created in `.agents/teamwork/explorer_m4_1/`.
2. **WebSocket Exceptions**:
   The current application exposes only HTTP REST endpoints (`/auth`, `/voice`, `/interview`, `/coach`, `/health`, `/`). WebSocket endpoints are not part of the MVP scope. If WebSockets are added post-MVP, a dedicated `WebSocketException` handler should be mapped.
3. **Pydantic v2 `jsonable_encoder`**:
   `RequestValidationError.errors()` from Pydantic v2 may contain non-standard objects in error context fields (e.g. `ctx={"error": ValueError(...)}`). Using FastAPI's `jsonable_encoder(exc.errors())` ensures seamless JSON serialization without raising `TypeError: Object of type ValueError is not JSON serializable`.

---

## 4. Conclusion & Concrete Blueprint

### 4.1 Recommended Blueprint for `backend/app/main.py`
Add the following middleware class, registration, and three exception handlers directly to `backend/app/main.py`:

```python
import logging
from typing import List
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("voxprep.errors")

# ... [Keep existing CORS configuration] ...

class GlobalExceptionMiddleware:
    """
    Pure ASGI middleware that catches unhandled exceptions escaping the application,
    logs the stack trace securely, and sends a standardized HTTP 500 JSON response.
    Operates without anyio/event loop dependencies, ensuring flawless operation in
    both local ASGI test clients and production uvicorn ASGI servers.
    """

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.asgi_app(scope, receive, send)
            return

        response_started = False

        async def custom_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.asgi_app(scope, receive, custom_send)
        except Exception as exc:
            logger.error(
                f"Unhandled exception during {scope.get('method', 'UNKNOWN')} {scope.get('path', 'UNKNOWN')}: {exc}",
                exc_info=True,
            )
            if not response_started:
                resp = JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "detail": "Internal server error occurred.",
                        "error_type": "internal_server_error",
                        "status_code": 500,
                    },
                )
                await resp(scope, receive, send)


app.add_middleware(GlobalExceptionMiddleware)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Global handler for HTTP exceptions (4xx / 5xx).
    Returns uniform JSON structure with detail, error_type, and status_code,
    preserving exact detail strings expected by client callers and test suites.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_type": "http_error",
            "status_code": exc.status_code,
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Global handler for Pydantic / FastAPI request validation errors (HTTP 422).
    Returns uniform JSON structure with detail list, error_type, and status_code.
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": jsonable_encoder(exc.errors()),
            "error_type": "validation_error",
            "status_code": 422,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global handler for unexpected internal exceptions (HTTP 500).
    Logs traceback securely and returns clean JSON without leaking stack details.
    """
    logger.error(
        f"Unhandled server exception during {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error occurred.",
            "error_type": "internal_server_error",
            "status_code": 500,
        },
    )
```

### 4.2 Recommended Blueprint for `backend/tests/test_errors.py`
Create `backend/tests/test_errors.py` with 9 comprehensive test scenarios:
1. `test_404_invalid_route_returns_uniform_error(client)`: Checks GET on `/api/v1/nonexistent/endpoint` -> 404, `{"detail": "Not Found", "error_type": "http_error", "status_code": 404}`.
2. `test_404_resource_not_found(client)`: Checks GET on non-existent interview report UUID -> 404, `"not found" in detail.lower()`, `error_type == "http_error"`.
3. `test_422_missing_mandatory_body_fields(client)`: Checks POST `/auth/register` with `{}` -> 422, `isinstance(detail, list)`, `error_type == "validation_error"`.
4. `test_422_field_type_mismatch(client)`: Checks POST `/interview/start` with bad types -> 422, `isinstance(detail, list)`, `error_type == "validation_error"`.
5. `test_400_bad_request_domain_validation(client)`: Checks POST `/auth/register` with malformed email -> 400, `isinstance(detail, str)`, `error_type == "http_error"`.
6. `test_400_coach_empty_user_id(client)`: Checks POST `/coach/start` with whitespace `user_id` -> 400, `"user_id" in detail.lower()`.
7. `test_400_coach_respond_empty_user_text(client)`: Checks POST `/coach/respond` with empty string `user_text` -> 400, `"user_text" in detail.lower()`.
8. `test_500_internal_server_error_sanitization(client)`: Simulates unhandled DB crash with `mock.patch` -> 500, `detail == "Internal server error occurred."`, `error_type == "internal_server_error"`, verifies no raw stack or secret leakage in text.
9. `test_error_response_backward_compatibility_detail_access(client)`: Validates that `res.json()["detail"]` and `res.json().get("detail")` work identically for 400, 404, 422, and 500.
10. `test_cors_headers_present_on_error_responses(client)`: Validates `access-control-allow-origin` is attached to error responses when client requests with `Origin`.

### 4.3 Deliverables Index
- Proposed `backend/app/main.py`:  
  `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m4_1\proposed_main.py`
- Proposed unified diff patch:  
  `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m4_1\proposed_main.patch`
- Proposed `backend/tests/test_errors.py`:  
  `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m4_1\proposed_test_errors.py`

---

## 5. Verification Method

To independently verify this blueprint:
1. **Apply the patch or copy `proposed_main.py` to `backend/app/main.py`**:
   ```powershell
   git apply ".agents/teamwork/explorer_m4_1/proposed_main.patch"
   ```
2. **Add `proposed_test_errors.py` to `backend/tests/test_errors.py`**:
   ```powershell
   Copy-Item ".agents/teamwork/explorer_m4_1/proposed_test_errors.py" -Destination "backend/tests/test_errors.py"
   ```
3. **Execute the full test suite**:
   ```powershell
   .venv\Scripts\pytest -v
   ```
   **Expected Result**: All 324 tests (314 existing + 10 new error tests) PASS with 0 failures and 0 regressions.
4. **Invalidation Conditions**:
   - Any test expecting `response.json()["detail"]` raises `KeyError` or type mismatch.
   - Any unhandled exception leaks Python stack traces or file paths to HTTP response JSON.
   - Any browser request to an error endpoint is blocked by missing CORS headers.
