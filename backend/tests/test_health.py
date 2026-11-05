"""Unit tests for VOXPREP Backend health endpoint, root metadata, and CORS middleware."""


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
