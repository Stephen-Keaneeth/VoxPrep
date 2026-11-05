# Test Harness & Adversarial Suite Investigation & Design Report

**Author**: Explorer Agent (`explorer_m0_iter2_3`)  
**Date**: 2026-11-05  
**Working Directory**: `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m0_iter2_3`  
**Milestone**: Milestone 0 — Iteration 2 Gate Check Resolution  

---

## 1. Executive Summary

During Milestone 0 Iteration 1 gate check, running tests via pytest hung indefinitely when collecting or executing `backend/tests/e2e/conftest.py`. Concurrently, executing the adversarial test suite (`backend/tests/test_adversarial_m0.py`) revealed 5 failing tests exposing edge-case bugs in `app/main.py` and `app/db/supabase.py`.

This investigation has:
1. **Isolated the Exact Root Cause of the TestClient Hang**: Starlette's `TestClient` initializes an AnyIO `BlockingPortal` using `socket.socketpair()`. In Windows sandboxed environments, loopback socket creation/handshakes block indefinitely without elevated permissions. Empirical verification confirmed that `socket.socketpair()` deadlocks the process.
2. **Identified Missing Capabilities in `LocalClient`**: While `LocalClient` in `backend/tests/conftest.py` executes ASGI coroutines directly and fast (0.05s) without network sockets, it lacked two features required by the E2E test suite:
   - URL query-string partitioning (`path.partition("?")`), causing parameterized GET requests to 404.
   - Multipart form-data encoding (`files=` parameter), causing audio upload tests (`POST /voice/process`) to crash with `TypeError`.
   - In addition, route handlers in `_build_reference_fallback_app()` were declared as synchronous `def` instead of `async def`, which caused FastAPI to invoke `anyio.to_thread.run_sync()`, triggering `NoEventLoopError`.
3. **Diagnosed All 5 Failures in `backend/tests/test_adversarial_m0.py`**:
   - `test_get_allowed_origins_empty_string_fallback`: `main.py` treated empty string `""` as falsy in `or` expressions, falling back to wildcard `["*"]` instead of contract default `["http://localhost:3000"]`.
   - `test_get_supabase_client_thread_safety`: `app/db/supabase.py` lacked thread locking in `get_supabase_client()`, spawning multiple client instances under concurrent race conditions.
   - `test_mock_query_chaining_update_order_behavior`: `MockTableQuery.update()` mutated store rows immediately upon method call rather than deferring to `execute()`, causing updates before `.eq()` filtering to overwrite unrelated rows.
   - `test_mock_query_insert_none_handling` & `test_mock_query_insert_primitive_handling`: `MockTableQuery.execute()` assumed all store rows are dictionaries and called `r.get()`, raising `AttributeError` when `None` or integers were inserted.
4. **Formulated the Complete Production & Harness Blueprints and Verification Sequences** for Worker implementation.

---

## 2. Root Cause Analysis

### 2.1 The Starlette `TestClient` Sandbox Hang
When `fastapi.testclient.TestClient` is instantiated, it relies on Starlette's `TestClient` implementation:
```
TestClient.__enter__()
  -> starlette.testclient._ASGIAdapter
    -> anyio.from_thread.start_blocking_portal()
      -> asyncio.new_event_loop() / asyncio.get_event_loop()
        -> asyncio.WindowsProactorEventLoopPolicy
          -> socket.socketpair()
```
**Empirical Verification**:
Running `python -c "import socket; s1, s2 = socket.socketpair()"` in the active sandbox environment blocks indefinitely until killed. Because the Windows sandbox restricts loopback IPC sockets, any test relying on Starlette's `TestClient` deadlocks the test runner.

