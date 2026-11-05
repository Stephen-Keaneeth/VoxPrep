# Milestone 0 (Phase 0): Virtual Environment & Dependency Installation Analysis

**Author**: `explorer_m0_1`  
**Date**: 2026-11-05  
**Working Directory**: `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m0_1`  
**Target Milestone**: M0 (Phase 0: Project Initialization, Environment, and Setup)

---

## 1. Executive Summary

This report establishes the complete environment and dependency strategy for the VOXPREP Backend MVP on Windows with Python 3.12:
1. **Windows PowerShell Execution Policy**: The host environment's PowerShell ExecutionPolicy is `Restricted`. Running activation scripts (`.venv\Scripts\Activate.ps1`) fails by default. The design adopts **direct binary path execution** (`.\.venv\Scripts\python.exe`, `.\.venv\Scripts\pip.exe`, etc.), which is immune to execution policy restrictions and eliminates process-isolation state loss across subagents and automated tools.
2. **Deterministic Dependencies for Python 3.12**: Identified verified compatible versions for `backend/requirements.txt` that require zero C/C++ compilation on Windows x86_64 and have zero dependency constraint conflicts.
3. **Environment Template (`backend/.env.example`)**: Defined a self-documenting `.env.example` covering all required variables (`NVIDIA_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `PORT`, `ALLOWED_ORIGINS`) and standard NIM model identifiers with dummy placeholders.
4. **Worker Implementation Plan**: Step-by-step, copy-paste executable commands for the Worker to initialize `.venv`, install packages, configure environment templates, and execute verification.

---

## 2. Host Environment Observations

The following facts were directly verified on the host system:
- **Operating System**: Windows (AMD64 / x86_64 architecture)
- **Active Python**: `Python 3.12.10` located at `C:\Users\Stephen\AppData\Local\Programs\Python\Python312\python.exe`
- **Active Pip**: `pip 25.0.1`
- **PowerShell ExecutionPolicy**: `Restricted` (verified via `Get-ExecutionPolicy`)
- **Network / Sandbox Notice**: Package installation commands reaching external PyPI servers require running outside the restricted sandbox (`BypassSandbox: true`), which the user explicitly requested to proceed via virtual environment.

---

## 3. Virtual Environment Strategy (Windows PowerShell)

### 3.1 The ExecutionPolicy Challenge & Direct Path Solution
In Windows PowerShell, attempting to execute:
```powershell
.\.venv\Scripts\Activate.ps1
```
fails with:
```
File ...\Activate.ps1 cannot be loaded because running scripts is disabled on this system.
```
Even if bypassed for a single session using `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, in automated tool execution (such as agent tool calls or CI runners), each command executes in an independent process where environment changes do not persist.

### 3.2 Recommended Invocation Pattern: Direct Executable Paths
The most reliable, deterministic pattern is direct binary invocation:

| Purpose | Command from Workspace Root | Command from `backend/` |
|---|---|---|
| **Python interpreter** | `.\.venv\Scripts\python.exe` | `..\.venv\Scripts\python.exe` |
| **Package manager** | `.\.venv\Scripts\python.exe -m pip` (or `.\.venv\Scripts\pip.exe`) | `..\.venv\Scripts\python.exe -m pip` |
| **ASGI Server (Uvicorn)** | `.\.venv\Scripts\python.exe -m uvicorn app.main:app` (or `.\.venv\Scripts\uvicorn.exe`) | `..\.venv\Scripts\python.exe -m uvicorn app.main:app` |
| **Test Runner (Pytest)** | `.\.venv\Scripts\python.exe -m pytest` (or `.\.venv\Scripts\pytest.exe`) | `..\.venv\Scripts\python.exe -m pytest` |

**Advantages**:
1. Completely immune to Windows PowerShell execution policy.
2. Guarantees that the virtual environment interpreter and site-packages are used rather than system Python.
3. Preserves isolation without needing persistent subshell state.

### 3.3 Interactive Developer Activation (For Manual Devs)
For human developers working in an interactive PowerShell terminal who prefer `(venv)` prompt activation:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

---

## 4. `backend/requirements.txt` Specification (Python 3.12 Compatibility)

### 4.1 Dependency Compatibility Analysis
All packages were analyzed against Python 3.12 on Windows AMD64:
- **`fastapi` (0.115.6)**: Pure Python; compatible with Starlette 0.40+ and Pydantic v2.
- **`uvicorn[standard]` (0.34.0)**: Pulls standard extras. Note that on Windows, `uvloop` is automatically excluded by pip markers because it is POSIX-only. Standard Windows asyncio event loop is used seamlessly. `httptools` and `watchfiles` have pre-compiled Windows wheels.
- **`pydantic` (2.10.4) & `pydantic-settings` (2.7.0)**: Pre-compiled `pydantic-core` wheels for Python 3.12 on Windows exist, requiring no MSVC build tools.
- **`openai` (1.58.1)**: Pure Python SDK used for OpenAI-compatible async calls to NVIDIA Nemotron (`https://integrate.api.nvidia.com/v1`).
- **`supabase` (2.11.0)**: Pure Python client for Supabase Auth and PostgREST.
- **`httpx` (0.28.1)**: Required by FastAPI `TestClient`, OpenAI SDK, and for direct REST calls to NVIDIA Parakeet STT and Magpie TTS.
- **`python-dotenv` (1.0.1)**: Pure Python `.env` configuration loader.
- **`python-multipart` (0.0.20)**: Required by FastAPI to accept audio file uploads (`UploadFile` / `Form`) in `POST /voice/process`.
- **`pytest` (8.3.4)** & **`pytest-asyncio` (0.25.0)**: Standard async testing framework for Python 3.12.

### 4.2 Exact Content for `backend/requirements.txt`
```text
# ==============================================================================
# VOXPREP Backend Dependencies
# Target: Python 3.12 on Windows / Linux (Zero C-build dependencies)
# ==============================================================================

# Web Framework & ASGI Server
fastapi==0.115.6
uvicorn[standard]==0.34.0

# Data Validation & Settings Management
pydantic==2.10.4
pydantic-settings==2.7.0

# AI Services & HTTP Clients
openai==1.58.1
httpx==0.28.1

# Database & Authentication
supabase==2.11.0

# Environment Configuration & Form Handling
python-dotenv==1.0.1
python-multipart==0.0.20

# Testing Framework & Async Support
pytest==8.3.4
pytest-asyncio==0.25.0
```

---

## 5. `backend/.env.example` Specification

The `.env.example` file must document all required environment variables without committing actual secrets.

### 5.1 Exact Content for `backend/.env.example`
```ini
# ==============================================================================
# VOXPREP Backend Environment Variables
# Copy this file to .env and replace placeholder values with your real credentials.
# DO NOT COMMIT THE ACTUAL .env FILE TO VERSION CONTROL.
# ==============================================================================

# ------------------------------------------------------------------------------
# Server Configuration
# ------------------------------------------------------------------------------
PORT=8000
HOST=0.0.0.0
ENVIRONMENT=development

# ------------------------------------------------------------------------------
# CORS Configuration
# Comma-separated list of allowed origins for the Next.js frontend
# ------------------------------------------------------------------------------
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# ------------------------------------------------------------------------------
# NVIDIA NIM API Configuration
# Sign up and generate your API key at: https://build.nvidia.com
# Single key covers Nemotron LLM, Parakeet STT, and Magpie TTS.
# ------------------------------------------------------------------------------
NVIDIA_API_KEY=your_nvidia_nim_api_key_here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_LLM_MODEL=nvidia/llama-3.1-nemotron-70b-instruct
NVIDIA_STT_MODEL=nvidia/parakeet-ctc-1.1b-asr
NVIDIA_TTS_MODEL=nvidia/magpie-tts-multilingual

# ------------------------------------------------------------------------------
# Supabase Configuration
# Obtain from your Supabase Dashboard -> Project Settings -> API
# ------------------------------------------------------------------------------
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_public_key_here
SUPABASE_SERVICE_KEY=your_supabase_service_role_secret_key_here
```

---

## 6. Recommended Implementation Steps for the Worker

The Worker should perform the following sequential steps to complete this portion of Milestone 0:

### Step 1: Create the Virtual Environment at Root
Execute from workspace root (`d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer`):
```powershell
python -m venv .venv
```

### Step 2: Upgrade Pip & Build Tools
```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
```

### Step 3: Create `backend/requirements.txt`
Write the exact content specified in Section 4.2 to `backend/requirements.txt`.

### Step 4: Install Dependencies into `.venv`
```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```
*(Note: Requires `BypassSandbox: true` so pip can access PyPI over HTTPS)*

### Step 5: Create `backend/.env.example`
Write the exact content specified in Section 5.1 to `backend/.env.example`.

### Step 6: Verify Installation & Environment Health
Run the following verification commands to ensure zero errors:
1. Verify virtual environment Python version:
   ```powershell
   .\.venv\Scripts\python.exe --version
   ```
   *Expected: `Python 3.12.x`*
2. Verify all core modules import cleanly:
   ```powershell
   .\.venv\Scripts\python.exe -c "import fastapi, uvicorn, openai, supabase, pydantic, pydantic_settings, httpx, dotenv, multipart, pytest, pytest_asyncio; print('ALL_CORE_MODULES_OK')"
   ```
   *Expected: `ALL_CORE_MODULES_OK`*
3. Verify pytest executable inside `.venv`:
   ```powershell
   .\.venv\Scripts\pytest.exe --version
   ```
   *Expected: `pytest 8.3.4`*
