"""Tier 1: Isolated Feature Coverage (Happy Path).

Verifies the primary behavior (happy path) for each public interface in isolation:
1. Health Check (GET /health)
2. User Registration (POST /auth/register)
3. User Login (POST /auth/login)
4. Voice Processing (POST /voice/process)
5. Interview Session Start (POST /interview/start)
6. Interview Session Respond (POST /interview/respond)
7. Interview Session End (POST /interview/end)
8. Interview Report Retrieval (GET /interview/report/{session_id})
9. Coach Session Start (POST /coach/start)
10. Coach Session Respond (POST /coach/respond)
11. Coach Session End (POST /coach/end)
"""

import uuid
import pytest


def test_health_check_returns_ok(client):
    """Authoritative source: ORIGINAL_REQUEST.md R1 & docs/05_ACCEPTANCE_CRITERIA.md.
    
    Expected output: HTTP 200 with {"status": "ok"}.
    """
    response = client.get("/health")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data.get("status") == "ok", f"Expected status 'ok', got: {data}"


def test_auth_register_isolated(client):
    """Authoritative source: ORIGINAL_REQUEST.md R2 & docs/06_TASK_DIVISION.md.
    
    Expected output: HTTP 200/201 with user object and access token.
    """
    unique_email = f"tier1_reg_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": unique_email,
        "password": "StrongPassword123!",
        "name": "Alex Candidate",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code in [200, 201], f"Register failed: {response.status_code} {response.text}"
    data = response.json()
    assert "user" in data, f"Missing 'user' key in register response: {data}"
    assert data["user"].get("email") == unique_email
    assert "access_token" in data, f"Missing 'access_token' in register response: {data}"
    assert len(data["access_token"]) > 0


def test_auth_login_isolated(client):
    """Authoritative source: ORIGINAL_REQUEST.md R2 & docs/06_TASK_DIVISION.md.
    
    Expected output: HTTP 200 with user object and access token.
    """
    unique_email = f"tier1_login_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"
    reg_payload = {
        "email": unique_email,
        "password": password,
        "name": "Login Tester",
    }
    reg_resp = client.post("/auth/register", json=reg_payload)
    assert reg_resp.status_code in [200, 201]

    login_payload = {
        "email": unique_email,
        "password": password,
    }
    response = client.post("/auth/login", json=login_payload)
    assert response.status_code == 200, f"Login failed: {response.status_code} {response.text}"
    data = response.json()
    assert "user" in data, f"Missing 'user' in login response: {data}"
    assert data["user"].get("email") == unique_email
    assert "access_token" in data, f"Missing 'access_token' in login response: {data}"


def test_voice_process_isolated(client, dummy_wav_bytes):
    """Authoritative source: ORIGINAL_REQUEST.md R2 & PROJECT.md Feature 8.
    
    Expected output: HTTP 200 containing either JSON transcript/spoken_response or audio stream.
    """
    files = {"file": ("sample.wav", dummy_wav_bytes, "audio/wav")}
    form_data = {"agent_type": "interview"}
    response = client.post("/voice/process", files=files, data=form_data)
    assert response.status_code == 200, f"Voice process failed: {response.status_code} {response.text}"
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        data = response.json()
        assert "spoken_response" in data or "transcript" in data, f"Unexpected JSON response: {data}"
    elif "audio" in content_type:
        assert len(response.content) > 0, "Empty audio stream returned"


def test_interview_start_isolated(client):
    """Authoritative source: ORIGINAL_REQUEST.md R3 & docs/08_AGENT_PROMPTS.md.
    
    Expected output: HTTP 200 with session_id and opening_message.
    """
    payload = {
        "candidate_name": "Jordan Lee",
        "role": "Backend Engineer",
        "experience_level": "Mid-level",
        "interview_type": "technical",
    }
    response = client.post("/interview/start", json=payload)
    assert response.status_code == 200, f"Interview start failed: {response.status_code} {response.text}"
    data = response.json()
    assert "session_id" in data, f"Missing session_id in response: {data}"
    assert "opening_message" in data, f"Missing opening_message in response: {data}"
    assert len(data["session_id"]) > 0
    assert len(data["opening_message"]) > 0


def test_interview_respond_isolated(client):
    """Authoritative source: ORIGINAL_REQUEST.md R3 & docs/08_AGENT_PROMPTS.md.
    
    Expected output: HTTP 200 with spoken_response, is_complete, and follow_up_or_next.
    """
    # Start interview first
    start_resp = client.post("/interview/start", json={
        "candidate_name": "Taylor Swift",
        "role": "Python Developer",
        "experience_level": "Senior",
        "interview_type": "technical",
    })
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]

    # Submit an answer
    respond_payload = {
        "session_id": session_id,
        "answer_text": "I have extensive experience designing microservices using FastAPI, Celery, and PostgreSQL.",
    }
    response = client.post("/interview/respond", json=respond_payload)
    assert response.status_code == 200, f"Interview respond failed: {response.status_code} {response.text}"
    data = response.json()
    assert "spoken_response" in data, f"Missing spoken_response: {data}"
    assert "is_complete" in data, f"Missing is_complete: {data}"
    assert isinstance(data["is_complete"], bool)
    assert "follow_up_or_next" in data, f"Missing follow_up_or_next: {data}"
    assert data["follow_up_or_next"] in ["follow_up", "next"]