### 2.2 Why `LocalClient` Works & What It Lacked
`LocalClient` (in `backend/tests/conftest.py`) completely bypasses network sockets and thread portals. It directly drives the ASGI application coroutine:
```python
coro = self.app(scope, receive, send)
stack = [coro]
while stack:
    current = stack[-1]
    try:
        sub = current.send(None)
        if hasattr(sub, "send"):
            stack.append(sub)
    except StopIteration:
        stack.pop()
```
However, to serve as the unified in-process test client for the entire project (unit, adversarial, and E2E suites), `LocalClient` requires three extensions:
1. **Query-String Partitioning**:
   - *Current bug*: `scope["path"] = path`, `scope["query_string"] = b""`.
   - *Result*: A request to `client.get("/health?item=1")` sets `scope["path"] = "/health?item=1"`, which Starlette's routing fails to match, returning HTTP 404.
   - *Fix*: Partition `path` into `path_part, _, query_part = path.partition("?")`. Set `scope["path"] = path_part`, `scope["query_string"] = query_part.encode("latin1")`.
2. **Multipart Form-Data Encoding (`files=`)**:
   - *Current bug*: `LocalClient.post` only accepts `(self, path, json=None, data=None, headers=None)`.
   - *Result*: E2E audio tests calling `client.post("/voice/process", files=files, data=form_data)` fail with `TypeError: unexpected keyword argument 'files'`.
   - *Fix*: Implement RFC-compliant multipart form-data boundary generation and body packing for fields and file tuples (`filename`, `bytes`, `content_type`).
3. **Synchronous Handlers in `_build_reference_fallback_app`**:
   - When FastAPI encounters a route handler declared with `def` (sync), it delegates to a thread pool via `anyio.to_thread.run_sync()`. Because no AnyIO event loop is running under `LocalClient`, this raises `anyio.NoEventLoopError`.
   - Declaring all route handlers in `_build_reference_fallback_app()` as `async def` allows FastAPI to execute them directly within the coroutine frame without thread pools.

---

## 3. Review of `backend/tests/test_adversarial_m0.py` Failures

Executing `pytest backend/tests/test_adversarial_m0.py` yielded **19 passed, 5 failed**:

### Failure 1: CORS Allowed Origins Empty String Fallback
- **Test**: `TestFastAPICorsAndHttp.test_get_allowed_origins_empty_string_fallback`
- **Location**: `backend/app/main.py:21`
- **Error**: `AssertionError: Expected fallback ['http://localhost:3000'] but got ['*'].`
- **Mechanism**:
  ```python
  raw_origins = os.getenv("ALLOWED_ORIGINS") or os.getenv("CORS_ORIGINS")
  ```
  When `ALLOWED_ORIGINS=""`, Python treats `""` as falsy. Therefore, `"" or os.getenv(...)` evaluates to `None` if `CORS_ORIGINS` is unset. Then `if raw_origins is not None:` evaluates to `False`, dropping into `return ["*"]`.
- **Contract**: Per docstring and specification:
  - If unset: `["*"]`
  - If set to `""`: fallback to `["http://localhost:3000"]`
- **Fix**: Check `os.getenv("ALLOWED_ORIGINS")` first; only fall back to `os.getenv("CORS_ORIGINS")` if the former is strictly `None`.

### Failure 2: Supabase Singleton Race Condition
- **Test**: `TestSupabaseClientAndMock.test_get_supabase_client_thread_safety`
- **Location**: `backend/app/db/supabase.py:133`
- **Error**: `AssertionError: Singleton race condition detected! 2 distinct instances created across 30 concurrent threads. get_supabase_client() lacks thread locking.`
- **Mechanism**:
  ```python
  if _client_instance is not None:
      return _client_instance
  # Multiple threads pass this check simultaneously and instantiate distinct clients
  _client_instance = MockSupabaseClient()
  return _client_instance
  ```
- **Fix**: Implement thread synchronization via `threading.Lock()` with double-checked locking:
  ```python
  _client_lock = threading.Lock()
  ...
  if _client_instance is not None:
      return _client_instance
  with _client_lock:
      if _client_instance is not None:
          return _client_instance
      # initialization
  ```

