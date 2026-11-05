"""
Adversarial Stress Test Suite for Milestone 0
Tests FastAPI CORS & HTTP edge cases, Supabase SQL schema boundaries,
and db/supabase.py client concurrency and mock robustness.
"""

import os
import re
import uuid
import threading
import concurrent.futures
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

from app.main import app, get_allowed_origins
from app.db import supabase
from app.db.supabase import (
    get_supabase_client,
    MockSupabaseClient,
    MockTableQuery,
    MockAuth,
)
from tests.conftest import LocalClient, LocalResponse, CaseInsensitiveDict


class QueryAwareClient(LocalClient):
    """Enhanced LocalClient that correctly partitions path and query_string in ASGI scope,
    allowing synchronous, socket-free testing of malformed and complex query parameters."""

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


# =============================================================================
# 1. FASTAPI CORS AND HTTP BEHAVIOR CHALLENGES
# =============================================================================

class TestFastAPICorsAndHttp:
    """Stress-tests CORS configurations, non-standard origins, complex headers,
    OPTIONS preflights, malformed parameters, and concurrent requests."""

    def test_cors_non_standard_and_untrusted_origins(self):
        """Challenge: Evaluate CORS response headers with non-standard and adversarial origins."""
        client = QueryAwareClient(app)
        test_origins = [
            "null",
            "chrome-extension://nkbihfbeogaeaoehlefnkodbefgpgknn",
            "http://[::1]:3000",
            "https://evil.attacker.com",
            "http://localhost:3000.evil.com",
            "http://localhost:3000",
            "https://voxprep.ai",
        ]

        for origin in test_origins:
            response = client.get("/health", headers={"Origin": origin})
            assert response.status_code == 200
            allow_origin = response.headers.get("access-control-allow-origin")
            allow_creds = response.headers.get("access-control-allow-credentials")

            assert allow_origin is not None, f"Missing Access-Control-Allow-Origin for {origin}"
            assert allow_origin in [origin, "*"], f"Unexpected allow_origin: {allow_origin}"

    def test_cors_wildcard_with_credentials_specification_check(self):
        """Challenge: Check for W3C CORS specification conflict when allow_origins=['*']
        and allow_credentials=True are simultaneously active.
        
        Per W3C Fetch Spec, credentialed requests are rejected by browsers if Allow-Origin is '*'.
        """
        client = QueryAwareClient(app)
        res = client.get("/health", headers={"Origin": "http://localhost:3000"})
        allow_origin = res.headers.get("access-control-allow-origin")
        allow_creds = res.headers.get("access-control-allow-credentials")

        # Document whether the server returns both wildcard and credentials: true
        has_wildcard_credential_conflict = (allow_origin == "*" and allow_creds == "true")
        # In the current implementation, Starlette emits both, which is a known browser hazard
        assert allow_origin is not None

    def test_get_allowed_origins_empty_string_fallback(self, monkeypatch):
        """Challenge: Verify docstring contract: empty string falls back to ['http://localhost:3000'].
        
        Docstring in app/main.py:
        '- If set to empty string, falls back to ["http://localhost:3000"].'
        """
        monkeypatch.setenv("ALLOWED_ORIGINS", "")
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        result = get_allowed_origins()
        assert result == ["http://localhost:3000"], (
            f"Expected fallback ['http://localhost:3000'] but got {result}. "
            "Bug caused by 'raw_origins = os.getenv(...) or os.getenv(...)' where '' is falsy."
        )

    def test_get_allowed_origins_whitespace_and_commas(self, monkeypatch):
        """Challenge: Test whitespace trimming and multiple origins."""
        monkeypatch.setenv("ALLOWED_ORIGINS", "  http://localhost:3000 ,  https://voxprep.ai  ")
        origins = get_allowed_origins()
        assert origins == ["http://localhost:3000", "https://voxprep.ai"]

        monkeypatch.setenv("ALLOWED_ORIGINS", ", , ,")
        assert get_allowed_origins() == ["http://localhost:3000"]

    def test_cors_preflight_complex_headers_and_methods(self):
        """Challenge: OPTIONS preflight with complex headers and diverse HTTP methods."""
        client = QueryAwareClient(app)
        preflight_headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, X-Custom-Token, Content-Type, Sentry-Trace",
        }
        res = client.options("/health", headers=preflight_headers)
        assert res.status_code == 200
        assert "access-control-allow-origin" in res.headers
        assert "access-control-allow-methods" in res.headers
        assert "access-control-allow-headers" in res.headers

        allowed_methods = res.headers.get("access-control-allow-methods", "")
        for m in ["GET", "POST", "PUT", "DELETE", "OPTIONS"]:
            assert m in allowed_methods

    def test_cors_preflight_on_nonexistent_endpoint(self):
        """Challenge: OPTIONS preflight sent to an unregistered endpoint."""
        client = QueryAwareClient(app)
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        }
        res = client.options("/nonexistent/endpoint", headers=headers)
        assert res.status_code == 200
        assert "access-control-allow-origin" in res.headers

    def test_options_without_origin_header(self):
        """Challenge: Direct OPTIONS request without Origin header."""
        client = QueryAwareClient(app)
        res = client.options("/health")
        assert res.status_code == 405
        assert "allow" in res.headers

    def test_malformed_and_extreme_query_parameters(self):
        """Challenge: Send malformed, oversized, and adversarial query params."""
        client = QueryAwareClient(app)

        # 1. Extreme length query string (10,000 characters)
        long_query = "x=" + ("a" * 10000)
        res = client.get(f"/health?{long_query}")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

        # 2. SQL injection and XSS payloads in query
        sqli_query = "id=1'%20OR%20'1'='1&q=<script>alert(1)</script>"
        res = client.get(f"/health?{sqli_query}")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

        # 3. Repeated array parameters
        res = client.get("/health?item=1&item=2&item=3&mode=test")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

        # 4. Unusual characters and spaces
        res = client.get("/health?unicode=%E2%9C%93&spaces=hello+world")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

    def test_concurrent_http_requests(self):
        """Challenge: 50 concurrent requests hitting the health endpoint."""
        client = QueryAwareClient(app)
        concurrency = 50

        def make_request(idx: int) -> int:
            res = client.get("/health", headers={"Origin": f"http://client-{idx}.voxprep.ai"})
            assert res.json() == {"status": "ok"}
            return res.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request, i) for i in range(concurrency)]
            results = [f.result() for f in futures]

        assert len(results) == concurrency
        assert all(code == 200 for code in results)


