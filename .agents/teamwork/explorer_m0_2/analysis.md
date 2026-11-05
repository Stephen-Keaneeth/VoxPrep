# Analysis Report: FastAPI Application Architecture & Test Harness (Milestone 0)

**Agent:** `explorer_m0_2`  
**Working Directory:** `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m0_2`  
**Mission:** Design FastAPI application structure, CORS configuration, health and root endpoints, and test harness for Milestone 0.  
**Target Recipient:** Worker Agent & Parent Orchestrator (`f8724849-4618-4264-8e42-f39ec432b779`)  
**Date:** 2026-11-05  

---

## 1. Executive Summary & Problem Boundary

In Milestone 0 (Phase 0: Project Initialization, Environment, and Setup), Member A is establishing the core backend skeleton for VOXPREP. This report provides the architectural design, exact source code specifications, and test fixtures for:
1. `backend/app/main.py`: The entry point FastAPI application, configured with title `"VOXPREP Backend API"`, dynamic CORS middleware, and clean modular placeholders for future routers.
2. Endpoint contracts:
   - `GET /health` returning `{"status": "ok"}` with status code `200`.
   - `GET /` returning service metadata, status, and API documentation links with status code `200`.
3. Test layout:
   - `backend/tests/conftest.py` with FastAPI `TestClient` fixture and automated `sys.path` resolution.
   - `backend/tests/test_health.py` validating `GET /health`, `GET /`, CORS preflight/headers, and OpenAPI documentation endpoints.
   - `backend/pytest.ini` enabling frictionless test runs from any working directory.
4. Exact implementation instructions and verification steps for the Worker.

---

## 2. FastAPI Application Initialization (`backend/app/main.py`)

### 2.1 Design Objectives
- **Title & Metadata**: App title must be strictly `"VOXPREP Backend API"`. Include concise description and versioning (`0.1.0`).
- **CORS Middleware**: Must support:
  - Local development flexibility (`["*"]`).
  - Production configurability via `ALLOWED_ORIGINS` (or `CORS_ORIGINS`) environment variable.
  - Graceful fallback to `["http://localhost:3000"]` if empty or invalid.
  - `allow_credentials=True`.
  - `allow_methods=["*"]`.
  - `allow_headers=["*"]`.
- **Router Scaffolding**: Provide structured placeholders for Milestones 1–3 routers (`auth`, `voice`, `interview`, `coach`) without introducing premature import errors before those modules exist.
- **Standalone Execution**: Include `if __name__ == "__main__":` block to enable `python backend/app/main.py` execution directly.

### 2.2 Starlette / FastAPI CORS Specification Nuance
Under the W3C CORS specification and Starlette's `CORSMiddleware`:
- When `allow_credentials=True` is combined with wildcard `allow_origins=["*"]`, Starlette does **not** return `Access-Control-Allow-Origin: *` (as browsers reject credentialed requests with a wildcard origin).
- Instead, Starlette dynamically reflects the incoming request's `Origin` header into `Access-Control-Allow-Origin` while adding `Vary: Origin` and `Access-Control-Allow-Credentials: true`.
- If an incoming request does not carry an `Origin` header (e.g. server-to-server or direct tool requests), Starlette simply passes the response through without adding CORS headers.
- When `ALLOWED_ORIGINS` contains explicit URLs (e.g., `http://localhost:3000,http://127.0.0.1:3000`), Starlette validates incoming origins against that whitelist.

### 2.3 Proposed Implementation: `backend/app/main.py`