### Failure 3: Mock Query Chaining Overwriting Unrelated Rows
- **Test**: `TestSupabaseClientAndMock.test_mock_query_chaining_update_order_behavior`
- **Location**: `backend/app/db/supabase.py:41`
- **Error**: `AssertionError: MockTableQuery.update().eq() overwrote unrelated row user-A! Name is 'Updated Bob'.`
- **Mechanism**:
  In `MockTableQuery.update(data)`:
  ```python
  for row in rows:
      if self._filter_col is None or row.get(self._filter_col) == self._filter_val:
          row.update(data)
  ```
  PostgREST query chaining syntax is `client.table("users").update(data).eq("id", target).execute()`. Because `.update()` is invoked before `.eq()`, `self._filter_col` is `None` during `.update()`, mutating *every* record in the table immediately.
- **Fix**: Store `self._update_data = data` in `update()` and defer mutation to `execute()`, where filters have already been registered.

### Failures 4 & 5: Mock Query Crashing on `None` and Primitive Store Entries
- **Tests**: `test_mock_query_insert_none_handling` and `test_mock_query_insert_primitive_handling`
- **Location**: `backend/app/db/supabase.py:67`
- **Error**: `AttributeError: 'NoneType' object has no attribute 'get'` / `'int' object has no attribute 'get'`.
- **Mechanism**:
  `rows = [r for r in rows if r.get(self._filter_col) == self._filter_val]`
  When non-dictionary entries exist in `self.store`, invoking `.get()` causes an unhandled exception.
- **Fix**:
  Guard with `isinstance(r, dict)` before calling `r.get(self._filter_col)`.

---

## 4. Detailed Component Design & Blueprints

### Blueprint 1: Upgraded `LocalClient` in `backend/tests/conftest.py`
To provide a rock-solid, socket-free test harness for all unit, adversarial, and E2E tests:

