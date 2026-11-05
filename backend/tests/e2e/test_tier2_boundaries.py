"""Tier 2: Boundary & Corner Cases.

Verifies system resilience, guardrails, and error handling under extreme or invalid conditions:
1. Empty audio file (0 bytes)
2. Corrupt non-audio file
3. Maximum 5 core questions boundary enforcement
4. Maximum 1 follow-up per question boundary enforcement
5. Maximum 1-2 coach corrections per exchange
6. Invalid interview_type validation
7. Invalid coach mode validation
8. Missing required request body fields (HTTP 422)
9. Extremely short (1-word) answers
10. Explicit "I don't know" answer handling
11. Non-existent session IDs (HTTP 404)
"""

import uuid
import pytest


def test_voice_process_empty_audio_boundary(client, empty_audio_bytes):
    """Authoritative source: docs/07_GUARDRAILS.md & ORIGINAL_REQUEST.md.
    
    Guardrail: If audio is empty or STT fails, returns friendly message without 500 crash.
    """
    files = {"file": ("empty.wav", empty_audio_bytes, "audio/wav")}
    form_data = {"agent_type": "interview"}
    response = client.post("/voice/process", files=files, data=form_data)
    # Must NOT crash with 500
    assert response.status_code in [200, 400, 422], f"Server crashed with {response.status_code}: {response.text}"
    if response.status_code == 200:
        data = response.json()
        assert "spoken_response" in data or "transcript" in data
        resp_text = (data.get("spoken_response") or data.get("transcript") or "").lower()
        assert "not understand" in resp_text or "try again" in resp_text or len(resp_text) > 0


def test_voice_process_corrupt_audio_boundary(client, corrupt_audio_bytes):
    """Authoritative source: docs/07_GUARDRAILS.md & ORIGINAL_REQUEST.md.
    
    Guardrail: Corrupt audio must not cause unhandled exceptions.
    """
    files = {"file": ("corrupt.wav", corrupt_audio_bytes, "audio/wav")}
    form_data = {"agent_type": "interview"}
    response = client.post("/voice/process", files=files, data=form_data)
    assert response.status_code in [200, 400, 422], f"Server crashed with {response.status_code}: {response.text}"
    if response.status_code == 200:
        data = response.json()
        resp_text = (data.get("spoken_response") or data.get("transcript") or "").lower()
        assert "not understand" in resp_text or "try again" in resp_text or len(resp_text) > 0


def test_interview_max_5_questions_boundary(client):
    """Authoritative source: docs/07_GUARDRAILS.md & docs/08_AGENT_PROMPTS.md.
    
    Rule: Session must enforce maximum 5 core questions. Once reached, is_complete is True.
    """
    start_resp = client.post("/interview/start", json={
        "candidate_name": "Boundary Tester",
        "role": "QA Engineer",
        "experience_level": "Mid-level",
        "interview_type": "technical",
    })
    session_id = start_resp.json()["session_id"]

    is_complete = False
    turn_count = 0
    max_turns = 12  # Guard against infinite loop

    while not is_complete and turn_count < max_turns:
        turn_count += 1
        resp = client.post("/interview/respond", json={
            "session_id": session_id,
            "answer_text": f"This is detailed answer #{turn_count} addressing performance and test automation.",
        })
        assert resp.status_code == 200, f"Turn {turn_count} failed: {resp.text}"
        data = resp.json()
        is_complete = data.get("is_complete", False)
        if is_complete:
            break

    assert is_complete is True, "Interview did not conclude within expected 5 questions limit"
    assert turn_count <= 10, f"Exceeded maximum allowable questions and follow-ups: {turn_count} turns"


def test_interview_max_1_follow_up_boundary(client):
    """Authoritative source: docs/07_GUARDRAILS.md & docs/08_AGENT_PROMPTS.md.
    
    Rule: Maximum ONE follow-up per question. Never two follow-ups in a row.
    """
    start_resp = client.post("/interview/start", json={
        "candidate_name": "FollowUp Tester",
        "role": "DevOps Engineer",
        "experience_level": "Senior",
        "interview_type": "technical",
    })
    session_id = start_resp.json()["session_id"]

    consecutive_follow_ups = 0
    for turn in range(6):
        resp = client.post("/interview/respond", json={
            "session_id": session_id,
            "answer_text": "I configure CI/CD pipelines using GitHub Actions and ArgoCD.",
        })
        assert resp.status_code == 200
        data = resp.json()
        if data.get("is_complete"):
            break
        follow_type = data.get("follow_up_or_next")
        if follow_type == "follow_up":
            consecutive_follow_ups += 1
        else:
            consecutive_follow_ups = 0
        assert consecutive_follow_ups <= 1, f"Found {consecutive_follow_ups} consecutive follow-ups (max 1 allowed)"


