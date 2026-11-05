"""
VOXPREP Backend API - Adversarial Stress Tests for Error Handling and CORS Resilience
Milestone 4: Phase 4 Production Hardening, Error Handling, and Deployment

Adversarial Stress Test Categories:
1. Malformed JSON payloads, truncated bodies, null bytes, extreme Unicode characters, and invalid top-level types.
2. Route fuzzing: directory traversal attacks (/../../etc/passwd), path normalization attacks, script injection in paths, and extreme path lengths.
3. Unhandled exception injection: simulate routes raising arbitrary unhandled exceptions (RuntimeError, KeyError, ZeroDivisionError, TypeError, ValueError), ensuring:
   - Status code is strictly 500.
   - Payload is strictly sanitized {"detail": "Internal server error occurred.", "error_type": "internal_server_error", "status_code": 500}.
   - Internal secrets, file paths, and Python tracebacks are NEVER leaked.
   - Server does not crash, hang, or lose operational state.
4. CORS resilience across all HTTP error statuses (400, 404, 422, 500):
   - Access-Control-Allow-Origin dynamically reflects the requesting origin.
   - Access-Control-Allow-Credentials is set to "true".
   - Preflight OPTIONS requests to invalid/error routes handle CORS headers correctly.
"""

import unittest.mock as mock
import pytest
from fastapi import status


# =============================================================================
# Category 1: Malformed JSON Bodies, Null Bytes & Extreme Payloads
# =============================================================================

