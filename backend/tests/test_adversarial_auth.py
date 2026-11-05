"""Adversarial Stress Test Suite for VOXPREP Authentication and Database Resilience.

Milestone 1 Verification & Stress Testing:
1. Malformed and Boundary Inputs:
   - SQL Injection strings in email/password fields
   - Unicode, emoji, and international characters in name and email
   - Extreme length strings (10,000 char passwords/emails)
   - Missing required fields, extra unrecognized fields, incorrect data types
2. Case Sensitivity and Normalization:
   - Case-insensitive email uniqueness and login resolution
   - Whitespace stripping on emails and display names
3. Concurrency and Race Conditions:
   - Thread safety of concurrent registrations with identical email
   - Rapid sequential login attempts with wrong passwords
   - Multi-threaded distinct registrations
4. Security & Error Leaks:
   - Generic 401 on all login failures preventing user enumeration
   - No raw Python tracebacks or stack leaks on malformed payloads
   - Absence of password exposure in response models and public users table
   - Disallowed HTTP methods rejected with 405
"""

import concurrent.futures
import json
import uuid
from typing import Any, Dict, List
import pytest

from app.db.supabase import get_supabase_client
from tests.conftest import LocalClient
from app.main import app


# =============================================================================
# 1. MALFORMED AND BOUNDARY INPUTS
# =============================================================================