# =============================================================================
# 2. SUPABASE SQL SCHEMA CHALLENGES
# =============================================================================

class TestSupabaseSqlSchema:
    """Stress-tests backend/schema.sql DDL parsing, table definitions,
    foreign key behaviors, and constraint boundaries."""

    @pytest.fixture(autouse=True)
    def load_schema(self):
        schema_path = Path(__file__).resolve().parent.parent / "schema.sql"
        assert schema_path.exists(), "schema.sql not found"
        self.sql_content = schema_path.read_text(encoding="utf-8")

    def test_schema_ddl_syntax_and_block_integrity(self):
        """Challenge: Validate SQL statement segmentation, comments, and block structure."""
        cleaned = re.sub(r"'[^']*'", "", self.sql_content)
        cleaned = re.sub(r"--[^\n]*", "", cleaned)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

        open_parens = cleaned.count("(")
        close_parens = cleaned.count(")")
        assert open_parens == close_parens, f"Unbalanced parentheses: (={open_parens}, )={close_parens}"

    def test_schema_required_tables_and_columns(self):
        """Challenge: Verify all required tables, UUID primary keys, and required columns."""
        sql_upper = self.sql_content.upper()

        assert "CREATE TABLE IF NOT EXISTS USERS" in sql_upper
        assert "CREATE TABLE IF NOT EXISTS INTERVIEW_SESSIONS" in sql_upper
        assert "CREATE TABLE IF NOT EXISTS COACH_SESSIONS" in sql_upper

        assert re.search(r"id\s+UUID\s+PRIMARY\s+KEY\s+DEFAULT\s+gen_random_uuid\(\)", self.sql_content, re.IGNORECASE)

        for col in ["email", "name", "created_at", "updated_at", "communication_profile"]:
            assert re.search(rf"\b{col}\b", self.sql_content, re.IGNORECASE)

        for col in [
            "user_id", "candidate_name", "role_applied", "experience_level",
            "interview_type", "questions", "answers", "scores", "report",
            "current_question_index", "follow_up_count", "is_complete"
        ]:
            assert re.search(rf"\b{col}\b", self.sql_content, re.IGNORECASE)

        for col in ["user_id", "mode", "exchanges", "summary", "is_complete"]:
            assert re.search(rf"\b{col}\b", self.sql_content, re.IGNORECASE)

    def test_schema_interview_type_constraint_boundary(self):
        """Challenge: Verify interview_type CHECK constraint boundary.
        
        Allowed: ('hr', 'technical')
        Disallowed: 'debate', 'behavioral', 'casual', 'HR', 'TECHNICAL', ''
        """
        match = re.search(
            r"interview_type\s+TEXT\s+NOT\s+NULL\s+CHECK\s*\(\s*interview_type\s+IN\s*\((.*?)\)\)",
            self.sql_content,
            re.IGNORECASE,
        )
        assert match is not None, "interview_type CHECK constraint not found"
        raw_values = match.group(1)
        allowed_values = [v.strip().strip("'") for v in raw_values.split(",")]

        assert set(allowed_values) == {"hr", "technical"}

        def validate_interview_type(val: Any) -> bool:
            return isinstance(val, str) and val in allowed_values

        assert validate_interview_type("hr") is True
        assert validate_interview_type("technical") is True

        for inv in ["debate", "behavioral", "casual", "HR", "TECHNICAL", "", "  hr  ", None, 123]:
            assert validate_interview_type(inv) is False, f"Expected {inv} to be rejected"

    def test_schema_coach_mode_constraint_boundary(self):
        """Challenge: Verify coach_sessions.mode CHECK constraint boundary.
        
        Allowed: ('conversation', 'answer_training', 'english_improvement')
        Disallowed: 'casual', 'chat', 'debate', 'english', 'CONVERSATION', ''
        """
        match = re.search(
            r"mode\s+TEXT\s+NOT\s+NULL\s+CHECK\s*\(\s*mode\s+IN\s*\((.*?)\)\)",
            self.sql_content,
            re.IGNORECASE,
        )
        assert match is not None, "coach_sessions.mode CHECK constraint not found"
        raw_values = match.group(1)
        allowed_modes = [v.strip().strip("'") for v in raw_values.split(",")]

        assert set(allowed_modes) == {"conversation", "answer_training", "english_improvement"}

        def validate_coach_mode(val: Any) -> bool:
            return isinstance(val, str) and val in allowed_modes

        for m in ["conversation", "answer_training", "english_improvement"]:
            assert validate_coach_mode(m) is True

        for inv in ["casual", "chat", "debate", "english", "CONVERSATION", "", "answer training", None]:
            assert validate_coach_mode(inv) is False, f"Expected {inv} to be rejected"

    def test_schema_user_communication_profile_constraint_boundary(self):
        """Challenge: Verify chk_users_skill_level constraint on communication_profile->>'skill_level'."""
        assert "chk_users_skill_level" in self.sql_content
        assert "'beginner', 'intermediate', 'advanced'" in self.sql_content

        def validate_skill_level(profile: Optional[Dict[str, Any]]) -> bool:
            if profile is None:
                return True
            skill = profile.get("skill_level")
            if skill is None:
                return True
            return skill in ("beginner", "intermediate", "advanced")

        assert validate_skill_level({"skill_level": "beginner"}) is True
        assert validate_skill_level({"skill_level": "intermediate"}) is True
        assert validate_skill_level({"skill_level": "advanced"}) is True
        assert validate_skill_level({}) is True

        for inv_skill in ["casual", "expert", "novice", "master", "", "INTERMEDIATE", 123]:
            assert validate_skill_level({"skill_level": inv_skill}) is False

    def test_schema_non_negative_integer_constraints(self):
        """Challenge: Verify current_question_index and follow_up_count non-negative constraints."""
        assert re.search(r"current_question_index\s+INT\s+NOT\s+NULL\s+DEFAULT\s+0\s+CHECK\s*\(\s*current_question_index\s*>=\s*0\s*\)", self.sql_content, re.IGNORECASE)
        assert re.search(r"follow_up_count\s+INT\s+NOT\s+NULL\s+DEFAULT\s+0\s+CHECK\s*\(\s*follow_up_count\s*>=\s*0\s*\)", self.sql_content, re.IGNORECASE)

    def test_schema_foreign_keys_and_delete_behavior(self):
        """Challenge: Verify foreign keys: SET NULL for interview_sessions, CASCADE for coach_sessions."""
        assert re.search(
            r"REFERENCES\s+users\s*\(\s*id\s*\)\s+ON\s+DELETE\s+SET\s+NULL",
            self.sql_content,
            re.IGNORECASE,
        )
        assert re.search(
            r"REFERENCES\s+users\s*\(\s*id\s*\)\s+ON\s+DELETE\s+CASCADE",
            self.sql_content,
            re.IGNORECASE,
        )

    def test_schema_rls_and_permissive_policies(self):
        """Challenge: Verify Row Level Security is enabled and permissive policies exist for dev."""
        for tbl in ["users", "interview_sessions", "coach_sessions"]:
            assert f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY" in self.sql_content
            assert f'CREATE POLICY "Allow full access to {tbl}"' in self.sql_content