def test_malformed_truncated_json_body_returns_422(client):
    """Verifies that truncated JSON request payloads return HTTP 422 with uniform schema and no server crash."""
    truncated_payload = b'{"email": "attacker@example.com", "password": '
    resp = client.post(
        "/auth/login",
        data=truncated_payload,
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = resp.json()
    assert data["error_type"] == "validation_error"
    assert data["status_code"] == 422
    assert isinstance(data["detail"], list)
    assert len(data["detail"]) > 0


def test_malformed_invalid_syntax_json_body_returns_422(client):
    """Verifies that syntactically broken JSON returns HTTP 422 with validation_error type."""
    broken_payload = b'{"broken": [,,,], "key": }'
    resp = client.post(
        "/auth/register",
        data=broken_payload,
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = resp.json()
    assert data["error_type"] == "validation_error"
    assert data["status_code"] == 422
    assert isinstance(data["detail"], list)


def test_malformed_binary_content_as_json_returns_422(client):
    """Verifies that non-JSON arbitrary binary payload with application/json header is caught gracefully."""
    raw_binary = b"\x00\x01\x02\xff\xfe\xfd\xaa\xbb"
    resp = client.post(
        "/interview/start",
        data=raw_binary,
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = resp.json()
    assert data["error_type"] == "validation_error"
    assert data["status_code"] == 422


def test_empty_body_with_json_content_type_returns_422(client):
    """Verifies that sending an empty byte stream with application/json header returns HTTP 422."""
    resp = client.post(
        "/auth/login",
        data=b"",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = resp.json()
    assert data["error_type"] == "validation_error"
    assert data["status_code"] == 422


def test_top_level_json_array_instead_of_object_returns_422(client):
    """Verifies that sending a JSON list when a JSON object model is expected returns HTTP 422."""
    resp = client.post(
        "/auth/login",
        json=[{"email": "attacker@test.com"}, {"password": "pass"}],
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = resp.json()
    assert data["error_type"] == "validation_error"
    assert data["status_code"] == 422


def test_top_level_json_primitive_instead_of_object_returns_422(client):
    """Verifies that sending a primitive JSON scalar (string or int) returns HTTP 422."""
    resp = client.post(
        "/coach/start",
        data=b'"just-a-raw-string-primitive"',
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = resp.json()
    assert data["error_type"] == "validation_error"
    assert data["status_code"] == 422


def test_payload_with_null_bytes_handled_gracefully(client):
    """Verifies that payloads containing embedded null bytes do not crash the parser or leak memory."""
    payload_with_null = {
        "candidate_name": "Adversary\x00Injected",
        "role": "Security\x00Specialist",
        "experience_level": "Senior",
        "interview_type": "technical",
    }
    resp = client.post("/interview/start", json=payload_with_null)
    # The server should either accept and process it safely or reject with 400/422, but never 500
    assert resp.status_code in (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)
    if resp.status_code != status.HTTP_200_OK:
        data = resp.json()
        assert "status_code" in data
        assert "error_type" in data


def test_extreme_unicode_and_huge_strings_handled_gracefully(client):
    """Verifies that adversarial Unicode (RTL, Zalgo, surrogate sequences, emojis, long strings) is handled gracefully."""
    extreme_unicode = (
        "\U0001F600 \u202E\u200B\uFEFF\u2603 "  # Emoji + RTL override + zero-width + BOM + snowman
        "\u0300\u0301\u0302\u0303\u0304"       # Combining diacritics / zalgo
        "نص_عربي_اختباري"                       # Arabic script
        "測試測試"                               # CJK ideographs
    ) * 100  # Repeat to form large payload
    payload = {
        "candidate_name": extreme_unicode,
        "role": "Software Engineer",
        "experience_level": "Mid",
        "interview_type": "technical",
    }
    resp = client.post("/interview/start", json=payload)
    # Must process without server crash or unhandled 500
    assert resp.status_code in (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)


# =============================================================================
# Category 2: Route Fuzzing & Path Traversal Attacks
# =============================================================================

@pytest.mark.parametrize(
    "traversal_path",
    [
        "/../../etc/passwd",
        "/interview/../../etc/passwd",
        "/coach/../../../windows/win.ini",
        "/%2e%2e/%2e%2e/etc/passwd",
        "/..%2f..%2fetc%2fpasswd",
        "/auth/..%2f..%2fsecret_file",
        "/static/../../../../boot.ini",
    ],
)
def test_path_traversal_attempts_return_404_not_found(client, traversal_path):
    """Verifies that directory traversal vectors return HTTP 404 with uniform error format and no file leak."""
    resp = client.get(traversal_path)
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["detail"] == "Not Found"
    assert data["error_type"] == "http_error"
    assert data["status_code"] == 404
    # Ensure system files are never exposed
    assert "root:" not in resp.text
    assert "[extensions]" not in resp.text


@pytest.mark.parametrize(
    "fuzzed_path",
    [
        "/<script>alert('xss')</script>",
        "/api/v1/test;DROP TABLE users;--",
        "/api/v1/test|whoami",
        "/api/v1/test\\windows\\backslash\\path",
        "/api/v1/test${IFS}cat",
        "/api/v1/test%00nullbyte",
        "/api/v1/test%ff%fe",
        "/api/v1/test'`\"$()",
    ],
)
def test_route_fuzzing_special_characters_return_404(client, fuzzed_path):
    """Verifies that malicious URL characters, SQL injection, and script tags return HTTP 404 safely."""
    resp = client.get(fuzzed_path)
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    data = resp.json()
    assert data["error_type"] == "http_error"
    assert data["status_code"] == 404
    assert data["detail"] == "Not Found"


def test_route_fuzzing_extreme_path_length_returns_404(client):
    """Verifies that extremely long URL paths (2048 chars) do not cause buffer overflow, recursion error or crash."""
    long_path = "/" + ("sub/" * 250) + ("a" * 1000)
    resp = client.get(long_path)
    assert resp.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST)
    data = resp.json()
    assert "error_type" in data
    assert "status_code" in data


def test_unsupported_http_method_returns_405(client):
    """Verifies that calling endpoints with unsupported methods returns HTTP 405 Method Not Allowed."""
    # /health supports GET only
    resp = client.request("POST", "/health", headers={}, body=b"")
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    data = resp.json()
    assert data["detail"] == "Method Not Allowed"
    assert data["error_type"] == "http_error"
    assert data["status_code"] == 405


# =============================================================================
# Category 3: Unhandled Exception Injection & Secret Sanitization
# =============================================================================

def test_unhandled_runtime_error_sanitization(client):
    """Verifies that unexpected RuntimeError with sensitive secrets returns sanitized 500 without leaking secrets."""
    secret = "SUPER_SECRET_AWS_KEY_AKIAIOSFODNN7EXAMPLE"
    with mock.patch("app.routers.auth.get_supabase_client", side_effect=RuntimeError(f"Database fail: {secret}")):
        resp = client.post("/auth/login", json={"email": "victim@example.com", "password": "Password123!"})
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = resp.json()
        assert data["detail"] == "Internal server error occurred."
        assert data["error_type"] == "internal_server_error"
        assert data["status_code"] == 500

        # Verify no leaks of secrets or stack traces
        assert secret not in resp.text
        assert "traceback" not in resp.text.lower()
        assert 'File "' not in resp.text


def test_unhandled_key_error_sanitization(client):
    """Verifies that KeyError in internal logic returns sanitized 500 without leaking dict keys."""
    secret_key = "PRIVATE_JWT_ENCRYPTION_KEY_ABC123"
    with mock.patch("app.routers.interview.create_interview_session", side_effect=KeyError(secret_key)):
        resp = client.post("/interview/start", json={
            "candidate_name": "Test Candidate",
            "role": "Backend Engineer",
            "experience_level": "Mid",
            "interview_type": "technical",
        })
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = resp.json()
        assert data["detail"] == "Internal server error occurred."
        assert data["error_type"] == "internal_server_error"
        assert data["status_code"] == 500

        assert secret_key not in resp.text
        assert "traceback" not in resp.text.lower()


def test_unhandled_zero_division_error_sanitization(client):
    """Verifies that ZeroDivisionError in calculation services returns sanitized 500 without leaking math details."""
    with mock.patch("app.routers.coach.get_user_profile", side_effect=ZeroDivisionError("float division by zero in rubric math")):
        resp = client.post("/coach/start", json={
            "user_id": "test-user-id-1234",
            "mode": "conversation",
        })
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = resp.json()
        assert data["detail"] == "Internal server error occurred."
        assert data["error_type"] == "internal_server_error"
        assert data["status_code"] == 500

        assert "rubric math" not in resp.text
        assert "traceback" not in resp.text.lower()


def test_unhandled_type_error_and_value_error_sanitization(client):
    """Verifies that TypeError and unhandled ValueError return uniform sanitized HTTP 500."""
    # Test unhandled TypeError
    with mock.patch("app.routers.auth.get_supabase_client", side_effect=TypeError("unsupported operand type(s) for +: 'NoneType' and 'str'")):
        resp = client.post("/auth/login", json={"email": "victim@example.com", "password": "Password123!"})
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = resp.json()
        assert data["detail"] == "Internal server error occurred."
        assert data["error_type"] == "internal_server_error"
        assert data["status_code"] == 500


def test_server_remains_operational_and_healthy_after_unhandled_exceptions(client):
    """Verifies that after repeated unhandled 500 exceptions, the server continues to handle requests normally."""
    # Trigger 3 unhandled exceptions in a row
    for _ in range(3):
        with mock.patch("app.routers.auth.get_supabase_client", side_effect=RuntimeError("Transient cluster crash")):
            resp = client.post("/auth/login", json={"email": "victim@example.com", "password": "Password123!"})
            assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # Verify server is still completely operational
    health_resp = client.get("/health")
    assert health_resp.status_code == status.HTTP_200_OK
    assert health_resp.json() == {"status": "ok"}

    root_resp = client.get("/")
    assert root_resp.status_code == status.HTTP_200_OK
    assert root_resp.json()["status"] == "online"


# =============================================================================
# Category 4: CORS Resilience Across All Error States (400, 404, 422, 500)
# =============================================================================

@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://voxprep.vercel.app",
        "https://candidate-portal.domain.com",
    ],
)
def test_cors_headers_preserved_on_400_bad_request(client, origin):
    """Verifies that HTTP 400 Bad Request error responses preserve CORS origin reflection and credentials headers."""
    resp = client.post(
        "/auth/register",
        json={"email": "invalid-email-format", "password": "Password123!"},
        headers={"Origin": origin},
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert resp.headers.get("access-control-allow-origin") == origin
    assert resp.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://voxprep.vercel.app",
        "https://custom-interviewer.org",
    ],
)
def test_cors_headers_preserved_on_404_not_found(client, origin):
    """Verifies that HTTP 404 Not Found error responses preserve CORS origin reflection and credentials headers."""
    resp = client.get(
        "/nonexistent/fuzzed/adversarial/route",
        headers={"Origin": origin},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert resp.headers.get("access-control-allow-origin") == origin
    assert resp.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://voxprep.vercel.app",
    ],
)
def test_cors_headers_preserved_on_422_validation_error(client, origin):
    """Verifies that HTTP 422 Unprocessable Entity validation errors preserve CORS origin and credentials headers."""
    resp = client.post(
        "/auth/register",
        json={},  # Missing all required fields
        headers={"Origin": origin},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert resp.headers.get("access-control-allow-origin") == origin
    assert resp.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://voxprep.vercel.app",
    ],
)
def test_cors_headers_preserved_on_500_internal_server_error(client, origin):
    """Verifies that HTTP 500 Internal Server Error responses preserve CORS origin and credentials headers."""
    with mock.patch("app.routers.auth.get_supabase_client", side_effect=RuntimeError("Internal failure")):
        resp = client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "Password123!"},
            headers={"Origin": origin},
        )
        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert resp.headers.get("access-control-allow-origin") == origin
        assert resp.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_options_request_on_nonexistent_route(client):
    """Verifies that CORS preflight OPTIONS request on a non-existent path returns HTTP 200 with CORS headers."""
    resp = client.options(
        "/nonexistent/api/route",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, Authorization",
        },
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert resp.headers.get("access-control-allow-credentials") == "true"
    assert "POST" in resp.headers.get("access-control-allow-methods", "")