class TestMalformedAndBoundaryInputs:
    """Aggressively tests boundary values, malformed inputs, SQL injection vectors,
    extreme lengths, and data type violations."""

    def test_sql_injection_in_registration_email(self, client):
        """Challenge: Attempt SQL injection vectors in email field during registration.
        
        Must either be rejected (HTTP 400 for bad email format) or stored literally
        without executing SQL or corrupting the backend.
        """
        sqli_emails = [
            "' OR '1'='1",
            "admin'--",
            "'; DROP TABLE users; --",
            "' UNION SELECT * FROM users--",
        ]

        # Vectors without '@' must be rejected with HTTP 400
        for payload in sqli_emails:
            res = client.post("/auth/register", json={
                "email": payload,
                "password": "Password123!",
                "name": "Attacker",
            })
            assert res.status_code == 400, f"Expected 400 for {payload}, got {res.status_code}"
            assert "email" in res.json().get("detail", "").lower()

        # Vector with '@' to pass basic email validation: must be treated as literal string
        safe_sqli_email = f"attacker_{uuid.uuid4().hex[:6]}'or'1'='1@example.com"
        res_valid = client.post("/auth/register", json={
            "email": safe_sqli_email,
            "password": "Password123!",
            "name": "Safe Attacker",
        })
        assert res_valid.status_code in [200, 201]
        data = res_valid.json()
        assert data["user"]["email"] == safe_sqli_email.lower()

        # Verify literal persistence in database without SQL execution
        sb = get_supabase_client()
        query = sb.table("users").select("*").eq("email", safe_sqli_email.lower()).execute()
        assert len(query.data) == 1
        assert query.data[0]["email"] == safe_sqli_email.lower()

    def test_sql_injection_in_login(self, client):
        """Challenge: Attempt authentication bypass via SQL injection in login credentials."""
        sqli_attempts = [
            {"email": "' OR '1'='1", "password": "' OR '1'='1"},
            {"email": "admin'--@example.com", "password": "' OR 1=1--"},
            {"email": "demo@voxprep.ai' OR '1'='1", "password": "Password123!"},
            {"email": "demo@voxprep.ai", "password": "' OR '1'='1"},
            {"email": "'; DROP TABLE users; --@example.com", "password": "bad"},
        ]

        for creds in sqli_attempts:
            res = client.post("/auth/login", json=creds)
            assert res.status_code == 401, f"Expected 401 for SQLi payload {creds}, got {res.status_code}"
            detail = res.json().get("detail", "")
            assert detail == "Invalid email or password", f"Expected generic error, got {detail}"

    def test_unicode_and_emojis_in_name_and_email(self, client):
        """Challenge: Unicode, emojis, diacritics, and RTL scripts in user name and email."""
        test_cases = [
            ("Jane 👩‍💻 Doe 🚀", f"jane_{uuid.uuid4().hex[:6]}@example.com"),
            ("René François d'Artagnan", f"rene_{uuid.uuid4().hex[:6]}@example.fr"),
            ("李小龙 (Bruce Lee)", f"bruce_{uuid.uuid4().hex[:6]}@example.cn"),
            ("أحمد محمد", f"ahmed_{uuid.uuid4().hex[:6]}@example.ae"),
            ("ユーザー名", f"user_{uuid.uuid4().hex[:6]}@example.jp"),
            ("Candidate with <script>alert('xss')</script>", f"xss_{uuid.uuid4().hex[:6]}@example.com"),
        ]

        for name, email in test_cases:
            res = client.post("/auth/register", json={
                "email": email,
                "password": "Password123!",
                "name": name,
            })
            assert res.status_code in [200, 201], f"Failed to register with name {name}: {res.text}"
            data = res.json()
            assert data["user"]["name"] == name.strip()
            assert data["user"]["email"] == email.lower()

            # Verify login retains display name
            login_res = client.post("/auth/login", json={
                "email": email,
                "password": "Password123!",
            })
            assert login_res.status_code == 200
            assert login_res.json()["user"]["name"] == name.strip()

    def test_extreme_length_password(self, client):
        """Challenge: Passwords with extreme lengths (10,000 characters)."""
        long_password = "P@" + ("a" * 9996) + "1!"
        email = f"longpass_{uuid.uuid4().hex[:8]}@example.com"

        # 1. Register with 10,000 char password
        res = client.post("/auth/register", json={
            "email": email,
            "password": long_password,
            "name": "Long Password User",
        })
        assert res.status_code in [200, 201], f"Failed extreme password registration: {res.text}"

        # 2. Login with correct 10,000 char password
        login_res = client.post("/auth/login", json={
            "email": email,
            "password": long_password,
        })
        assert login_res.status_code == 200
        assert login_res.json()["user"]["email"] == email

        # 3. Login with wrong extreme password
        wrong_long_password = long_password[:-1] + "X"
        bad_login = client.post("/auth/login", json={
            "email": email,
            "password": wrong_long_password,
        })
        assert bad_login.status_code == 401
        assert bad_login.json().get("detail") == "Invalid email or password"

    def test_extreme_length_email(self, client):
        """Challenge: Extremely long email addresses (>10,000 characters)."""
        extreme_email = ("e" * 10000) + "@example.com"
        res = client.post("/auth/register", json={
            "email": extreme_email,
            "password": "Password123!",
        })
        # Server must handle gracefully without crashing (either 201 or 400/422, never 500)
        assert res.status_code in [201, 400, 422]
        assert res.status_code != 500

    def test_password_length_boundary(self, client):
        """Challenge: Password min_length=6 boundary enforcement."""
        email = f"pw_bound_{uuid.uuid4().hex[:8]}@example.com"

        # Under boundary: 5 characters -> 422 Unprocessable Entity
        res_under = client.post("/auth/register", json={
            "email": email,
            "password": "12345",
            "name": "Under Boundary",
        })
        assert res_under.status_code == 422

        # Exact boundary: 6 characters -> accepted
        res_exact = client.post("/auth/register", json={
            "email": email,
            "password": "123456",
            "name": "Exact Boundary",
        })
        assert res_exact.status_code in [200, 201]

    def test_missing_required_fields(self, client):
        """Challenge: Payloads with missing mandatory fields return HTTP 422."""
        cases = [
            ("/auth/register", {"name": "No Email or Password"}),
            ("/auth/register", {"email": "no_pw@example.com"}),
            ("/auth/register", {"password": "Password123!"}),
            ("/auth/register", {}),
            ("/auth/login", {"email": "no_pw@example.com"}),
            ("/auth/login", {"password": "Password123!"}),
            ("/auth/login", {}),
        ]
        for endpoint, payload in cases:
            res = client.post(endpoint, json=payload)
            assert res.status_code == 422, f"Expected 422 for {endpoint} with {payload}, got {res.status_code}"

    def test_incorrect_field_types(self, client):
        """Challenge: Payloads with wrong types (lists, dicts, booleans) instead of strings."""
        invalid_type_payloads = [
            {"email": ["user@example.com"], "password": "Password123!"},
            {"email": {"email": "user@example.com"}, "password": "Password123!"},
            {"email": "user@example.com", "password": ["Password123!"]},
            {"email": "user@example.com", "password": {"secret": "Password123!"}},
            {"email": None, "password": "Password123!"},
            {"email": "user@example.com", "password": None},
        ]
        for payload in invalid_type_payloads:
            res_reg = client.post("/auth/register", json=payload)
            assert res_reg.status_code == 422, f"Register expected 422 for {payload}, got {res_reg.status_code}"

            res_log = client.post("/auth/login", json=payload)
            assert res_log.status_code == 422, f"Login expected 422 for {payload}, got {res_log.status_code}"

    def test_extra_unrecognized_fields(self, client):
        """Challenge: Payloads with extra unrecognized and privilege escalation fields."""
        email = f"extra_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "email": email,
            "password": "Password123!",
            "name": "Extra Fields User",
            "is_admin": True,
            "role": "superadmin",
            "access_level": 999,
            "communication_profile": {"skill_level": "advanced", "hack": True},
        }
        res = client.post("/auth/register", json=payload)
        assert res.status_code in [200, 201]
        data = res.json()
        assert "is_admin" not in data["user"]
        assert "role" not in data["user"]

        # Verify DB record was seeded safely
        sb = get_supabase_client()
        row = sb.table("users").select("*").eq("email", email).single().execute().data
        assert row is not None
        assert row.get("role") is None


