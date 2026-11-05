"""Unit tests for Supabase SQL schema script and database client singleton."""

from pathlib import Path
from app.db.supabase import get_supabase_client, MockSupabaseClient


def test_schema_sql_file_exists():
    """Verify that backend/schema.sql exists and is non-empty."""
    schema_path = Path(__file__).resolve().parent.parent / "schema.sql"
    assert schema_path.exists(), f"Schema file not found at {schema_path}"
    content = schema_path.read_text(encoding="utf-8")
    assert len(content) > 500, "Schema file appears too short or truncated"


def test_schema_contains_core_tables():
    """Verify schema DDL defines users, interview_sessions, and coach_sessions."""
    schema_path = Path(__file__).resolve().parent.parent / "schema.sql"
    content = schema_path.read_text(encoding="utf-8").upper()

    assert "CREATE TABLE IF NOT EXISTS USERS" in content
    assert "CREATE TABLE IF NOT EXISTS INTERVIEW_SESSIONS" in content
    assert "CREATE TABLE IF NOT EXISTS COACH_SESSIONS" in content


def test_schema_contains_constraints_and_rls():
    """Verify schema DDL defines constraints, foreign keys, indexes, and RLS policies."""
    schema_path = Path(__file__).resolve().parent.parent / "schema.sql"
    content = schema_path.read_text(encoding="utf-8")

    # Table constraints
    assert "chk_users_skill_level" in content
    assert "CHECK (interview_type IN ('hr', 'technical'))" in content
    assert "CHECK (mode IN ('conversation', 'answer_training', 'english_improvement'))" in content

    # RLS policies
    assert "ALTER TABLE users ENABLE ROW LEVEL SECURITY" in content
    assert "ALTER TABLE interview_sessions ENABLE ROW LEVEL SECURITY" in content
    assert "ALTER TABLE coach_sessions ENABLE ROW LEVEL SECURITY" in content

    # Key indexes
    assert "idx_users_email" in content
    assert "idx_interview_sessions_user_id" in content
    assert "idx_coach_sessions_user_id" in content


def test_supabase_client_singleton():
    """Verify get_supabase_client returns a singleton instance."""
    client1 = get_supabase_client()
    client2 = get_supabase_client()
    assert client1 is client2
    assert hasattr(client1, "table")
    assert hasattr(client1, "auth")


def test_mock_supabase_client_query_operations():
    """Verify MockSupabaseClient query builder can select, insert, and update."""
    client = get_supabase_client()

    # Query initial users
    res = client.table("users").select("*").execute()
    assert res.data is not None
    assert len(res.data) >= 1
    assert res.data[0]["email"] == "demo@voxprep.ai"

    # Filter with eq and single
    single_res = client.table("users").select("*").eq("email", "demo@voxprep.ai").single().execute()
    assert single_res.data is not None
    assert single_res.data["email"] == "demo@voxprep.ai"

    # Insert into interview_sessions
    insert_res = client.table("interview_sessions").insert({
        "id": "11111111-1111-1111-1111-111111111111",
        "candidate_name": "Test Candidate",
        "role_applied": "Backend Engineer",
        "experience_level": "mid",
        "interview_type": "technical",
    }).execute()
    assert insert_res.data is not None

    # Query back inserted session
    query_res = client.table("interview_sessions").select("*").eq("id", "11111111-1111-1111-1111-111111111111").single().execute()
    assert query_res.data is not None
    assert query_res.data["candidate_name"] == "Test Candidate"

    # Update session
    update_res = client.table("interview_sessions").eq("id", "11111111-1111-1111-1111-111111111111").update({"is_complete": True}).execute()
    assert update_res.data is not None


def test_mock_supabase_auth_operations():
    """Verify MockSupabaseClient auth supports sign_up and sign_in_with_password."""
    client = get_supabase_client()

    # Sign up
    signup_res = client.auth.sign_up({"email": "newuser@voxprep.ai", "password": "securepassword123"})
    assert signup_res.user is not None
    assert signup_res.user.email == "newuser@voxprep.ai"

    # Sign in
    signin_res = client.auth.sign_in_with_password({"email": "newuser@voxprep.ai", "password": "securepassword123"})
    assert signin_res.user is not None
    assert signin_res.session is not None
    assert signin_res.session.access_token == "mock-jwt-token"