def test_coach_max_1_to_2_corrections_boundary(client):
    """Authoritative source: docs/07_GUARDRAILS.md & docs/08_AGENT_PROMPTS.md.
    
    Rule: Never overwhelm user; provide at most 1-2 corrections per exchange.
    """
    start_resp = client.post("/coach/start", json={
        "user_id": str(uuid.uuid4()),
        "mode": "english_improvement",
    })
    session_id = start_resp.json()["session_id"]

    # Utterance deliberately packed with grammatical errors
    flawed_utterance = (
        "Yesterday I was go to markets and I buyed many fishes and then "
        "he do not know where is the car and we was very sad."
    )
    resp = client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": flawed_utterance,
    })
    assert resp.status_code == 200
    data = resp.json()

    correction = data.get("correction")
    if correction:
        if isinstance(correction, list):
            assert len(correction) <= 2, f"Coach provided more than 2 corrections: {len(correction)}"
        elif isinstance(correction, dict):
            # Single correction object is compliant with 1-2 limit
            assert "original" in correction
            assert "improved" in correction


def test_interview_invalid_mode_rejected(client):
    """Authoritative source: docs/07_GUARDRAILS.md & docs/04_MVP_vs_EXTRA.md.
    
    Post-MVP modes (debate, situational) or arbitrary modes must be rejected with 400 or 422.
    """
    payload = {
        "candidate_name": "Invalid Tester",
        "role": "Lawyer",
        "experience_level": "Mid-level",
        "interview_type": "debate",  # Explicitly Post-MVP
    }
    response = client.post("/interview/start", json=payload)
    assert response.status_code in [400, 422], f"Expected 400/422 for invalid interview_type, got {response.status_code}"


def test_coach_invalid_mode_rejected(client):
    """Authoritative source: docs/07_GUARDRAILS.md & ORIGINAL_REQUEST.md R4.
    
    Only 'conversation', 'answer_training', 'english_improvement' are allowed.
    """
    payload = {
        "user_id": str(uuid.uuid4()),
        "mode": "hostile_cross_examination",
    }
    response = client.post("/coach/start", json=payload)
    assert response.status_code in [400, 422], f"Expected 400/422 for invalid coach mode, got {response.status_code}"


def test_missing_required_fields_raises_422(client):
    """Authoritative source: ORIGINAL_REQUEST.md Phase 4 & FastAPI Pydantic validation."""
    # 1. Missing password in register
    resp1 = client.post("/auth/register", json={"email": "bad_req@example.com"})
    assert resp1.status_code == 422, f"Expected 422 for missing password, got {resp1.status_code}"

    # 2. Missing role in interview start
    resp2 = client.post("/interview/start", json={"candidate_name": "No Role", "interview_type": "hr"})
    assert resp2.status_code == 422, f"Expected 422 for missing role, got {resp2.status_code}"

    # 3. Missing session_id in interview respond
    resp3 = client.post("/interview/respond", json={"answer_text": "Answer without session"})
    assert resp3.status_code == 422, f"Expected 422 for missing session_id, got {resp3.status_code}"

    # 4. Missing mode in coach start
    resp4 = client.post("/coach/start", json={"user_id": str(uuid.uuid4())})
    assert resp4.status_code == 422, f"Expected 422 for missing mode, got {resp4.status_code}"


def test_interview_1_word_answer_handling(client):
    """Authoritative source: docs/07_GUARDRAILS.md (Candidate provides 1-word answer).
    
    Fallback: Ask once 'Could you elaborate on that?' or advance cleanly without crashing.
    """
    start_resp = client.post("/interview/start", json={
        "candidate_name": "Terse Candidate",
        "role": "Frontend Engineer",
        "experience_level": "Junior",
        "interview_type": "technical",
    })
    session_id = start_resp.json()["session_id"]

    response = client.post("/interview/respond", json={
        "session_id": session_id,
        "answer_text": "React.",
    })
    assert response.status_code == 200, f"Failed on 1-word answer: {response.text}"
    data = response.json()
    assert "spoken_response" in data
    assert len(data["spoken_response"]) > 0


def test_interview_i_dont_know_answer_handling(client):
    """Authoritative source: docs/07_GUARDRAILS.md (Candidate says 'I don't know').
    
    Fallback: Acknowledge politely, note in evaluation, and move to next question.
    """
    start_resp = client.post("/interview/start", json={
        "candidate_name": "Honest Candidate",
        "role": "Security Engineer",
        "experience_level": "Entry",
        "interview_type": "technical",
    })
    session_id = start_resp.json()["session_id"]

    response = client.post("/interview/respond", json={
        "session_id": session_id,
        "answer_text": "I honestly don't know the answer to this question.",
    })
    assert response.status_code == 200, f"Failed on 'I don't know': {response.text}"
    data = response.json()
    assert "spoken_response" in data
    assert len(data["spoken_response"]) > 0


def test_nonexistent_session_id_returns_404(client):
    """Authoritative source: spec_report.md Section 6.1 (Standardized Error Handling).
    
    Non-existent session IDs must return HTTP 404 with structured detail.
    """
    random_sid = str(uuid.uuid4())

    # Interview respond
    resp1 = client.post("/interview/respond", json={
        "session_id": random_sid,
        "answer_text": "Random text",
    })
    assert resp1.status_code == 404, f"Expected 404 for interview respond, got {resp1.status_code}"

    # Interview report
    resp2 = client.get(f"/interview/report/{random_sid}")
    assert resp2.status_code == 404, f"Expected 404 for interview report, got {resp2.status_code}"

    # Coach respond
    resp3 = client.post("/coach/respond", json={
        "session_id": random_sid,
        "user_text": "Random coach utterance",
    })
    assert resp3.status_code == 404, f"Expected 404 for coach respond, got {resp3.status_code}"