# =============================================================================
# 2. CASE SENSITIVITY AND NORMALIZATION
# =============================================================================

class TestCaseSensitivityAndNormalization:
    """Stress-tests email casing, uniqueness across upper/lower variations,
    and whitespace stripping."""

    def test_email_case_insensitivity_duplicate_registration(self, client):
        """Challenge: Attempt duplicate registration with alternating casing.
        
        Registering User@Example.COM must block user@example.com, USER@EXAMPLE.COM,
        and uSeR@eXaMpLe.CoM with HTTP 400.
        """
        base = f"case_{uuid.uuid4().hex[:8]}"
        primary_email = f"{base}@Example.COM"

        # 1. Register with mixed casing
        res1 = client.post("/auth/register", json={
            "email": primary_email,
            "password": "Password123!",
            "name": "Case User",
        })
        assert res1.status_code in [200, 201]
        # Returned email must be normalized to lowercase
        assert res1.json()["user"]["email"] == primary_email.lower()

        # 2. Duplicate registration attempts with different casing
        variants = [
            f"{base}@example.com",
            f"{base.upper()}@EXAMPLE.COM",
            f"{base.capitalize()}@Example.Com",
        ]
        for variant in variants:
            res_dup = client.post("/auth/register", json={
                "email": variant,
                "password": "AnotherPassword456!",
                "name": "Impostor",
            })
            assert res_dup.status_code == 400, (
                f"Expected 400 duplicate error for variant '{variant}', got {res_dup.status_code}"
            )
            detail = res_dup.json().get("detail", "").lower()
            assert any(t in detail for t in ["already", "registered", "exists"])

    def test_email_case_insensitivity_login(self, client):
        """Challenge: User registers with uppercase email and logs in with lowercase or mixed casing."""
        base = f"caselogin_{uuid.uuid4().hex[:8]}"
        registered_email = f"{base.upper()}@DOMAIN.ORG"
        password = "CasePassword123!"

        res_reg = client.post("/auth/register", json={
            "email": registered_email,
            "password": password,
            "name": "Case Login User",
        })
        assert res_reg.status_code in [200, 201]

        # Login with lowercase
        res_lower = client.post("/auth/login", json={
            "email": registered_email.lower(),
            "password": password,
        })
        assert res_lower.status_code == 200
        assert res_lower.json()["user"]["email"] == registered_email.lower()

        # Login with mixed case
        mixed_email = f"{base.capitalize()}@Domain.Org"
        res_mixed = client.post("/auth/login", json={
            "email": mixed_email,
            "password": password,
        })
        assert res_mixed.status_code == 200
        assert res_mixed.json()["user"]["email"] == registered_email.lower()

    def test_email_whitespace_stripping(self, client):
        """Challenge: Leading and trailing whitespaces, tabs, and newlines in email."""
        base = f"whitespace_{uuid.uuid4().hex[:8]}@example.com"
        padded_email = f"  \t  {base}  \n  "
        password = "WhitespacePassword123!"

        # Register with padded email
        res = client.post("/auth/register", json={
            "email": padded_email,
            "password": password,
            "name": "Whitespace Tester",
        })
        assert res.status_code in [200, 201]
        assert res.json()["user"]["email"] == base

        # Verify DB store contains stripped email
        sb = get_supabase_client()
        row = sb.table("users").select("*").eq("email", base).single().execute().data
        assert row is not None
        assert row["email"] == base

        # Login with padded email
        login_padded = client.post("/auth/login", json={
            "email": f"   {base}   ",
            "password": password,
        })
        assert login_padded.status_code == 200

        # Login with unpadded email
        login_clean = client.post("/auth/login", json={
            "email": base,
            "password": password,
        })
        assert login_clean.status_code == 200

    def test_name_whitespace_and_fallback(self, client):
        """Challenge: Whitespace trimming on user display name and default fallback."""
        # 1. Padded name gets stripped
        email1 = f"namepad_{uuid.uuid4().hex[:8]}@example.com"
        res1 = client.post("/auth/register", json={
            "email": email1,
            "password": "Password123!",
            "name": "   Dr. John Watson   ",
        })
        assert res1.status_code in [200, 201]
        assert res1.json()["user"]["name"] == "Dr. John Watson"

        # 2. Omitted name defaults to Candidate
        email2 = f"name_omit_{uuid.uuid4().hex[:8]}@example.com"
        res2 = client.post("/auth/register", json={
            "email": email2,
            "password": "Password123!",
        })
        assert res2.status_code in [200, 201]
        assert res2.json()["user"]["name"] == "Candidate"

        # 3. None name defaults to Candidate
        email3 = f"name_none_{uuid.uuid4().hex[:8]}@example.com"
        res3 = client.post("/auth/register", json={
            "email": email3,
            "password": "Password123!",
            "name": None,
        })
        assert res3.status_code in [200, 201]
        assert res3.json()["user"]["name"] == "Candidate"