```python
import json
import os
import sys
import uuid
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import pytest

# Ensure backend/ and repo root are in sys.path
backend_dir = Path(__file__).resolve().parent.parent
repo_dir = backend_dir.parent

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(repo_dir) not in sys.path:
    sys.path.insert(0, str(repo_dir))

from app.main import app


class CaseInsensitiveDict(dict):
    """Case-insensitive dictionary for HTTP headers."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        for k, v in dict(*args, **kwargs).items():
            self[k] = v

    def __setitem__(self, key, value):
        super().__setitem__(key.lower() if isinstance(key, str) else key, value)

    def __getitem__(self, key):
        return super().__getitem__(key.lower() if isinstance(key, str) else key)

    def __contains__(self, key):
        return super().__contains__(key.lower() if isinstance(key, str) else key)

    def get(self, key, default=None):
        return super().get(key.lower() if isinstance(key, str) else key, default)


class LocalResponse:
    """Synchronous HTTP response wrapper returned by LocalClient."""

    def __init__(self, status_code: int, raw_headers: List[tuple], body: bytes):
        self.status_code = status_code
        self.headers = CaseInsensitiveDict({
            k.decode("latin1"): v.decode("latin1") for k, v in raw_headers
        })
        self.content = body
        self.text = body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


class LocalClient:
    """In-memory ASGI test client that directly drives the application coroutine.

    Operates without thread portals or loopback network sockets, making it
    completely immune to sandbox socket restrictions while preserving full
    ASGI lifecycle and middleware behavior.
    """

    def __init__(self, asgi_app: Any):
        self.app = asgi_app

    def __enter__(self) -> "LocalClient":
        return self

    def __exit__(self, *args) -> None:
        pass

    @staticmethod
    def _encode_multipart(
        fields: Optional[Dict[str, Any]],
        files: Optional[Dict[str, Any]],
    ) -> Tuple[bytes, str]:
        """Encodes form fields and files into multipart/form-data payload."""
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        body = bytearray()
        quote = '"'

        if fields:
            for name, val in fields.items():
                body.extend(f"--{boundary}\r\n".encode("utf-8"))
                body.extend(f"Content-Disposition: form-data; name={quote}{name}{quote}\r\n\r\n".encode("utf-8"))
                body.extend(str(val).encode("utf-8"))
                body.extend(b"\r\n")

        if files:
            for name, file_spec in files.items():
                if isinstance(file_spec, tuple):
                    filename = file_spec[0]
                    file_content = file_spec[1]
                    content_type = file_spec[2] if len(file_spec) > 2 else "application/octet-stream"
                else:
                    filename = getattr(file_spec, "name", "upload.bin")
                    file_content = getattr(file_spec, "read", lambda: file_spec)()
                    content_type = "application/octet-stream"

                if isinstance(file_content, str):
                    file_content = file_content.encode("utf-8")

                body.extend(f"--{boundary}\r\n".encode("utf-8"))
                body.extend(
                    f"Content-Disposition: form-data; name={quote}{name}{quote}; filename={quote}{filename}{quote}\r\n".encode("utf-8")
                )
                body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
                body.extend(file_content)
                body.extend(b"\r\n")

        body.extend(f"--{boundary}--\r\n".encode("utf-8"))
        return bytes(body), f"multipart/form-data; boundary={boundary}"

    def request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        body: bytes = b"",
    ) -> LocalResponse:
        path_part, _, query_part = path.partition("?")
        hdrs = [
            (k.lower().encode("latin1"), v.encode("latin1"))
            for k, v in (headers or {}).items()
        ]
        raw_headers = [(b"host", b"testserver")] + hdrs
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method.upper(),
            "path": path_part,
            "raw_path": path_part.encode("latin1"),
            "query_string": query_part.encode("latin1"),
            "headers": raw_headers,
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
        messages: List[Dict[str, Any]] = []

        async def receive() -> Dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(msg: Dict[str, Any]) -> None:
            messages.append(msg)

        coro = self.app(scope, receive, send)

        # Drive coroutine stack to completion
        stack = [coro]
        while stack:
            current = stack[-1]
            try:
                sub = current.send(None)
                if hasattr(sub, "send"):
                    stack.append(sub)
            except StopIteration:
                stack.pop()

        status_code = 200
        resp_headers: List[tuple] = []
        body_chunks: List[bytes] = []

        for msg in messages:
            if msg["type"] == "http.response.start":
                status_code = msg["status"]
                resp_headers = msg.get("headers", [])
            elif msg["type"] == "http.response.body":
                body_chunks.append(msg.get("body", b""))

        return LocalResponse(status_code, resp_headers, b"".join(body_chunks))

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> LocalResponse:
        if params:
            qs = urllib.parse.urlencode(params)
            sep = "&" if "?" in path else "?"
            path = f"{path}{sep}{qs}"
        return self.request("GET", path, headers=headers)

    def options(self, path: str, headers: Optional[Dict[str, str]] = None) -> LocalResponse:
        return self.request("OPTIONS", path, headers=headers)

    def post(
        self,
        path: str,
        json: Any = None,
        data: Any = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> LocalResponse:
        body = b""
        req_headers = dict(headers or {})

        if files is not None:
            fields = data if isinstance(data, dict) else {}
            body, content_type = self._encode_multipart(fields, files)
            req_headers.setdefault("content-type", content_type)
        elif json is not None:
            body = json.dumps(json).encode("utf-8")
            req_headers.setdefault("content-type", "application/json")
        elif isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode("utf-8")
            req_headers.setdefault("content-type", "application/x-www-form-urlencoded")
        elif isinstance(data, (bytes, bytearray)):
            body = bytes(data)
        elif isinstance(data, str):
            body = data.encode("utf-8")

        return self.request("POST", path, headers=req_headers, body=body)

    def put(
        self,
        path: str,
        json: Any = None,
        data: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> LocalResponse:
        req_headers = dict(headers or {})
        body = b""
        if json is not None:
            body = json.dumps(json).encode("utf-8")
            req_headers.setdefault("content-type", "application/json")
        elif isinstance(data, (bytes, bytearray)):
            body = bytes(data)
        elif isinstance(data, str):
            body = data.encode("utf-8")
        return self.request("PUT", path, headers=req_headers, body=body)

    def delete(self, path: str, headers: Optional[Dict[str, str]] = None) -> LocalResponse:
        return self.request("DELETE", path, headers=headers)
```

