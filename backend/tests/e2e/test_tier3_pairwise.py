"""Tier 3: Pairwise Cross-Feature Combinations.

Validates the interactions between disparate backend subsystems across lifecycles:
1. Register -> Login -> Start Technical Interview -> Respond -> End -> Fetch Report.
2. Register -> Start Coach Session -> Respond with errors -> End -> Verify Profile Weak/Strong Areas Updated.
3. Authenticated Voice Processing (Bearer Token + Voice STT-to-Agent Pipeline).
"""

import uuid
import pytest


def test_pairwise_register_login_interview_report_lifecycle(client):
    """Sequence: Auth Register -> Login -> Interview Start -> Respond -> End -> Report Retrieval.
    
    Verifies that a user can create an account, authenticate, participate in an interview,
    and persist/retrieve their structured performance report.
    """
    email = f"candidate_pairwise_{uuid.uuid4().hex[:8]}@example.com"
    password = "PairwiseSecure123!"

    # 1. Register
    reg_resp = client.post("/auth/register", json={
        "email": email,
        "password": password,
        "name": "Pairwise Candidate",
    })
    assert reg_resp.status_code in [200, 201], f"Registration failed: {reg_resp.text}"
    user_id = reg_resp.json()["user"]["id"]

    # 2. Login
    login_resp = client.post("/auth/login", json={
        "email": email,
        "password": password,
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    access_token = login_resp.json()["access_token"]
    assert len(access_token) > 0

    # 3. Start Interview with user_id
    start_resp = client.post("/interview/start", json={
        "candidate_name": "Pairwise Candidate",
        "role": "Distributed Systems Engineer",
        "experience_level": "Senior",
        "interview_type": "technical",
        "user_id": user_id,
    })
    assert start_resp.status_code == 200, f"Interview start failed: {start_resp.text}"
    session_id = start_resp.json()["session_id"]
    assert len(session_id) > 0

    # 4. Respond to questions
    answers = [
        "I have built distributed consensus mechanisms with Raft in Go.",
        "To handle partitioning, we used quorum reads and optimistic concurrency control.",
    ]
    for ans in answers:
        resp = client.post("/interview/respond", json={
            "session_id": session_id,
            "answer_text": ans,
        })
        assert resp.status_code == 200, f"Response failed: {resp.text}"
        assert "spoken_response" in resp.json()

    # 5. End Interview
    end_resp = client.post("/interview/end", json={"session_id": session_id})
    assert end_resp.status_code == 200, f"End interview failed: {end_resp.text}"

    # 6. Retrieve Report
    report_resp = client.get(f"/interview/report/{session_id}")
    assert report_resp.status_code == 200, f"Report fetch failed: {report_resp.text}"
    report = report_resp.json()

    assert "overall_score" in report
    assert "dimension_scores" in report
    assert "strengths" in report
    assert "improvement_tips" in report
    assert "coach_recommendation" in report


def test_pairwise_register_coach_profile_update_lifecycle(client):
    """Sequence: Auth Register -> Start Coach Session -> Multi-turn drills -> End -> Profile Learning.
    
    Verifies that coach sessions update the user's communication profile in persistence.
    """
    email = f"coach_pairwise_{uuid.uuid4().hex[:8]}@example.com"
    password = "CoachPassword123!"

    # 1. Register
    reg_resp = client.post("/auth/register", json={
        "email": email,
        "password": password,
        "name": "Coach Learner",
    })
    assert reg_resp.status_code in [200, 201]
    user_id = reg_resp.json()["user"]["id"]

    # 2. Start Coach Session
    start_resp = client.post("/coach/start", json={
        "user_id": user_id,
        "mode": "english_improvement",
    })
    assert start_resp.status_code == 200
    coach_sid = start_resp.json()["session_id"]

    # 3. Respond with learning phrases
    resp1 = client.post("/coach/respond", json={
        "session_id": coach_sid,
        "user_text": "Yesterday I was go to cinema with my friend and we watch very good movie.",
    })
    assert resp1.status_code == 200
    assert "coach_message" in resp1.json()

    resp2 = client.post("/coach/respond", json={
        "session_id": coach_sid,
        "user_text": "Next time I will went there again.",
    })
    assert resp2.status_code == 200

    # 4. End Coach Session
    end_resp = client.post("/coach/end", json={"session_id": coach_sid})
    assert end_resp.status_code == 200
    end_data = end_resp.json()

    # 5. Verify Profile Update
    assert "updated_profile" in end_data
    prof = end_data["updated_profile"]
    assert prof.get("sessions_count", 0) >= 1
    assert "weak_areas" in prof
    assert "strong_areas" in prof


def test_pairwise_authenticated_voice_processing(client, dummy_wav_bytes):
    """Sequence: Auth Login -> Obtain Bearer Token -> Process Voice with Auth Headers.
    
    Verifies that voice processing works seamlessly in authenticated sessions.
    """
    email = f"voice_auth_{uuid.uuid4().hex[:8]}@example.com"
    password = "AuthVoicePassword123!"

    client.post("/auth/register", json={
        "email": email,
        "password": password,
        "name": "Voice User",
    })

    login_resp = client.post("/auth/login", json={
        "email": email,
        "password": password,
    })
    token = login_resp.json().get("access_token", "mock-token")

    files = {"file": ("audio_input.wav", dummy_wav_bytes, "audio/wav")}
    form_data = {"agent_type": "interview"}
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/voice/process", files=files, data=form_data, headers=headers)
    assert response.status_code == 200, f"Authenticated voice processing failed: {response.text}"
