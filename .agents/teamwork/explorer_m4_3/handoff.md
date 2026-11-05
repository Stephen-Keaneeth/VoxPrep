# Containerization & Railway Deployment Architecture Handoff

**Author**: `explorer_m4_3` (Containerization & Railway Deployment Architect)  
**Date**: 2026-11-05T22:40:00Z  
**Milestone**: Milestone 4 (Phase 4: Production Hardening, Error Handling, and Deployment)  
**Task**: Containerization (`Dockerfile`) and Railway Cloud Deployment (`railway.json`, `Procfile`) Blueprint

---

## 1. Observation

### 1.1 Existing Repository State & Absence of Deployment Files
Inspection of the project root and `backend/` directory confirmed that no containerization or PaaS deployment manifests currently exist.
- Search command executed:
  ```powershell
  Get-ChildItem -Path . -Recurse -Include Dockerfile*,railway*,Procfile* -File
  ```
  Result: `0` items returned. Neither `Dockerfile`, `railway.json`, `Procfile`, nor `.dockerignore` exist in the repository.

### 1.2 Layout & Specifications in `PROJECT.md` and `ORIGINAL_REQUEST.md`
- In `PROJECT.md` lines 53–56, the target backend code layout explicitly prescribes:
  ```
  backend/
  ├── Dockerfile
  ├── railway.json
  └── Procfile
  ```
- In `ORIGINAL_REQUEST.md` lines 76–78:
  > "Deployment to Railway:
  > - Provide containerization/deployment configuration files (`Dockerfile`, `railway.json` / `Procfile`).
  > - If Railway CLI and credentials are authenticated in the environment, execute live deployment to Railway and confirm `GET /health` on the production URL. Otherwise, document the exact Railway deployment steps and verify production startup locally."

### 1.3 Backend Dependencies & Runtime Characteristics
Inspecting `backend/requirements.txt` reveals:
```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
pydantic-settings==2.7.0
openai==1.58.1
httpx==0.28.1
supabase==2.11.0
python-dotenv==1.0.1
python-multipart==0.0.20
pytest==8.3.4
pytest-asyncio==0.25.0
```
- Line 3 states: `# Target: Python 3.12 on Windows / Linux (Zero C-build dependencies)`.
- All dependencies have pre-compiled binary wheels for Linux `x86_64` and `aarch64`. No C compilers (`gcc`, `g++`, `make`) are required at container build time, making `python:3.12-slim` ideal.

### 1.4 Health Check Endpoint & Dynamic Port Binding in `backend/app/main.py`
Inspecting `backend/app/main.py`:
- Lines 72–78 provide the standardized health check endpoint:
  ```python
  @app.get("/health", status_code=200, tags=["Health"])
  async def health_check():
      """
      Health check endpoint returning service uptime and operational status.
      Required by Acceptance Criteria: returns HTTP 200 with {"status": "ok"}.
      """
      return {"status": "ok"}
  ```
- Lines 111–116 define the server boot:
  ```python
  if __name__ == "__main__":
      import uvicorn

      host = os.getenv("HOST", "0.0.0.0")
      port = int(os.getenv("PORT", "8000"))
      uvicorn.run("app.main:app", host=host, port=port, reload=True)
  ```

### 1.5 Local Environment & Tool Checks
- **Railway CLI**:
  ```powershell
  Get-Command railway -ErrorAction SilentlyContinue
  ```
  Exit code: `1`.
  Direct execution `railway --version`:
  `railway : The term 'railway' is not recognized as the name of a cmdlet, function, script file, or operable program.`
- **Railway Credentials**:
  `Get-ChildItem env:RAILWAY*`: returned 0 items. No `RAILWAY_TOKEN` or credentials exist in the environment.
- **Docker CLI**:
  `docker --version`: `Docker version 29.8.2, build 7fc2dff`.
  `docker info`: `failed to connect to the docker API at npipe:////./pipe/docker_engine` (Docker Desktop daemon is not running on this host).
- **Python Environment**:
  `.venv\Scripts\python --version`: `Python 3.12.10`.