---

### Blueprint 2: `backend/tests/e2e/conftest.py` Modifications
1. **Declare route functions in `_build_reference_fallback_app()` as `async def`**:
   - `async def health_check():`
   - `async def root():`
   - `async def register(req: RegisterRequest):`
   - `async def login(req: LoginRequest):`
   - `async def start_interview(req: InterviewStartRequest):`
   - `async def respond_interview(req: InterviewRespondRequest):`
   - `async def end_interview(req: InterviewEndRequest):`
   - `async def get_interview_report(session_id: str):`
   - `async def start_coach(req: CoachStartRequest):`
   - `async def respond_coach(req: CoachRespondRequest):`
   - `async def end_coach(req: CoachEndRequest):`
2. **Update `app_instance` fixture**:
   ```python
   @pytest.fixture(scope="session")
   def app_instance():
       """Resolves either the implemented backend.app.main app or the reference mock fallback."""
       app_candidate = None
       try:
           from app.main import app as real_app
           app_candidate = real_app
       except Exception:
           try:
               from backend.app.main import app as real_app
               app_candidate = real_app
           except Exception:
               pass

       if app_candidate is not None:
           route_paths = {getattr(r, "path", "") for r in getattr(app_candidate, "routes", [])}
           # If all routers are mounted, use real_app
           if "/auth/register" in route_paths or "/interview/start" in route_paths:
               return app_candidate

       return _build_reference_fallback_app()
   ```
3. **Update `client` fixture**:
   ```python
   from tests.conftest import LocalClient

   @pytest.fixture
   def client(app_instance) -> Generator:
       """Provides an HTTP client for opaque-box E2E testing.
       
       If `BASE_URL` is configured in the environment, runs real HTTP requests against the live server.
       Otherwise, runs in-process via LocalClient to avoid Windows sandbox socketpair restrictions.
       """
       base_url = os.getenv("BASE_URL")
       if base_url:
           import httpx
           with httpx.Client(base_url=base_url, timeout=30.0) as http_client:
               yield http_client
       else:
           with LocalClient(app_instance) as local_client:
               yield local_client
   ```

---

### Blueprint 3: `backend/app/main.py` Fix
Replace lines 21-27 with:
```python
    raw_origins = os.getenv("ALLOWED_ORIGINS")
    if raw_origins is None:
        raw_origins = os.getenv("CORS_ORIGINS")
    if raw_origins is not None:
        origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
        if origins:
            return origins
        return ["http://localhost:3000"]
    return ["*"]
```

---

### Blueprint 4: `backend/app/db/supabase.py` Fixes
1. **Thread-safe double-checked locking**:
   ```python
   import threading

   _client_lock = threading.Lock()
   _client_instance: Optional[Any] = None

   def get_supabase_client() -> Any:
       """Returns singleton Supabase client or mock fallback if credentials are absent."""
       global _client_instance
       if _client_instance is not None:
           return _client_instance

       with _client_lock:
           if _client_instance is not None:
               return _client_instance

           url = os.getenv("SUPABASE_URL", "").strip()
           key = os.getenv("SUPABASE_SERVICE_KEY", "").strip() or os.getenv("SUPABASE_ANON_KEY", "").strip()

           is_dummy = (
               not url
               or not key
               or "placeholder" in url.lower()
               or "your-" in url.lower()
               or "your_" in url.lower()
               or "example" in url.lower()
           )

           if is_dummy:
               logger.warning("Supabase credentials not configured or placeholder. Initializing MockSupabaseClient.")
               _client_instance = MockSupabaseClient()
               return _client_instance

           try:
               from supabase import create_client
               _client_instance = create_client(url, key)
               logger.info("Supabase client successfully initialized.")
               return _client_instance
           except Exception as exc:
               logger.error(f"Failed to initialize live Supabase client: {exc}. Falling back to MockSupabaseClient.")
               _client_instance = MockSupabaseClient()
               return _client_instance
   ```