```python
"""
VOXPREP Backend API - Main Application Entrypoint
Milestone 0: Phase 0 Setup & Environment
"""

import os
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def get_allowed_origins() -> List[str]:
    """
    Parses allowed CORS origins from environment variables.
    Checks ALLOWED_ORIGINS first, then CORS_ORIGINS as fallback.
    - If set to a comma-separated list of URLs, splits and strips whitespace.
    - If set to "*", returns ["*"] for wildcard access.
    - If set to empty string, falls back to ["http://localhost:3000"].
    - If unset in environment, defaults to ["*"] for development convenience.
    """
    raw_origins = os.getenv("ALLOWED_ORIGINS") or os.getenv("CORS_ORIGINS")
    if raw_origins is not None:
        origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
        if origins:
            return origins
        return ["http://localhost:3000"]
    return ["*"]


# Initialize FastAPI application with project metadata
app = FastAPI(
    title="VOXPREP Backend API",
    description="Backend API for VOXPREP - AI-powered voice interview and communication coaching platform.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS Middleware
allowed_origins = get_allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", status_code=200, tags=["Health"])
async def health_check():
    """
    Health check endpoint returning service uptime and operational status.
    Required by Acceptance Criteria: returns HTTP 200 with {"status": "ok"}.
    """
    return {"status": "ok"}


@app.get("/", status_code=200, tags=["Root"])
async def root():
    """
    Root endpoint providing service metadata, health status, and API documentation links.
    """
    return {
        "title": "VOXPREP Backend API",
        "version": "0.1.0",
        "status": "online",
        "docs_url": "/docs",
        "health_check": "/health",
    }


# =============================================================================
# Router Mount Points (Milestones 1–3)
# =============================================================================
# As routers are implemented in subsequent milestones, they will be registered here:
# from app.routers import auth, voice, interview, coach
# app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
# app.include_router(voice.router, prefix="/voice", tags=["Voice Pipeline"])
# app.include_router(interview.router, prefix="/interview", tags=["Interviewer Agent"])
# app.include_router(coach.router, prefix="/coach", tags=["Coach Agent"])


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
```

---

## 3. Test Harness Design

### 3.1 Sys.Path Resolution Strategy
A common pain point in Python and FastAPI test suites is running `pytest` from different directories (e.g., repository root `d:\...\AI-Interviewer` vs `backend/`). If `backend` is not installed as an editable wheel or added to `PYTHONPATH`, executing `pytest backend/tests` causes `ModuleNotFoundError: No module named 'app'`.

To eliminate this friction permanently:
1. `backend/tests/conftest.py` dynamically computes the parent directory (`backend/`) and inserts it at `sys.path[0]` before importing `app.main`.
2. A `backend/pytest.ini` is provided specifying `testpaths = tests` and `pythonpath = .`.

### 3.2 Proposed Implementation: `backend/tests/conftest.py`

```python
"""
Pytest configuration and shared fixtures for VOXPREP Backend API.
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure the backend directory is in sys.path regardless of execution working directory
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app  # noqa: E402


@pytest.fixture(scope="function")
def client():
    """
    Provides a FastAPI TestClient instance scoped per test function.
    Uses context manager to ensure startup and shutdown event lifecycles are executed.
    """
    with TestClient(app) as test_client:
        yield test_client
```

### 3.3 Proposed Implementation: `backend/tests/test_health.py`

```python
"""
Unit tests for VOXPREP Backend health endpoint, root metadata, and CORS middleware.
"""

def test_health_check_returns_ok(client):
    """
    Verify GET /health returns HTTP 200 with exact payload {"status": "ok"}.
    Satisfies Phase 0 Acceptance Criteria.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "application/json" in response.headers.get("content-type", "")


def test_root_endpoint_metadata(client):
    """
    Verify GET / returns HTTP 200 with service metadata and documentation links.
    """
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data.get("title") == "VOXPREP Backend API"
    assert data.get("version") == "0.1.0"
    assert data.get("status") == "online"
    assert data.get("docs_url") == "/docs"
    assert data.get("health_check") == "/health"


def test_cors_headers_with_origin(client):
    """
    Verify that requests containing an Origin header receive appropriate CORS response headers.
    """
    test_origin = "http://localhost:3000"
    response = client.get("/health", headers={"Origin": test_origin})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    # Verify CORS allow origin matches requested origin (or wildcard)
    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin in [test_origin, "*"]
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_options(client):
    """
    Verify CORS preflight (OPTIONS) request succeeds with valid headers.
    """
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Content-Type",
    }
    response = client.options("/health", headers=headers)
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers


def test_openapi_documentation_accessible(client):
    """
    Verify OpenAPI schema and Swagger UI documentation endpoints are accessible.
    """
    docs_response = client.get("/docs")
    assert docs_response.status_code == 200

    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == 200
    schema = openapi_response.json()
    assert schema.get("info", {}).get("title") == "VOXPREP Backend API"
    assert "/health" in schema.get("paths", {})
```

### 3.4 Proposed Implementation: `backend/pytest.ini`