# =============================================================================
# 3. CONCURRENCY AND RACE CONDITIONS
# =============================================================================

class TestConcurrencyAndRaceConditions:
    """Stress-tests multi-threaded registration race conditions, thread safety
    of MockAuth and MockTableQuery, and rapid sequential brute-force attempts."""

    def test_concurrent_registration_same_email(self):
        """Challenge: 15 concurrent threads simultaneously attempt to register the SAME email.
        
        Thread safety invariant:
        - Exactly ONE thread must succeed with HTTP 201.
        - Exactly 14 threads must be rejected with HTTP 400.
        - ZERO unhandled exceptions or 500 internal server errors.
        - Supabase users table must contain exactly ONE record for this email.
        """
        target_email = f"race_{uuid.uuid4().hex[:8]}@example.com"
        password = "RacePassword123!"
        concurrency = 15

        def register_worker(worker_id: int) -> int:
            client = LocalClient(app)
            resp = client.post("/auth/register", json={
                "email": target_email,
                "password": password,
                "name": f"Worker-{worker_id}",
            })
            return resp.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(register_worker, i) for i in range(concurrency)]
            status_codes = [f.result() for f in futures]

        success_count = status_codes.count(201) + status_codes.count(200)
        duplicate_count = status_codes.count(400)
        error_count = [c for c in status_codes if c not in [200, 201, 400]]

        assert success_count == 1, (
            f"Race condition! Expected exactly 1 registration success, got {success_count}. "
            f"Status distribution: {status_codes}"
        )
        assert duplicate_count == concurrency - 1, (
            f"Expected {concurrency - 1} duplicates with 400, got {duplicate_count}"
        )
        assert len(error_count) == 0, f"Unexpected error status codes: {error_count}"

        # Invariant: exactly 1 user in MockTableQuery store
        sb = get_supabase_client()
        query = sb.table("users").select("*").eq("email", target_email).execute()
        assert len(query.data) == 1, f"Expected 1 user in table, found {len(query.data)}"

    def test_rapid_sequential_login_attempts_wrong_password(self, client):
        """Challenge: 30 rapid sequential failed login attempts.
        
        Verifies:
        - All 30 attempts return HTTP 401 with generic error.
        - Server does not lock up, crash, or enter corrupted state.
        - Subsequent valid login succeeds immediately with HTTP 200.
        """
        email = f"brute_{uuid.uuid4().hex[:8]}@example.com"
        correct_password = "CorrectPassword123!"

        # Register user
        reg_res = client.post("/auth/register", json={
            "email": email,
            "password": correct_password,
            "name": "Brute Force Target",
        })
        assert reg_res.status_code in [200, 201]

        # 30 rapid failed login attempts
        for i in range(30):
            bad_login = client.post("/auth/login", json={
                "email": email,
                "password": f"WrongPass_{i}_!@#",
            })
            assert bad_login.status_code == 401
            assert bad_login.json().get("detail") == "Invalid email or password"

        # 31st login with correct credentials succeeds
        good_login = client.post("/auth/login", json={
            "email": email,
            "password": correct_password,
        })
        assert good_login.status_code == 200
        assert good_login.json()["user"]["email"] == email

    def test_concurrent_different_user_registrations(self):
        """Challenge: 15 concurrent threads registering 15 distinct unique emails.
        
        Verifies MockSupabaseClient store and MockAuth withstand high concurrent write traffic.
        """
        concurrency = 15
        emails = [f"multi_{i}_{uuid.uuid4().hex[:6]}@example.com" for i in range(concurrency)]

        def register_distinct(idx: int) -> int:
            client = LocalClient(app)
            resp = client.post("/auth/register", json={
                "email": emails[idx],
                "password": "Password123!",
                "name": f"User-{idx}",
            })
            return resp.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(register_distinct, i) for i in range(concurrency)]
            status_codes = [f.result() for f in futures]

        assert all(c in [200, 201] for c in status_codes), (
            f"Some concurrent distinct registrations failed: {status_codes}"
        )

        sb = get_supabase_client()
        for email in emails:
            res = sb.table("users").select("id").eq("email", email).execute()
            assert len(res.data) == 1