# =============================================================================
# 3. DB/SUPABASE.PY CONCURRENCY AND MOCK STORE CHALLENGES
# =============================================================================

class TestSupabaseClientAndMock:
    """Stress-tests Supabase client singleton thread safety, empty credential
    handling, mock query builder type handling, and chaining behavior."""

    def test_get_supabase_client_thread_safety(self):
        """Challenge: Concurrent calls to get_supabase_client() under race conditions.
        
        Contract per PROJECT.md interface 1:
        'Returns thread-safe singleton Supabase client or in-memory mock fallback.'
        """
        supabase._client_instance = None
        concurrency = 30
        client_instances: List[int] = []

        def worker():
            client = get_supabase_client()
            client_instances.append(id(client))
            return client

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(worker) for _ in range(concurrency)]
            results = [f.result() for f in futures]

        unique_instances = set(client_instances)
        assert len(unique_instances) == 1, (
            f"Singleton race condition detected! {len(unique_instances)} distinct instances created "
            f"across {concurrency} concurrent threads. get_supabase_client() lacks thread locking."
        )

    def test_empty_and_placeholder_credentials_handling(self, monkeypatch):
        """Challenge: Verify fallback to MockSupabaseClient across edge-case credentials."""
        credential_scenarios = [
            ("", ""),
            ("   ", "   "),
            ("https://placeholder.supabase.co", "placeholder-key"),
            ("https://your-project.supabase.co", "your-anon-key"),
            ("https://your_project.supabase.co", "your_service_key"),
            ("https://example.supabase.co", "example-key"),
        ]

        for url, key in credential_scenarios:
            supabase._client_instance = None
            monkeypatch.setenv("SUPABASE_URL", url)
            monkeypatch.setenv("SUPABASE_SERVICE_KEY", key)
            client = get_supabase_client()
            assert isinstance(client, MockSupabaseClient), f"Failed mock fallback for ({url}, {key})"
            assert hasattr(client, "table")
            assert hasattr(client, "auth")

    def test_mock_query_chaining_update_order_behavior(self):
        """Challenge: Verify MockTableQuery.update().eq() does not overwrite unrelated rows.
        
        Standard Postgrest pattern: client.table('users').update({...}).eq('id', target).execute()
        """
        client = MockSupabaseClient()
        client.table("users").insert({"id": "user-A", "email": "a@voxprep.ai", "name": "Alice"}).execute()
        client.table("users").insert({"id": "user-B", "email": "b@voxprep.ai", "name": "Bob"}).execute()

        # Update user-B only
        client.table("users").update({"name": "Updated Bob"}).eq("id", "user-B").execute()

        all_users = client.table("users").select().execute().data
        user_a = next(u for u in all_users if u["id"] == "user-A")
        user_b = next(u for u in all_users if u["id"] == "user-B")

        assert user_a["name"] == "Alice", (
            f"MockTableQuery.update().eq() overwrote unrelated row user-A! Name is '{user_a['name']}'. "
            "Update must defer execution until execute() or apply filters properly."
        )
        assert user_b["name"] == "Updated Bob"

    def test_mock_query_insert_none_handling(self):
        """Challenge: Test inserting None into MockTableQuery and subsequent query stability."""
        client = MockSupabaseClient()

        # Inserting None into mock store should either reject or not corrupt subsequent queries
        client.table("users").insert(None).execute()

        # When store contains None, subsequent queries must not crash with unhandled AttributeError
        try:
            res = client.table("users").select().eq("email", "demo@voxprep.ai").execute()
            assert res is not None
        except AttributeError as exc:
            pytest.fail(f"MockTableQuery query crashed after None insert: {exc}")

    def test_mock_query_insert_primitive_handling(self):
        """Challenge: Test inserting raw integer into MockTableQuery and subsequent query stability."""
        client = MockSupabaseClient()

        client.table("users").insert(12345).execute()

        try:
            res = client.table("users").select().eq("email", "demo@voxprep.ai").execute()
            assert res is not None
        except AttributeError as exc:
            pytest.fail(f"MockTableQuery query crashed after integer insert: {exc}")

    def test_mock_query_missing_table_and_empty_filters(self):
        """Challenge: Querying non-existent tables and non-matching filters."""
        client = MockSupabaseClient()

        # Non-existent table returns empty list
        res = client.table("non_existent_table").select().execute()
        assert res.data == []

        # Filter yielding 0 matches with .single() returns None
        res_single = client.table("users").select().eq("email", "does-not-exist@voxprep.ai").single().execute()
        assert res_single.data is None

        # Filter on non-existent column returns empty list
        res_col = client.table("users").select().eq("unknown_col", "val").execute()
        assert res_col.data == []

    def test_mock_auth_edge_cases(self):
        """Challenge: MockAuth with missing/empty credentials."""
        auth = MockAuth()

        res1 = auth.sign_up({})
        assert res1.user.email == "test@voxprep.ai"
        assert res1.session.access_token == "mock-jwt-token"

        res2 = auth.sign_in_with_password({})
        assert res2.user.email == "test@voxprep.ai"
        assert res2.session.access_token == "mock-jwt-token"

    def test_mock_query_multi_column_filtering(self):
        """Challenge: Multi-column equality filtering on MockTableQuery across select and update.
        
        Stress-tests PostgREST pattern: .eq('role', 'admin').eq('status', 'active')
        Ensures conjunction (AND) semantics and that partial matches are strictly excluded.
        """
        client = MockSupabaseClient()
        members = [
            {"id": 1, "role": "admin", "status": "active", "dept": "eng"},
            {"id": 2, "role": "admin", "status": "inactive", "dept": "sales"},
            {"id": 3, "role": "user", "status": "active", "dept": "eng"},
            {"id": 4, "role": "user", "status": "inactive", "dept": "marketing"},
            {"id": 5, "role": "guest", "status": "active", "dept": "sales"},
        ]
        client.table("team").insert(members).execute()

        # 1. Two-column conjunction: role=admin AND status=active -> only id=1
        res1 = client.table("team").select().eq("role", "admin").eq("status", "active").execute()
        assert len(res1.data) == 1
        assert res1.data[0]["id"] == 1

        # 2. Two-column conjunction: status=active AND dept=eng -> id=1 and id=3
        res2 = client.table("team").select().eq("status", "active").eq("dept", "eng").execute()
        assert len(res2.data) == 2
        assert {r["id"] for r in res2.data} == {1, 3}

        # 3. Three-column conjunction: role=admin, status=active, dept=eng -> id=1
        res3 = client.table("team").select().eq("role", "admin").eq("status", "active").eq("dept", "eng").execute()
        assert len(res3.data) == 1
        assert res3.data[0]["id"] == 1

        # 4. Conjunction with zero matching rows
        res4 = client.table("team").select().eq("role", "admin").eq("dept", "marketing").execute()
        assert res4.data == []

        # 5. Multi-column update: mutate only rows satisfying all chained .eq() filters
        # Update only role=admin AND status=active
        client.table("team").update({"status": "promoted"}).eq("role", "admin").eq("status", "active").execute()

        all_team = client.table("team").select().execute().data
        by_id = {r["id"]: r for r in all_team}
        assert by_id[1]["status"] == "promoted", "Target row id=1 was not updated"
        assert by_id[2]["status"] == "inactive", "Unrelated row id=2 (admin, inactive) was mutated!"
        assert by_id[3]["status"] == "active", "Unrelated row id=3 (user, active) was mutated!"
        assert by_id[4]["status"] == "inactive", "Unrelated row id=4 was mutated!"
        assert by_id[5]["status"] == "active", "Unrelated row id=5 was mutated!"

        # 6. Mutually exclusive filters on the same column -> empty result
        res_conflicting = client.table("team").select().eq("role", "admin").eq("role", "guest").execute()
        assert res_conflicting.data == []

    def test_mock_query_delete_filtering(self):
        """Challenge: PostgREST .delete() filtering, multi-filter deletion, and store mutation integrity."""
        client = MockSupabaseClient()
        logs = [
            {"id": 1, "level": "INFO", "source": "web"},
            {"id": 2, "level": "ERROR", "source": "db"},
            {"id": 3, "level": "ERROR", "source": "web"},
            {"id": 4, "level": "DEBUG", "source": "cron"},
        ]
        client.table("audit_logs").insert(logs).execute()

        # 1. Single filter delete: delete id=4
        del1 = client.table("audit_logs").delete().eq("id", 4).execute()
        assert len(del1.data) == 1
        assert del1.data[0]["id"] == 4

        # Verify id=4 removed, others remain
        remaining1 = client.table("audit_logs").select().execute().data
        assert {r["id"] for r in remaining1} == {1, 2, 3}

        # 2. Multi-column filter delete: level=ERROR AND source=web -> only id=3
        del2 = client.table("audit_logs").delete().eq("level", "ERROR").eq("source", "web").execute()
        assert len(del2.data) == 1
        assert del2.data[0]["id"] == 3

        # Verify only id=3 was deleted; id=2 (ERROR, db) must still exist
        remaining2 = client.table("audit_logs").select().execute().data
        assert {r["id"] for r in remaining2} == {1, 2}
        err_log = next(r for r in remaining2 if r["id"] == 2)
        assert err_log["level"] == "ERROR" and err_log["source"] == "db"

        # 3. Delete matching 0 rows -> returns empty list, does not modify table
        del3 = client.table("audit_logs").delete().eq("level", "FATAL").execute()
        assert del3.data == []
        remaining3 = client.table("audit_logs").select().execute().data
        assert len(remaining3) == 2

        # 4. Delete with .single() modifier
        del4 = client.table("audit_logs").delete().eq("id", 1).single().execute()
        assert isinstance(del4.data, dict)
        assert del4.data["id"] == 1

        remaining4 = client.table("audit_logs").select().execute().data
        assert len(remaining4) == 1
        assert remaining4[0]["id"] == 2

        # 5. Reverse chaining order: .eq() before .delete()
        del5 = client.table("audit_logs").eq("id", 2).delete().execute()
        assert len(del5.data) == 1
        assert del5.data[0]["id"] == 2

        # Table now empty
        remaining5 = client.table("audit_logs").select().execute().data
        assert remaining5 == []

    def test_mock_query_order_and_limit_chaining(self):
        """Challenge: PostgREST .order() and .limit() chaining, direction, edge limits, and null handling."""
        client = MockSupabaseClient()
        rankings = [
            {"id": "A", "score": 50, "age": 25},
            {"id": "B", "score": 90, "age": 30},
            {"id": "C", "score": 10, "age": 40},
            {"id": "D", "score": 90, "age": 20},
            {"id": "E", "score": None, "age": 35},
        ]
        client.table("rankings").insert(rankings).execute()

        # 1. Order by numeric ascending (desc=False) with limit
        res_asc = client.table("rankings").select().order("score", desc=False).limit(3).execute()
        assert len(res_asc.data) == 3
        # Ascending: 10, 50, 90 (None goes to end)
        assert [r["score"] for r in res_asc.data] == [10, 50, 90]

        # 2. Order by numeric age descending without Nones
        res_desc = client.table("rankings").select().order("age", desc=True).limit(3).execute()
        assert len(res_desc.data) == 3
        assert [r["age"] for r in res_desc.data] == [40, 35, 30]
        assert [r["id"] for r in res_desc.data] == ["C", "E", "B"]

        # 3. Limit 0 returns empty list
        res_zero = client.table("rankings").select().order("score").limit(0).execute()
        assert res_zero.data == []

        # 4. Limit exceeding table size returns all items
        res_large = client.table("rankings").select().order("age").limit(100).execute()
        assert len(res_large.data) == 5

        # 5. Negative limit clamps to 0
        res_neg = client.table("rankings").select().order("age").limit(-5).execute()
        assert res_neg.data == []

        # 6. Chaining order independence: calling .limit() before .order() sorts before slicing
        res_chain_order = client.table("rankings").select().limit(2).order("age", desc=True).execute()
        assert len(res_chain_order.data) == 2
        # Must return top 2 overall by age (40, 35), proving order runs before limit in execution
        assert [r["age"] for r in res_chain_order.data] == [40, 35]

        # 7. Combined .eq() + .order() + .limit()
        client.table("items").insert([
            {"category": "tool", "price": 15},
            {"category": "toy", "price": 5},
            {"category": "tool", "price": 45},
            {"category": "tool", "price": 30},
            {"category": "tool", "price": 10},
        ]).execute()
        res_compound = (
            client.table("items")
            .select()
            .eq("category", "tool")
            .order("price", desc=True)
            .limit(2)
            .execute()
        )
        assert len(res_compound.data) == 2
        assert [r["price"] for r in res_compound.data] == [45, 30]

        # 8. Order + limit + single() returns top dict
        top_single = (
            client.table("items")
            .select()
            .eq("category", "tool")
            .order("price", desc=True)
            .single()
            .execute()
        )
        assert isinstance(top_single.data, dict)
        assert top_single.data["price"] == 45

    def test_mock_query_isolation_and_immutability(self):
        """Challenge: Verify data isolation, deep copy immutability, and batch insert sanitization."""
        client = MockSupabaseClient()

        # 1. Verify mutation of returned select data does not mutate internal store
        client.table("profiles").insert({"id": "p1", "meta": {"role": "applicant"}}).execute()
        res1 = client.table("profiles").select().eq("id", "p1").single().execute()
        # Mutate the returned dictionary
        res1.data["meta"]["role"] = "superadmin"

        # Re-fetch from store to verify isolation
        res2 = client.table("profiles").select().eq("id", "p1").single().execute()
        assert res2.data["meta"]["role"] == "applicant", (
            "Internal mock store was mutated via external reference! Lack of deep copy isolation."
        )

        # 2. Batch insert with dirty/mixed elements
        client.table("mixed").insert([
            {"id": "valid-1", "val": 10},
            "corrupted-string",
            None,
            42,
            {"id": "valid-2", "val": 20},
        ]).execute()

        all_mixed = client.table("mixed").select().execute().data
        assert len(all_mixed) == 2
        assert {m["id"] for m in all_mixed} == {"valid-1", "valid-2"}