def test_interview_end_isolated(client):
    """Authoritative source: ORIGINAL_REQUEST.md R3 & docs/08_AGENT_PROMPTS.md.
    
    Expected output: HTTP 200 with completed status and report object.
    """
    start_resp = client.post("/interview/start", json={
        "candidate_name": "Morgan Freeman",
        "role": "Cloud Architect",
        "experience_level": "Senior",
        "interview_type": "technical",
    })
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]

    # Respond once
    client.post("/interview/respond", json={
        "session_id": session_id,
        "answer_text": "I manage AWS multi-region infrastructure using Terraform and Kubernetes.",
    })

    # End session
    response = client.post("/interview/end", json={"session_id": session_id})
    assert response.status_code == 200, f"Interview end failed: {response.status_code} {response.text}"
    data = response.json()
    assert data.get("session_id") == session_id
    assert "report" in data or data.get("status") in ["completed", "ended", "success"]


def test_interview_report_retrieval_isolated(client):
    """Authoritative source: ORIGINAL_REQUEST.md R3 & docs/08_AGENT_PROMPTS.md.
    
    Expected output: HTTP 200 returning full JSON report matching authoritative schema.
    """
    # Start and end session
    start_resp = client.post("/interview/start", json={
        "candidate_name": "Chris Nolan",
        "role": "Data Engineer",
        "experience_level": "Mid-level",
        "interview_type": "technical",
    })
    session_id = start_resp.json()["session_id"]
    client.post("/interview/respond", json={
        "session_id": session_id,
        "answer_text": "I build real-time ETL pipelines with Apache Kafka, Spark Streaming, and Delta Lake.",
    })
    client.post("/interview/end", json={"session_id": session_id})

    # Retrieve report
    response = client.get(f"/interview/report/{session_id}")
    assert response.status_code == 200, f"Report retrieval failed: {response.status_code} {response.text}"
    report = response.json()
    assert "overall_score" in report, f"Missing overall_score: {report}"
    assert "dimension_scores" in report, f"Missing dimension_scores: {report}"
    dim_scores = report["dimension_scores"]
    for dim in ["relevance", "clarity", "depth", "examples"]:
        assert dim in dim_scores, f"Missing dimension {dim} in report: {dim_scores}"
        assert 1.0 <= float(dim_scores[dim]) <= 10.0, f"Score out of bounds 1-10: {dim_scores[dim]}"
    assert "strengths" in report and isinstance(report["strengths"], list)
    assert "weaknesses" in report and isinstance(report["weaknesses"], list)
    assert "improvement_tips" in report and isinstance(report["improvement_tips"], list)
    assert "coach_recommendation" in report and len(report["coach_recommendation"]) > 0
    assert "summary" in report and len(report["summary"]) > 0


def test_coach_start_isolated(client):
    """Authoritative source: ORIGINAL_REQUEST.md R4 & docs/08_AGENT_PROMPTS.md.
    
    Expected output: HTTP 200 with session_id and opening_message.
    """
    user_id = str(uuid.uuid4())
    payload = {
        "user_id": user_id,
        "mode": "conversation",
    }
    response = client.post("/coach/start", json=payload)
    assert response.status_code == 200, f"Coach start failed: {response.status_code} {response.text}"
    data = response.json()
    assert "session_id" in data, f"Missing session_id in coach start response: {data}"
    assert "opening_message" in data, f"Missing opening_message in coach start response: {data}"
    assert len(data["opening_message"]) > 0


def test_coach_respond_isolated(client):
    """Authoritative source: ORIGINAL_REQUEST.md R4 & docs/08_AGENT_PROMPTS.md.
    
    Expected output: HTTP 200 with coach_message, next_prompt, and optional correction.
    """
    start_resp = client.post("/coach/start", json={
        "user_id": str(uuid.uuid4()),
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    respond_payload = {
        "session_id": session_id,
        "user_text": "I really enjoy hiking on mountain trails during sunny weekends.",
    }
    response = client.post("/coach/respond", json=respond_payload)
    assert response.status_code == 200, f"Coach respond failed: {response.status_code} {response.text}"
    data = response.json()
    assert "coach_message" in data, f"Missing coach_message in coach respond: {data}"
    assert "next_prompt" in data, f"Missing next_prompt in coach respond: {data}"


def test_coach_end_isolated(client):
    """Authoritative source: ORIGINAL_REQUEST.md R4 & docs/08_AGENT_PROMPTS.md.
    
    Expected output: HTTP 200 with summary and updated_profile.
    """
    start_resp = client.post("/coach/start", json={
        "user_id": str(uuid.uuid4()),
        "mode": "english_improvement",
    })
    session_id = start_resp.json()["session_id"]

    client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "I was read book yesterday and learned many words.",
    })

    response = client.post("/coach/end", json={"session_id": session_id})
    assert response.status_code == 200, f"Coach end failed: {response.status_code} {response.text}"
    data = response.json()
    assert data.get("session_id") == session_id
    assert "summary" in data, f"Missing summary: {data}"
    assert "updated_profile" in data, f"Missing updated_profile: {data}"
    profile = data["updated_profile"]
    assert "skill_level" in profile
    assert "weak_areas" in profile and isinstance(profile["weak_areas"], list)
    assert "strong_areas" in profile and isinstance(profile["strong_areas"], list)
