"""
VOXPREP Backend API - Global Error Handling and Exception Middleware Tests
Milestone 4: Phase 4 Production Hardening, Error Handling, and Deployment

Test Coverage:
1. HTTP 404 Not Found handling on invalid routes and missing entities.
2. HTTP 422 Unprocessable Entity handling on missing mandatory fields and type errors.
3. HTTP 400 Bad Request handling on route logic validation errors.
4. HTTP 500 Internal Server Error handling on unexpected server exceptions (sanitization, no stack leaks).
5. Schema uniformity: response JSON consistently provides {"detail", "error_type", "status_code"}.
6. Full backward-compatibility: standard test patterns (res.json()["detail"], res.json().get("detail")) remain functional.
7. CORS preservation: error responses retain CORS origin reflection headers for browser clients.
"""

import unittest.mock as mock
import pytest
from fastapi import status


def test_404_invalid_route_returns_uniform_error(client):
    """Verifies that requests to non-existent route paths return HTTP 404 with uniform schema."""
    resp = client.get("/api/v1/nonexistent/endpoint")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"] == "Not Found"
    assert data["error_type"] == "http_error"
    assert data["status_code"] == 404


def test_404_resource_not_found(client):
    """Verifies that requests for missing domain entities return HTTP 404 with descriptive detail."""
    resp = client.get("/interview/report/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert "not found" in data["detail"].lower()
    assert data["error_type"] == "http_error"
    assert data["status_code"] == 404


def test_422_missing_mandatory_body_fields(client):
    """Verifies that omitting mandatory request body parameters returns HTTP 422 with validation errors."""
    resp = client.post("/auth/register", json={})
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = resp.json()
    assert isinstance(data["detail"], list)
    assert len(data["detail"]) > 0
    assert data["error_type"] == "validation_error"
    assert data["status_code"] == 422


def test_422_field_type_mismatch(client):
    """Verifies that invalid field types return HTTP 422 with structured field error locations."""
    resp = client.post("/interview/start", json={
        "candidate_name": 12345,
        "role": "Backend Engineer",
        "experience_level": "Senior",
        "interview_type": "invalid_track",
    })
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = resp.json()
    assert isinstance(data["detail"], list)
    assert data["error_type"] == "validation_error"
    assert data["status_code"] == 422


def test_400_bad_request_domain_validation(client):
    """Verifies that domain validation errors raise HTTP 400 with string detail."""
    resp = client.post("/auth/register", json={
        "email": "invalid-email-format-without-at-sign",
        "password": "ValidPassword123!",
        "name": "Test Candidate",
    })
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    data = resp.json()
    assert isinstance(data["detail"], str)
    assert "email" in data["detail"].lower()
    assert data["error_type"] == "http_error"
    assert data["status_code"] == 400


def test_400_coach_empty_user_id(client):
    """Verifies that empty user_id in coach start returns HTTP 400 with detail."""
    resp = client.post("/coach/start", json={
        "user_id": "   ",
        "mode": "conversation",
    })
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    data = resp.json()
    assert "user_id" in data["detail"].lower()
    assert data["error_type"] == "http_error"
    assert data["status_code"] == 400


def test_400_coach_respond_empty_user_text(client):
    """Verifies that empty user_text in coach respond returns HTTP 400 with detail."""
    resp = client.post("/coach/respond", json={
        "session_id": "any-active-session-id",
        "user_text": "   ",
    })
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    data = resp.json()
    assert "user_text" in data["detail"].lower()
    assert data["error_type"] == "http_error"
    assert data["status_code"] == 400


def test_500_internal_server_error_sanitization(client):
    """Verifies that unhandled exceptions return HTTP 500 without leaking stack traces or internal secrets."""
    with mock.patch("app.routers.auth.get_supabase_client", side_effect=RuntimeError("Secret database connection string leaked!")):
        resp = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "Password123!",
        })
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = resp.json()
        assert data["detail"] == "Internal server error occurred."
        assert data["error_type"] == "internal_server_error"
        assert data["status_code"] == 500
        # Ensure raw stack traces and internal secrets are NEVER leaked to client
        raw_text = resp.text.lower()
        assert "secret database" not in raw_text
        assert "traceback" not in raw_text
        assert "file " not in raw_text


def test_error_response_backward_compatibility_detail_access(client):
    """Verifies that existing test suite patterns (res.json()['detail'], res.json().get('detail')) work seamlessly."""
    # 404 check
    r404 = client.get("/nonexistent-route-for-backward-compat")
    assert r404.json()["detail"] == "Not Found"
    assert r404.json().get("detail") == "Not Found"

    # 400 check
    r400 = client.post("/auth/register", json={"email": "bad", "password": "password123"})
    assert isinstance(r400.json()["detail"], str)
    assert isinstance(r400.json().get("detail"), str)

    # 422 check
    r422 = client.post("/auth/register", json={})
    assert isinstance(r422.json()["detail"], list)
    assert isinstance(r422.json().get("detail"), list)


def test_cors_headers_present_on_error_responses(client):
    """Verifies CORS origin reflection headers are attached on error responses."""
    resp = client.get("/api/nonexistent", headers={"origin": "http://localhost:3000"})
    assert resp.status_code == 404
    assert "access-control-allow-origin" in resp.headers


def test_cors_headers_present_on_500_unhandled_error(client):
    """Verifies that unhandled exceptions returning HTTP 500 preserve CORS origin reflection and credentials headers."""
    origin = "http://localhost:3000"
    with mock.patch("app.routers.auth.get_supabase_client", side_effect=RuntimeError("Simulated unhandled failure")):
        resp = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "Password123!"},
            headers={"Origin": origin},
        )
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert resp.headers.get("access-control-allow-origin") == origin
        assert resp.headers.get("access-control-allow-credentials") == "true"
        data = resp.json()
        assert data["detail"] == "Internal server error occurred."
        assert data["error_type"] == "internal_server_error"
        assert data["status_code"] == 500