2. **`MockTableQuery` deferred update mutation and safe type checking**:
   ```python
   class MockTableQuery:
       """In-memory mock query builder for offline tests and development."""

       def __init__(self, table_name: str, store: Dict[str, List[Dict[str, Any]]]):
           self.table_name = table_name
           self.store = store
           self._filter_col: Optional[str] = None
           self._filter_val: Any = None
           self._is_single = False
           self._last_result: Any = None
           self._update_data: Optional[Dict[str, Any]] = None

       def select(self, *args, **kwargs) -> "MockTableQuery":
           return self

       def insert(self, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> "MockTableQuery":
           if data is None:
               self.store.setdefault(self.table_name, []).append(None)
               self._last_result = [None]
           elif isinstance(data, list):
               self.store.setdefault(self.table_name, []).extend(data)
               self._last_result = data
           else:
               self.store.setdefault(self.table_name, []).append(data)
               self._last_result = [data]
           return self

       def update(self, data: Dict[str, Any]) -> "MockTableQuery":
           self._update_data = data
           return self

       def eq(self, column: str, value: Any) -> "MockTableQuery":
           self._filter_col = column
           self._filter_val = value
           return self

       def single(self) -> "MockTableQuery":
           self._is_single = True
           return self

       def execute(self) -> Any:
           class MockResponse:
               def __init__(self, data: Any):
                   self.data = data

           rows = self.store.get(self.table_name, [])
           if self._filter_col:
               rows = [
                   r for r in rows
                   if isinstance(r, dict) and r.get(self._filter_col) == self._filter_val
               ]

           if self._update_data is not None:
               for r in rows:
                   if isinstance(r, dict):
                       r.update(self._update_data)
               result = rows
               if self._is_single:
                   result = rows[0] if rows else None
               return MockResponse(result)

           if self._is_single:
               result = rows[0] if rows else None
           else:
               result = getattr(self, "_last_result", None)
               if result is None:
                   result = rows
           return MockResponse(result)
   ```

---

## 5. Verification Command Sequence for Worker

Worker must execute the following commands sequentially using PowerShell:

```powershell
# 1. Verify Virtual Environment Python & Pytest
& ".venv\Scripts\python.exe" --version
& ".venv\Scripts\python.exe" -m pytest --version

# 2. Run Unit Tests (Health & Root Endpoints)
& ".venv\Scripts\python.exe" -m pytest backend/tests/test_health.py -v

# 3. Run Database Schema & Supabase Client Tests
& ".venv\Scripts\python.exe" -m pytest backend/tests/test_db_schema.py -v

# 4. Run Adversarial Milestone 0 Test Suite (24 tests)
& ".venv\Scripts\python.exe" -m pytest backend/tests/test_adversarial_m0.py -v

# 5. Run Tier 1 Isolated Feature Coverage E2E Tests (11 tests)
& ".venv\Scripts\python.exe" -m pytest backend/tests/e2e/test_tier1_features.py -v

# 6. Run Tier 2 Boundary & Corner Cases E2E Tests (11 tests)
& ".venv\Scripts\python.exe" -m pytest backend/tests/e2e/test_tier2_boundaries.py -v

# 7. Run Tier 3 Pairwise Integration E2E Tests (3 tests)
& ".venv\Scripts\python.exe" -m pytest backend/tests/e2e/test_tier3_pairwise.py -v

# 8. Run Tier 4 Complex Scenarios E2E Tests (3 tests)
& ".venv\Scripts\python.exe" -m pytest backend/tests/e2e/test_tier4_scenarios.py -v

# 9. Run Comprehensive Test Suite Across Entire Project (all 63 tests)
& ".venv\Scripts\python.exe" -m pytest backend/tests/ -v
```

**Expected Result**:
- All 63 tests pass with 0 failures, 0 errors, and 0 hangs in under 5 seconds.