- **Existing Test Suite**:
  `.venv\Scripts\pytest backend/tests`: `314 passed in 1.05s`.
- **Local Production Server & Health Check Execution**:
  Executed production uvicorn server in `backend/` with default port 8000:
  ```powershell
  .venv/Scripts/uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
  ```
  Output:
  ```
  INFO: Started server process [32656]
  INFO: Waiting for application startup.
  INFO: Application startup complete.
  INFO: Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
  INFO: 127.0.0.1:53295 - "GET /health HTTP/1.1" 200 OK
  Healthcheck status code: 200 Body: {'status': 'ok'}
  ```
  Also verified dynamic port binding using `PORT=7432`:
  ```
  INFO: Started server process [18904]
  INFO: Uvicorn running on http://127.0.0.1:7432 (Press CTRL+C to quit)
  INFO: 127.0.0.1:52447 - "GET /health HTTP/1.1" 200 OK
  Dynamic port healthcheck status: 200 Body: {'status': 'ok'}
  ```

---

## 2. Logic Chain

1. **Base Image Selection (`python:3.12-slim`)**:
   - Because `backend/requirements.txt` consists solely of pure Python libraries and packages with standard pre-compiled Linux wheels (`uvicorn[standard]`, `pydantic-core`, `httpx`), full Debian build tools are unnecessary.
   - `python:3.12-slim` (Debian 12 Bookworm) provides a minimal ~150 MB footprint while ensuring binary compatibility with the local development runtime (`Python 3.12.10`).

2. **System Health Check Prerequisite (`curl`)**:
   - The required Docker healthcheck instruction calls `curl -f http://localhost:8000/health || exit 1`.
   - `python:3.12-slim` does not package `curl` by default.
   - Therefore, the Dockerfile must execute `apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*` to provide `curl` with zero leftover cache bloat.

3. **Security & Non-Root Execution (`appuser`)**:
   - Running containerized workloads as `root` violates security best practices and enterprise compliance standards.
   - A dedicated system user and group `appuser` (UID 1001) is created via `groupadd -r appuser && useradd -r -u 1001 -g appuser -d /app -s /sbin/nologin appuser`.
   - Ownership of `/app` is granted to `appuser:appuser`, and `USER appuser` drops privileges prior to container execution.

4. **Clean Docker Layer Caching**:
   - Source code changes happen frequently; dependency updates happen rarely.
   - Copying `requirements.txt` first and running `pip install --no-cache-dir -r requirements.txt` before copying `app/` ensures Docker reuses the cached dependency layer whenever only application code changes.
   - A companion `.dockerignore` prevents copying local `.venv`, `__pycache__`, `.env`, and test artifacts into the build context.

5. **Dynamic `$PORT` Entrypoint for Railway**:
   - Railway dynamically assigns a listening port at container startup via the `$PORT` environment variable (e.g., `PORT=7432`).
   - If `CMD` uses exec form without a shell (e.g. `["uvicorn", "app.main:app", "--port", "8000"]`), the literal string `$PORT` or hardcoded `8000` is used, causing Railway's ingress proxy to fail with connection refused.
   - By running via shell form `CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]`, the container dynamically respects `$PORT` in production while cleanly defaulting to `8000` when tested locally.

6. **PaaS Configuration (`railway.json` and `Procfile`)**:
   - Railway supports two builder engines: **Dockerfile** and **Nixpacks**.
   - `railway.json` defines explicit build settings (`builder: "DOCKERFILE"`, `dockerfilePath: "Dockerfile"`) and deploy parameters (`healthcheckPath: "/health"`, `restartPolicyType: "ON_FAILURE"`).
   - `Procfile` (`web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`) provides an immediate fallback for Nixpacks builds, Heroku-style buildpacks, or alternative PaaS providers (e.g., Render, Fly.io).