```ini
[pytest]
testpaths = tests
pythonpath = .
asyncio_mode = auto
filterwarnings =
    ignore::DeprecationWarning
```

---

## 4. Directory & Package Scaffolding

Per `PROJECT.md` and `docs/02_TECH_STACK.md`, the backend code layout must be structured as follows:

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── db/
│   │   └── __init__.py
│   ├── services/
│   │   └── __init__.py
│   ├── agents/
│   │   └── __init__.py
│   ├── models/
│   │   └── __init__.py
│   └── routers/
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_health.py
├── pytest.ini
├── requirements.txt         (Assigned to explorer_m0_1)
├── .env.example             (Assigned to explorer_m0_1)
└── schema.sql               (Assigned to explorer_m0_3)
```

The Worker should create empty `__init__.py` files in each sub-package so that Python treats them as formal packages and IDE/linters resolve imports cleanly.

---

## 5. Worker Implementation Steps

When the Worker executes Milestone 0, follow this precise sequence:

### Step 1: Initialize Directory Scaffolding and `__init__.py` files
Create the required directory hierarchy and empty `__init__.py` files:
```powershell
New-Item -ItemType Directory -Force -Path "backend/app/db"
New-Item -ItemType Directory -Force -Path "backend/app/services"
New-Item -ItemType Directory -Force -Path "backend/app/agents"
New-Item -ItemType Directory -Force -Path "backend/app/models"
New-Item -ItemType Directory -Force -Path "backend/app/routers"
New-Item -ItemType Directory -Force -Path "backend/tests"

New-Item -ItemType File -Force -Path "backend/app/__init__.py"
New-Item -ItemType File -Force -Path "backend/app/db/__init__.py"
New-Item -ItemType File -Force -Path "backend/app/services/__init__.py"
New-Item -ItemType File -Force -Path "backend/app/agents/__init__.py"
New-Item -ItemType File -Force -Path "backend/app/models/__init__.py"
New-Item -ItemType File -Force -Path "backend/app/routers/__init__.py"
New-Item -ItemType File -Force -Path "backend/tests/__init__.py"
```

### Step 2: Create `backend/app/main.py`
Write the complete FastAPI application code as detailed in Section 2.3.

### Step 3: Create `backend/pytest.ini`
Write the pytest configuration file as detailed in Section 3.4.

### Step 4: Create `backend/tests/conftest.py`
Write the shared pytest fixtures and `sys.path` configuration as detailed in Section 3.2.

### Step 5: Create `backend/tests/test_health.py`
Write the comprehensive test suite as detailed in Section 3.3.

### Step 6: Execute Automated Test Harness
Run the test suite using the virtual environment pytest:
```powershell
.\.venv\Scripts\pytest -v backend/tests
```
Confirm all 5 tests pass:
- `test_health_check_returns_ok` -> PASSED
- `test_root_endpoint_metadata` -> PASSED
- `test_cors_headers_with_origin` -> PASSED
- `test_cors_preflight_options` -> PASSED
- `test_openapi_documentation_accessible` -> PASSED

### Step 7: Verify Uvicorn Local Startup
Test starting the FastAPI server briefly or verify with:
```powershell
.\.venv\Scripts\python -c "import uvicorn; from backend.app.main import app; print('App loaded successfully')"
```

---

## 6. Synthesis and Conflict Resolution

1. **CORS Origins Naming**:
   - `ORIGINAL_REQUEST.md` specifies `ALLOWED_ORIGINS`.
   - `explorer_survey_3` used `CORS_ORIGINS`.
   - **Resolution**: `get_allowed_origins()` explicitly checks `ALLOWED_ORIGINS` first, falling back to `CORS_ORIGINS`. Both conventions work seamlessly.
2. **Wildcard Origin vs Credentials**:
   - `allow_credentials=True` with `allow_origins=["*"]` is supported by Starlette via dynamic origin reflection. Our test suite includes a test specifically verifying that providing an `Origin` header returns matching CORS headers.
3. **Execution Path Agnosticism**:
   - Pytest can be run from either `.venv\Scripts\pytest backend/tests` (root) or `cd backend && pytest`. With `conftest.py`'s `sys.path` injection and `pytest.ini`'s `pythonpath = .`, both execution contexts work without configuration errors.
