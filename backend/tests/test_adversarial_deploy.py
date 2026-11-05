"""
VOXPREP Backend - Milestone 4 Production Deployment & Startup Adversarial Tests
Empirically stress-tests Uvicorn startup, health check endpoint, environment configurations,
socket binding, and container/cloud manifests (Dockerfile, railway.json, Procfile, .dockerignore).
"""

import gc
import importlib
import json
import os
import re
import socket
import sys
import time
from pathlib import Path
from unittest import mock
import pytest
from fastapi import FastAPI, status
import uvicorn

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
repo_dir = backend_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(repo_dir) not in sys.path:
    sys.path.insert(0, str(repo_dir))

from app.main import app, get_allowed_origins
from tests.conftest import LocalClient


class TestProductionStartupAndHealth:
    """Stress-tests uvicorn import cleanliness, health check stability, and socket behavior."""

    def test_uvicorn_app_import_cleanly(self):
        """Empirically verifies that uvicorn app.main:app imports cleanly without unhandled exceptions."""
        module = importlib.import_module("app.main")
        assert hasattr(module, "app"), "app.main must export an 'app' instance for Uvicorn"
        assert isinstance(module.app, FastAPI), "app must be an instance of FastAPI"
        assert module.app.title == "VOXPREP Backend API"

    def test_health_check_payload_and_status(self, client):
        """Empirically verifies GET /health returns HTTP 200 with exact {'status': 'ok'} payload."""
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == {"status": "ok"}, f"Expected {{'status': 'ok'}}, got {data}"

    def test_health_check_rapid_burst_stress(self, client):
        """Stress-tests GET /health under rapid burst queries (50 consecutive requests)."""
        start_time = time.perf_counter()
        for i in range(50):
            response = client.get("/health")
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == {"status": "ok"}
        elapsed = time.perf_counter() - start_time
        assert elapsed < 2.0, f"50 health checks took too long: {elapsed:.3f}s"

    def test_health_check_zero_resource_leak(self, client):
        """Verifies no object accumulation or leak occurs during repeated health check calls."""
        gc.collect()
        initial_objects = len(gc.get_objects())
        for _ in range(50):
            res = client.get("/health")
            assert res.status_code == status.HTTP_200_OK
        gc.collect()
        final_objects = len(gc.get_objects())
        growth = final_objects - initial_objects
        # Normal fluctuation is small, should not accumulate unboundedly
        assert growth < 100, f"Potential memory leak detected: object growth was {growth}"

    def test_health_check_query_params_ignored(self, client):
        """Verifies health check handles extraneous or adversarial query params without error."""
        params = {"probe": "k8s", "token": "secret_xyz", "repeat": "999"}
        response = client.get("/health", params=params)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}

    def test_health_check_oversized_header(self, client):
        """Verifies health check gracefully processes requests with large HTTP headers (4KB)."""
        large_header = "x" * 4096
        response = client.get("/health", headers={"X-Custom-Probe": large_header})
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}

    @pytest.mark.parametrize("disallowed_method", ["post", "put", "delete"])
    def test_health_check_disallowed_methods(self, client, disallowed_method):
        """Verifies health check rejects non-GET methods with HTTP 405 Method Not Allowed."""
        method_fn = getattr(client, disallowed_method)
        response = method_fn("/health")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        data = response.json()
        assert data.get("error_type") == "http_error"
        assert data.get("status_code") == 405

    def test_root_endpoint_metadata(self, client):
        """Verifies root endpoint GET / provides service metadata and links to health check."""
        response = client.get("/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.get("title") == "VOXPREP Backend API"
        assert data.get("status") == "online"
        assert data.get("health_check") == "/health"


class TestEnvironmentConfiguration:
    """Stress-tests parsing and resilience of environment configurations."""

    def test_get_allowed_origins_default_wildcard(self):
        """When ALLOWED_ORIGINS and CORS_ORIGINS are unset, defaults to wildcard [*]."""
        with mock.patch.dict(os.environ, {}, clear=True):
            origins = get_allowed_origins()
            assert origins == ["*"]

    def test_get_allowed_origins_explicit_list(self):
        """Parses comma-separated list of origins, trimming excess whitespace."""
        env_val = " http://localhost:3000 , https://voxprep.vercel.app , https://custom.domain.com "
        with mock.patch.dict(os.environ, {"ALLOWED_ORIGINS": env_val}, clear=True):
            origins = get_allowed_origins()
            assert origins == [
                "http://localhost:3000",
                "https://voxprep.vercel.app",
                "https://custom.domain.com",
            ]

    def test_get_allowed_origins_empty_string_fallback(self):
        """When ALLOWED_ORIGINS is an empty string, falls back to ['http://localhost:3000']."""
        with mock.patch.dict(os.environ, {"ALLOWED_ORIGINS": ""}, clear=True):
            origins = get_allowed_origins()
            assert origins == ["http://localhost:3000"]

    def test_get_allowed_origins_fallback_to_cors_origins(self):
        """When ALLOWED_ORIGINS is unset, falls back to CORS_ORIGINS."""
        with mock.patch.dict(os.environ, {"CORS_ORIGINS": "https://fallback.domain.com"}, clear=True):
            origins = get_allowed_origins()
            assert origins == ["https://fallback.domain.com"]

    def test_dynamic_port_binding_uvicorn(self):
        """Empirically binds Uvicorn config to dynamic high ports (simulating Railway $PORT assignment)."""
        test_ports = [7432, 8888]
        for p in test_ports:
            cfg = uvicorn.Config("app.main:app", host="127.0.0.1", port=p, log_level="warning")
            sock = cfg.bind_socket()
            try:
                sock_name = sock.getsockname()
                assert sock_name[1] == p, f"Expected bound port {p}, got {sock_name[1]}"
            finally:
                sock.close()

    def test_supabase_mock_mode_resilience(self):
        """Verifies database client safely initializes mock mode when credentials are dummy/placeholder."""
        from app.db.supabase import get_supabase_client, reset_supabase_client, MockSupabaseClient
        reset_supabase_client()
        with mock.patch.dict(os.environ, {"SUPABASE_URL": "https://placeholder.supabase.co", "SUPABASE_ANON_KEY": "dummy_key"}):
            client = get_supabase_client()
            assert isinstance(client, MockSupabaseClient)
        reset_supabase_client()

    def test_llm_mock_mode_resilience(self):
        """Verifies LLM service correctly identifies mock mode when API keys are dummy/placeholder."""
        from app.services.llm import is_mock_mode
        with mock.patch.dict(os.environ, {"NVIDIA_API_KEY": "your_nvidia_nim_api_key_here"}):
            assert is_mock_mode() is True

        with mock.patch.dict(os.environ, {"NVIDIA_API_KEY": ""}):
            assert is_mock_mode() is True


class TestDeploymentManifests:
    """Validates Dockerfiles, railway.json, Procfiles, and .dockerignore for production deployment."""

    def test_root_dockerfile_syntax_and_security(self):
        """Empirically validates root Dockerfile structure, non-root user, healthcheck, and entrypoint."""
        dockerfile_path = repo_dir / "Dockerfile"
        assert dockerfile_path.exists(), "Root Dockerfile must exist"
        content = dockerfile_path.read_text(encoding="utf-8")

        # Base image
        assert re.search(r"FROM\s+python:3\.12-slim", content), "Must use python:3.12-slim base image"

        # Non-root user creation and switch
        assert "groupadd -r appuser" in content, "Must create dedicated appuser group"
        assert "useradd -r" in content and "appuser" in content, "Must create dedicated appuser user"
        assert "USER appuser" in content, "Must switch to non-root USER appuser"

        # Layer caching order: requirements.txt copied before app code
        req_copy_idx = content.find("COPY backend/requirements.txt")
        app_copy_idx = content.find("COPY backend/app/")
        assert req_copy_idx != -1 and app_copy_idx != -1, "Must copy requirements.txt and app directory"
        assert req_copy_idx < app_copy_idx, "Requirements must be copied before app code for layer caching"

        # Healthcheck
        assert "HEALTHCHECK" in content, "Must include HEALTHCHECK instruction"
        assert "curl -f http://localhost:${PORT:-8000}/health" in content, "Healthcheck must probe /health"

        # Entrypoint with dynamic $PORT
        assert "uvicorn app.main:app" in content, "Entrypoint must invoke uvicorn app.main:app"
        assert "${PORT:-8000}" in content or "$PORT" in content, "Entrypoint must respect dynamic $PORT"

        # Verify referenced build context files exist
        assert (repo_dir / "backend" / "requirements.txt").exists()
        assert (repo_dir / "backend" / "app" / "main.py").exists()
        assert (repo_dir / "backend" / "schema.sql").exists()

    def test_backend_dockerfile_syntax_and_security(self):
        """Empirically validates backend/Dockerfile structure for standalone backend container build."""
        dockerfile_path = backend_dir / "Dockerfile"
        assert dockerfile_path.exists(), "backend/Dockerfile must exist"
        content = dockerfile_path.read_text(encoding="utf-8")

        assert re.search(r"FROM\s+python:3\.12-slim", content)
        assert "USER appuser" in content
        assert "HEALTHCHECK" in content
        assert "uvicorn app.main:app" in content

        # Verify referenced build context files exist
        assert (backend_dir / "requirements.txt").exists()
        assert (backend_dir / "app" / "main.py").exists()
        assert (backend_dir / "schema.sql").exists()

    def test_root_railway_json_validity(self):
        """Empirically validates root railway.json syntax, build and deploy settings."""
        railway_path = repo_dir / "railway.json"
        assert railway_path.exists(), "Root railway.json must exist"
        data = json.loads(railway_path.read_text(encoding="utf-8"))

        build = data.get("build", {})
        assert build.get("builder") == "DOCKERFILE"
        assert build.get("dockerfilePath") == "Dockerfile"
        assert (repo_dir / build.get("dockerfilePath")).exists()

        deploy = data.get("deploy", {})
        assert "uvicorn app.main:app" in deploy.get("startCommand", "")
        assert "$PORT" in deploy.get("startCommand", "")
        assert deploy.get("healthcheckPath") == "/health"
        assert deploy.get("restartPolicyType") == "ON_FAILURE"

    def test_backend_railway_json_validity(self):
        """Empirically validates backend/railway.json syntax, build and deploy settings."""
        railway_path = backend_dir / "railway.json"
        assert railway_path.exists(), "backend/railway.json must exist"
        data = json.loads(railway_path.read_text(encoding="utf-8"))

        build = data.get("build", {})
        assert build.get("builder") == "DOCKERFILE"
        assert build.get("dockerfilePath") == "Dockerfile"
        assert (backend_dir / build.get("dockerfilePath")).exists()

        deploy = data.get("deploy", {})
        assert "uvicorn app.main:app" in deploy.get("startCommand", "")
        assert "$PORT" in deploy.get("startCommand", "")
        assert deploy.get("healthcheckPath") == "/health"

    def test_procfile_configurations(self):
        """Empirically validates root Procfile and backend/Procfile format and commands."""
        root_procfile = repo_dir / "Procfile"
        assert root_procfile.exists()
        root_line = root_procfile.read_text(encoding="utf-8").strip()
        assert root_line.startswith("web:")
        assert "uvicorn app.main:app" in root_line
        assert "$PORT" in root_line

        backend_procfile = backend_dir / "Procfile"
        assert backend_procfile.exists()
        backend_line = backend_procfile.read_text(encoding="utf-8").strip()
        assert backend_line.startswith("web:")
        assert "uvicorn app.main:app" in backend_line
        assert "$PORT" in backend_line

    def test_dockerignore_security(self):
        """Empirically validates that .dockerignore prevents leaking secrets, git, and virtualenvs."""
        for path in [repo_dir / ".dockerignore", backend_dir / ".dockerignore"]:
            assert path.exists(), f"{path} must exist"
            content = path.read_text(encoding="utf-8")
            # Verify critical ignores
            assert ".venv" in content
            assert "__pycache__" in content
            assert ".env" in content
            assert ".git" in content