7. **Monorepo Directory Alignment**:
   - Per `PROJECT.md`, deployment files belong in `backend/` (`backend/Dockerfile`, `backend/railway.json`, `backend/Procfile`, `backend/.dockerignore`).
   - In Railway, setting **Root Directory** to `backend` allows Railway to treat `backend/` as the project root.
   - To make root deployment equally turnkey, providing companion root-level `railway.json` and `Procfile` guarantees that deployments succeed regardless of whether the user sets the Root Directory to `backend` or leaves it at repo root.

8. **Deployment Workflow Determination**:
   - Because `railway` CLI is not installed on the system and no `RAILWAY_*` tokens are present, automated cloud CLI deployment cannot be executed from this environment.
   - Therefore, per `ORIGINAL_REQUEST.md` R5:
     1. Design the complete container and deployment configuration files.
     2. Document the step-by-step manual deployment procedure via Railway GitHub integration.
     3. Document the CLI deployment command sequence for environments where the CLI is authenticated.
     4. Verify local production container and uvicorn startup instructions.

---

## 3. Caveats

1. **No Local Docker Daemon**:
   - Docker CLI 29.8.2 is installed, but the Docker Desktop daemon was not running on this host (`failed to connect to the docker API at npipe:////./pipe/docker_engine`). Actual compilation of the image within a local daemon could not be performed. However, production server execution was independently verified with Python 3.12 / Uvicorn.
2. **Dynamic Port Environment on Railway**:
   - Railway automatically sets the `PORT` environment variable. Users must NOT add a hardcoded `PORT=8000` to Railway's project variables in the dashboard, as this overrides Railway's internal port routing.
3. **CORS Configuration on Railway**:
   - In production, once the Vercel frontend is deployed (e.g., `https://voxprep.vercel.app`), the backend Railway service variable `ALLOWED_ORIGINS` must be set to that exact URL (plus `http://localhost:3000` for local frontend development).
4. **Cold Starts and Mock Mode Fallback**:
   - When external `NVIDIA_API_KEY` or `SUPABASE_URL` credentials are dummy or missing, the backend automatically operates in mock mode without failing container healthchecks. Live API keys must be added in the Railway dashboard for full AI functionality.

---

## 4. Conclusion & Production Blueprint

### 4.1 Artifact Blueprints to Implement

#### 1. `backend/Dockerfile`
```dockerfile
# ==============================================================================
# VOXPREP Backend - Production Dockerfile
# Base: Python 3.12 Slim (Debian Bookworm)
# Security: Non-root execution (appuser:appuser, UID 1001)
# ==============================================================================

FROM python:3.12-slim AS runtime

# Default container environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    PYTHONPATH=/app

# Install minimal OS dependencies for health check and clean apt cache
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated unprivileged user and group
RUN groupadd -r appuser && useradd -r -u 1001 -g appuser -d /app -s /sbin/nologin appuser

# Set working directory
WORKDIR /app

# Layer Caching Optimization: copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source code and schema
COPY app/ ./app/
COPY schema.sql .

# Ensure app directory permissions belong to non-root appuser
RUN chown -R appuser:appuser /app

# Switch to non-root execution
USER appuser

# Expose default application port (overridden by Railway $PORT at runtime)
EXPOSE 8000

# Container healthcheck instruction calling curl
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Production entrypoint: uvicorn binding to dynamic $PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

#### 2. `backend/.dockerignore`
```dockerignore
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
ENV/
env/
.pytest_cache/
.coverage
htmlcov/
tests/
.git/
.gitignore
.dockerignore
.env
.env.*
!.env.example
*.log
.agents/
docs/
```

#### 3. `backend/railway.json`
```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 5
  }
}
```

#### 4. `backend/Procfile`
```procfile
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

#### 5. Root-Level Compatibility Manifests
For monorepo flexibility (in case Railway service root is configured to `/`):
- **`railway.json` (Root)**:
  ```json
  {
    "$schema": "https://railway.com/railway.schema.json",
    "build": {
      "builder": "DOCKERFILE",
      "dockerfilePath": "backend/Dockerfile"
    },
    "deploy": {
      "startCommand": "cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT",
      "healthcheckPath": "/health",
      "healthcheckTimeout": 100,
      "restartPolicyType": "ON_FAILURE",
      "restartPolicyMaxRetries": 5
    }
  }
  ```
