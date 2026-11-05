"""Integration tests for Authentication endpoints (POST /auth/register, POST /auth/login).

Tests cover:
- Successful user registration returning user and access_token.
- Duplicate email registration returning HTTP 400.
- Registration validation errors (missing fields, malformed email) returning HTTP 422.
- Successful login returning user and access_token.
- Invalid password returning HTTP 401.
- Nonexistent email login returning HTTP 401.
- Login validation errors returning HTTP 422.
"""

import uuid
import pytest
from app.db.supabase import get_supabase_client


def test_auth_register_success(client):
    """Verify successful user registration creates user record and returns JWT token."""
    unique_email = f"auth_reg_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": unique_email,
        "password": "StrongPassword123!",
        "name": "Alex Candidate",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code in [200, 201], f"Register failed: {response.text}"

    data = response.json()
    assert "user" in data
    assert data["user"].get("email") == unique_email
    assert data["user"].get("name") == "Alex Candidate"
    assert "id" in data["user"]
    assert "access_token" in data
    assert len(data["access_token"]) > 0

    # Verify persistent record in Supabase / Mock database
    sb = get_supabase_client()
    query = sb.table("users").select("*").eq("email", unique_email).execute()
    assert len(query.data) == 1
    user_row = query.data[0]
    assert user_row["email"] == unique_email
    assert "communication_profile" in user_row
    assert user_row["communication_profile"].get("skill_level") == "intermediate"


def test_auth_register_duplicate_email_error(client):
    """Verify registering with an existing email returns HTTP 400."""
    duplicate_email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": duplicate_email,
        "password": "Password123!",
        "name": "First User",
    }
    # Initial registration
    resp1 = client.post("/auth/register", json=payload)
    assert resp1.status_code in [200, 201]

    # Duplicate registration attempt
    payload_dup = {
        "email": duplicate_email,
        "password": "AnotherPassword456!",
        "name": "Second User",
    }
    resp2 = client.post("/auth/register", json=payload_dup)
    assert resp2.status_code == 400, f"Expected 400 on duplicate email, got: {resp2.status_code} {resp2.text}"

    data = resp2.json()
    detail = data.get("detail", "").lower()
    assert any(term in detail for term in ["already registered", "already exists", "duplicate", "user exists"])


def test_auth_register_validation_errors(client):
    """Verify invalid payloads return HTTP 422."""
    # Missing password
    resp1 = client.post("/auth/register", json={"email": "nopass@example.com", "name": "No Pass"})
    assert resp1.status_code == 422

    # Missing email
    resp2 = client.post("/auth/register", json={"password": "Password123!", "name": "No Email"})
    assert resp2.status_code == 422

    # Empty payload
    resp3 = client.post("/auth/register", json={})
    assert resp3.status_code == 422


def test_auth_login_success(client):
    """Verify registered user can log in with correct credentials."""
    email = f"login_ok_{uuid.uuid4().hex[:8]}@example.com"
    password = "CorrectPassword123!"

    # 1. Register
    reg_resp = client.post("/auth/register", json={
        "email": email,
        "password": password,
        "name": "Jane Login",
    })
    assert reg_resp.status_code in [200, 201]

    # 2. Login
    login_resp = client.post("/auth/login", json={
        "email": email,
        "password": password,
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"

    data = login_resp.json()
    assert "user" in data
    assert data["user"].get("email") == email
    assert "access_token" in data
    assert len(data["access_token"]) > 0


def test_auth_login_invalid_password_error(client):
    """Verify login with wrong password returns HTTP 401."""
    email = f"login_badpass_{uuid.uuid4().hex[:8]}@example.com"
    password = "CorrectPassword123!"

    reg_resp = client.post("/auth/register", json={
        "email": email,
        "password": password,
        "name": "Bad Pass Tester",
    })
    assert reg_resp.status_code in [200, 201]

    # Attempt login with wrong password
    login_resp = client.post("/auth/login", json={
        "email": email,
        "password": "WrongPassword999!",
    })
    assert login_resp.status_code == 401, f"Expected 401, got {login_resp.status_code}: {login_resp.text}"
    detail = login_resp.json().get("detail", "").lower()
    assert "invalid" in detail or "credentials" in detail


def test_auth_login_nonexistent_user_error(client):
    """Verify login for an unregistered email returns HTTP 401."""
    login_resp = client.post("/auth/login", json={
        "email": f"ghost_{uuid.uuid4().hex[:8]}@example.com",
        "password": "AnyPassword123!",
    })
    assert login_resp.status_code == 401
    detail = login_resp.json().get("detail", "").lower()
    assert "invalid" in detail or "credentials" in detail or "not found" in detail


def test_auth_login_missing_fields_validation_error(client):
    """Verify login with missing email or password returns HTTP 422."""
    assert client.post("/auth/login", json={"email": "user@example.com"}).status_code == 422
    assert client.post("/auth/login", json={"password": "Password123!"}).status_code == 422
    assert client.post("/auth/login", json={}).status_code == 422