# =============================================================================
# 4. SECURITY & ERROR LEAKS
# =============================================================================

class TestSecurityAndErrorLeaks:
    """Stress-tests information leakage, user enumeration prevention,
    traceback suppression on unhandled exceptions, and password exposure."""

    def test_generic_401_on_all_login_failures(self, client):
        """Challenge: User enumeration prevention.
        
        Login failure responses must return the EXACT same HTTP status code (401)
        and error message ('Invalid email or password') regardless of whether:
        1. The email does not exist.
        2. The email exists but password is wrong.
        3. The email is malformed (no '@').
        4. The password is empty or garbage.
        """
        # Create an existing user
        registered_email = f"enum_target_{uuid.uuid4().hex[:8]}@example.com"
        client.post("/auth/register", json={
            "email": registered_email,
            "password": "TargetPassword123!",
            "name": "Enum Target",
        })

        failure_scenarios = [
            # 1. Non-existent email
            {"email": f"nonexistent_{uuid.uuid4().hex[:8]}@example.com", "password": "TargetPassword123!"},
            # 2. Existing email, wrong password
            {"email": registered_email, "password": "WrongPassword999!"},
            # 3. Malformed email without '@'
            {"email": "notanemail", "password": "TargetPassword123!"},
            # 4. Empty email string
            {"email": "", "password": "TargetPassword123!"},
        ]

        expected_detail = "Invalid email or password"

        for creds in failure_scenarios:
            res = client.post("/auth/login", json=creds)
            assert res.status_code == 401, (
                f"Expected 401 for {creds}, got {res.status_code}: {res.text}"
            )
            detail = res.json().get("detail")
            assert detail == expected_detail, (
                f"Information leak! Detail was '{detail}' instead of '{expected_detail}' for {creds}"
            )

    def test_no_traceback_leakage_on_malformed_json(self, client):
        """Challenge: Malformed raw request bodies must never leak raw Python stack tracebacks."""
        malformed_bodies = [
            b"{{{invalid json payload",
            b"<xml><email>test@example.com</email></xml>",
            b"\x00\x01\x02\x03\xff\xfe binary garbage",
            b'{"email": "valid@example.com", "password": ',
        ]

        for body in malformed_bodies:
            for path in ["/auth/register", "/auth/login"]:
                res = client.request("POST", path, headers={"Content-Type": "application/json"}, body=body)
                assert res.status_code in [400, 422], (
                    f"Expected 400 or 422 for malformed body, got {res.status_code}"
                )
                # Ensure no stack trace or Python internal filename leaks
                text_lower = res.text.lower()
                assert "traceback (most recent call last)" not in text_lower
                assert '.py", line' not in text_lower
                assert "file \"" not in text_lower

    def test_no_password_exposure_in_models_or_database(self, client):
        """Challenge: Passwords must NEVER be returned in API response models
        or seeded into the public users table.
        """
        email = f"nopass_leak_{uuid.uuid4().hex[:8]}@example.com"
        secret_password = "SuperSecretPassword123!"

        # 1. Register
        res_reg = client.post("/auth/register", json={
            "email": email,
            "password": secret_password,
            "name": "Secret User",
        })
        assert res_reg.status_code in [200, 201]
        reg_data = res_reg.json()
        reg_text = res_reg.text

        # Verify password is NOT in response JSON text or user dict
        assert secret_password not in reg_text
        assert "password" not in reg_data["user"]

        # 2. Login
        res_login = client.post("/auth/login", json={
            "email": email,
            "password": secret_password,
        })
        assert res_login.status_code == 200
        login_data = res_login.json()
        login_text = res_login.text

        # Verify password is NOT in response JSON text or user dict
        assert secret_password not in login_text
        assert "password" not in login_data["user"]

        # 3. Database public users table check
        sb = get_supabase_client()
        user_row = sb.table("users").select("*").eq("email", email).single().execute().data
        assert user_row is not None
        assert "password" not in user_row, "Critical security vulnerability: password stored in public users table!"
        assert secret_password not in json.dumps(user_row)

    def test_disallowed_http_methods(self, client):
        """Challenge: Endpoints must reject disallowed HTTP methods with HTTP 405 Method Not Allowed."""
        disallowed = [
            ("GET", "/auth/register"),
            ("PUT", "/auth/register"),
            ("DELETE", "/auth/register"),
            ("GET", "/auth/login"),
            ("PUT", "/auth/login"),
            ("DELETE", "/auth/login"),
        ]

        for method, path in disallowed:
            res = client.request(method, path)
            assert res.status_code == 405, (
                f"Expected 405 Method Not Allowed for {method} {path}, got {res.status_code}"
            )
            assert "allow" in res.headers