- **`Procfile` (Root)**:
  ```procfile
  web: cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```

---

### 4.2 Railway Deployment Guide: Manual GitHub Integration (Primary Path)

Follow these steps to deploy the VOXPREP backend to Railway via GitHub:

1. **Push Changes to GitHub**:
   Ensure all changes are committed and pushed to your remote repository:
   ```bash
   git add backend/Dockerfile backend/railway.json backend/Procfile backend/.dockerignore
   git commit -m "feat(deploy): add production Dockerfile, railway.json, and Procfile"
   git push origin main
   ```

2. **Create New Project in Railway Dashboard**:
   - Go to [https://railway.app/dashboard](https://railway.app/dashboard) and sign in.
   - Click **+ New Project**.
   - Select **Deploy from GitHub repo**.
   - Choose the `AI-Interviewer` repository from your list.

3. **Configure Service Settings**:
   - Click on the newly created backend service card in the Railway canvas.
   - Go to **Settings** -> **General**:
     * **Service Name**: `voxprep-backend`
     * **Root Directory**: Set to `backend` (this ensures Railway uses `backend/Dockerfile` and `backend/railway.json`).
   - Go to **Settings** -> **Build**:
     * **Builder**: `Dockerfile` (or leave default auto-detect).
     * **Dockerfile Path**: `Dockerfile`
   - Go to **Settings** -> **Deploy**:
     * **Healthcheck Path**: `/health`
     * **Healthcheck Timeout**: `100` seconds
     * **Restart Policy**: `On Failure` (Max Retries: `5`)

4. **Configure Environment Variables**:
   In the service card, switch to the **Variables** tab and add the following keys (matching `backend/.env.example`):
   | Variable Name | Example / Production Value | Notes |
   |---|---|---|
   | `NVIDIA_API_KEY` | `nvapi-xxxxxxxxxxxxxxxxxxxxxxxx` | Single key for Nemotron, Parakeet, Magpie |
   | `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1` | NVIDIA NIM endpoint |
   | `NVIDIA_LLM_MODEL` | `nvidia/llama-3.1-nemotron-70b-instruct` | LLM model identifier |
   | `NVIDIA_STT_MODEL` | `nvidia/parakeet-ctc-1.1b-asr` | STT model identifier |
   | `NVIDIA_TTS_MODEL` | `nvidia/magpie-tts-multilingual` | TTS model identifier |
   | `SUPABASE_URL` | `https://<your-project-id>.supabase.co` | Supabase project URL |
   | `SUPABASE_SERVICE_KEY` | `eyJhbGciOi...` | Supabase service role secret |
   | `SUPABASE_ANON_KEY` | `eyJhbGciOi...` | Supabase anon public key |
   | `ALLOWED_ORIGINS` | `https://<frontend-app>.vercel.app,http://localhost:3000` | Comma-separated CORS origins |
   | `HOST` | `0.0.0.0` | Default listening interface |
   | `ENVIRONMENT` | `production` | Deployment environment flag |

   *(Note: Do **NOT** set `PORT` in Railway variables. Railway automatically injects the assigned `PORT` at runtime).*

5. **Generate Public Domain**:
   - In **Settings** -> **Networking** -> **Public Networking**, click **Generate Domain**.
   - Railway will provide a live URL such as: `https://voxprep-backend-production.up.railway.app`.

6. **Verify Live Deployment**:
   Execute the following curl commands against your public domain:
   ```bash
   # 1. Healthcheck (expected: HTTP 200 {"status": "ok"})
   curl -f -i https://<your-railway-domain>/health

   # 2. Root metadata & Swagger documentation link
   curl -f -i https://<your-railway-domain>/

   # 3. OpenAPI docs check
   curl -f -i https://<your-railway-domain>/docs
   ```

---

### 4.3 Railway CLI Deployment Guide (Alternative Path for CLI Users)

For developers with the Railway CLI installed and authenticated:

1. **Install and Authenticate**:
   ```bash
   # Install via npm or scoop/brew
   npm i -g @railway/cli

   # Login via browser or API token
   railway login
   # Or headless with token:
   # export RAILWAY_TOKEN="<your-railway-api-token>"
   ```

2. **Initialize or Link Railway Project**:
   ```bash
   cd backend
   railway init
   # Or link to existing project:
   # railway link <project-id>
   ```

3. **Configure Environment Variables**:
   ```bash
   railway variables --set "NVIDIA_API_KEY=nvapi-xxxx" \
     "NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1" \
     "NVIDIA_LLM_MODEL=nvidia/llama-3.1-nemotron-70b-instruct" \
     "NVIDIA_STT_MODEL=nvidia/parakeet-ctc-1.1b-asr" \
     "NVIDIA_TTS_MODEL=nvidia/magpie-tts-multilingual" \
     "SUPABASE_URL=https://xxxx.supabase.co" \
     "SUPABASE_SERVICE_KEY=xxxx" \
     "SUPABASE_ANON_KEY=xxxx" \
     "ALLOWED_ORIGINS=*" \
     "HOST=0.0.0.0" \
     "ENVIRONMENT=production"
   ```

4. **Deploy Live**:
   ```bash
   railway up
   ```

5. **Generate Domain & Validate**:
   ```bash
   railway domain
   railway status
   railway logs
   curl -f https://<generated-domain>/health
   ```

---

### 4.4 Local Container Build & Verification Instructions

To test the container locally on any workstation with Docker running:

1. **Build Container Image**:
   ```bash
   # From project root:
   docker build -t voxprep-backend -f backend/Dockerfile ./backend

   # Or from backend directory:
   cd backend
   docker build -t voxprep-backend .
   ```

2. **Run Container Locally**:
   ```bash
   docker run --rm -d \
     --name voxprep-backend-test \
     -p 8000:8000 \
     -e PORT=8000 \
     -e NVIDIA_API_KEY="mock_key" \
     -e SUPABASE_URL="https://mock.supabase.co" \
     -e SUPABASE_SERVICE_KEY="mock_key" \
     voxprep-backend
   ```

3. **Verify Health & Inspect Container**:
   ```bash
   # Test health endpoint:
   curl -f http://localhost:8000/health
   # Expected response: {"status": "ok"}

   # Test root metadata:
   curl -f http://localhost:8000/
   # Expected response: {"title": "VOXPREP Backend API", ...}

   # Inspect Docker native health status:
   docker inspect --format='{{json .State.Health.Status}}' voxprep-backend-test
   # Expected output: "healthy"

   # Cleanup:
   docker stop voxprep-backend-test
   ```

---

## 5. Verification Method

To independently verify the containerization and deployment blueprints:

### 5.1 Automated Test Suite Verification
Run pytest from the backend virtual environment to ensure existing test coverage remains 100% intact:
```powershell
.venv\Scripts\pytest backend/tests
```
- **Expected Outcome**: All 314 tests pass with zero failures (`314 passed in ~1.0s`).

### 5.2 Local Production Startup Verification
Verify that `uvicorn` boots cleanly with production flags without relying on Docker daemon:
```powershell
# From project root:
cd backend
..\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
```
- In another terminal:
  ```powershell
  curl -i http://localhost:8000/health
  ```
- **Expected Outcome**: HTTP 200 with response `{"status": "ok"}`.

### 5.3 Dockerfile Syntax & Layer Verification
Once written by the implementation worker, verify file presence and syntax:
```powershell
Get-Content backend\Dockerfile
Get-Content backend\railway.json
Get-Content backend\Procfile
Get-Content backend\.dockerignore
```

### 5.4 Invalidation Conditions
This blueprint is invalidated if:
- `backend/requirements.txt` adds a package requiring native C compilation (e.g., `scipy`, `numpy` requiring `gcc`), necessitating multi-stage build toolchain stages (`python:3.12-slim` builder stage).
- `backend/app/main.py` changes the health check route from `/health` to another path without updating `HEALTHCHECK` and `railway.json`.
- Railway changes its configuration schema or drops support for `railway.json` v2.
