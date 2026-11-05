"""VOXPREP Backend - AI Interviewer Agent Unit & Integration Tests
Milestone 2: Phase 2 Interviewer Agent, Session Management, and Reporting.

Verifies:
1. Interview start for HR and Technical tracks (HTTP 200).
2. Candidate response processing, rubric evaluation, and follow-up progression.
3. Strict enforcement of maximum 1 follow-up per question.
4. Strict enforcement of maximum 5 core questions per session boundary.
5. Premature and natural session termination (POST /interview/end).
6. Performance report retrieval (GET /interview/report/{session_id}).
7. Error handling:
   - Non-existent session_id returns 404.
   - Uncompleted session report retrieval returns 400.
   - Missing fields and invalid interview_type return 422.
8. Conversational guardrails:
   - 1-word / terse candidate answers.
   - "I don't know" candidate answers.
9. Supabase database persistence synchronization.
10. Agent & Service unit tests (InterviewSession, report generator, session persistence).
"""

import uuid
import pytest
from app.agents.interviewer import (
    InterviewSession,
    MAX_QUESTIONS,
    MAX_FOLLOW_UPS_PER_QUESTION,
    _evaluate_mock_answer_heuristics,
    _extract_json_from_llm_response,
)
from app.db.session_persistence import (
    create_interview_session,
    get_interview_session,
    update_interview_session,
    finalize_interview_session,
)
from app.main import app
from app.routers.interview import session_manager
from app.services.report import (
    generate_fallback_report,
    generate_report,
    normalize_and_validate_report,
    parse_llm_report_json,
)
from tests.conftest import LocalClient


def run_sync(coro):
    """Executes a coroutine stack synchronously without socketpair event loop dependencies."""
    stack = [coro]
    while stack:
        current = stack[-1]
        try:
            sub = current.send(None)
            if hasattr(sub, "send"):
                stack.append(sub)
        except StopIteration as exc:
            stack.pop()
            if not stack:
                return exc.value


@pytest.fixture(autouse=True)
def clean_sessions():
    """Ensures clean in-memory session manager for every test function."""
    session_manager.clear()
    yield
    session_manager.clear()


@pytest.fixture
def test_client():
    """Provides synchronous LocalClient bound to the application."""
    with LocalClient(app) as client:
        yield client


# =============================================================================
# 1. Interview Start Tests
# =============================================================================

def test_interview_start_hr_track(test_client):
    """Verifies that an HR interview session initializes with valid opening greeting."""
    payload = {
        "candidate_name": "Jordan Lee",
        "role": "People Operations Manager",
        "experience_level": "Mid-level",
        "interview_type": "hr",
    }
    response = test_client.post("/interview/start", json=payload)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    data = response.json()
    assert "session_id" in data
    assert "opening_message" in data
    assert len(data["session_id"]) > 0
    assert "Jordan" in data["opening_message"]
    assert "HR" in data["opening_message"] or "People Operations" in data["opening_message"]


def test_interview_start_technical_track(test_client):
    """Verifies that a Technical interview session initializes with technical persona."""
    payload = {
        "candidate_name": "Alex Rivera",
        "role": "Distributed Systems Architect",
        "experience_level": "Senior",
        "interview_type": "technical",
    }
    response = test_client.post("/interview/start", json=payload)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    data = response.json()
    assert "session_id" in data
    assert "opening_message" in data
    assert "Alex" in data["opening_message"]
    assert "technical" in data["opening_message"].lower() or "Distributed Systems" in data["opening_message"]


def test_interview_start_invalid_type_raises_422(test_client):
    """Verifies that unsupported or post-MVP interview tracks are rejected with 422."""
    payload = {
        "candidate_name": "Invalid Candidate",
        "role": "Software Engineer",
        "experience_level": "Entry",
        "interview_type": "debate",  # Post-MVP / invalid
    }
    response = test_client.post("/interview/start", json=payload)
    assert response.status_code == 422, f"Expected 422 for invalid interview_type, got {response.status_code}"


def test_interview_start_missing_required_fields_raises_422(test_client):
    """Verifies that missing required parameters raise 422 Unprocessable Entity."""
    # Missing role
    resp1 = test_client.post("/interview/start", json={
        "candidate_name": "No Role",
        "experience_level": "Junior",
        "interview_type": "hr",
    })
    assert resp1.status_code == 422

    # Missing candidate_name
    resp2 = test_client.post("/interview/start", json={
        "role": "Backend Engineer",
        "experience_level": "Senior",
        "interview_type": "technical",
    })
    assert resp2.status_code == 422


# =============================================================================
# 2. Candidate Response & Progression Tests
# =============================================================================

def test_interview_respond_success(test_client):
    """Verifies that answering a question returns a spoken response and status indicators."""
    start_resp = test_client.post("/interview/start", json={
        "candidate_name": "Taylor Swift",
        "role": "Python Developer",
        "experience_level": "Senior",
        "interview_type": "technical",
    })
    session_id = start_resp.json()["session_id"]

    respond_resp = test_client.post("/interview/respond", json={
        "session_id": session_id,
        "answer_text": "I design fault-tolerant microservices using FastAPI, Redis caching, and PostgreSQL.",
    })
    assert respond_resp.status_code == 200, f"Expected 200, got: {respond_resp.text}"
    data = respond_resp.json()
    assert "spoken_response" in data
    assert "is_complete" in data
    assert isinstance(data["is_complete"], bool)
    assert data["follow_up_or_next"] in ["follow_up", "next"]
    assert "question_index" in data
    assert "total_questions" in data
    assert data["total_questions"] == 5


def test_interview_max_1_follow_up_rule(test_client):
    """Verifies that at most ONE follow-up is asked per question before moving forward."""
    start_resp = test_client.post("/interview/start", json={
        "candidate_name": "FollowUp Tester",
        "role": "DevOps Engineer",
        "experience_level": "Senior",
        "interview_type": "technical",
    })
    session_id = start_resp.json()["session_id"]

    consecutive_follow_ups = 0
    for turn in range(6):
        resp = test_client.post("/interview/respond", json={
            "session_id": session_id,
            "answer_text": f"Turn {turn + 1}: I configure Kubernetes clusters and ArgoCD pipelines.",
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


def test_interview_five_question_boundary(test_client):
    """Verifies that an interview session concludes after 5 core questions."""
    start_resp = test_client.post("/interview/start", json={
        "candidate_name": "Boundary Candidate",
        "role": "Cloud Architect",
        "experience_level": "Senior",
        "interview_type": "technical",
    })
    session_id = start_resp.json()["session_id"]

    is_complete = False
    turn_count = 0
    max_turns = 12

    while not is_complete and turn_count < max_turns:
        turn_count += 1
        resp = test_client.post("/interview/respond", json={
            "session_id": session_id,
            "answer_text": f"Detailed answer #{turn_count} demonstrating depth and concrete production metrics.",
        })
        assert resp.status_code == 200
        data = resp.json()
        is_complete = data.get("is_complete", False)
        if is_complete:
            break

    assert is_complete is True, "Interview did not conclude within expected 5 questions limit"
    assert turn_count <= 10, f"Exceeded maximum allowable questions and follow-ups: {turn_count} turns"

    # Subsequent responses should return completed state gracefully without mutating
    extra_resp = test_client.post("/interview/respond", json={
        "session_id": session_id,
        "answer_text": "Answering again after completion.",
    })
    assert extra_resp.status_code == 200
    assert extra_resp.json()["is_complete"] is True


# =============================================================================
# 3. Conversational Guardrail Tests
# =============================================================================

def test_interview_guardrail_one_word_answer(test_client):
    """Verifies that a 1-word answer prompts for elaboration without crashing."""
    start_resp = test_client.post("/interview/start", json={
        "candidate_name": "Terse Candidate",
        "role": "Frontend Developer",
        "experience_level": "Junior",
        "interview_type": "technical",
    })
    session_id = start_resp.json()["session_id"]

    resp = test_client.post("/interview/respond", json={
        "session_id": session_id,
        "answer_text": "React.",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "spoken_response" in data
    assert len(data["spoken_response"]) > 0


def test_interview_guardrail_i_dont_know(test_client):
    """Verifies that an 'I don't know' answer is politely handled and advances to next question."""
    start_resp = test_client.post("/interview/start", json={
        "candidate_name": "Honest Candidate",
        "role": "Security Engineer",
        "experience_level": "Entry",
        "interview_type": "technical",
    })
    session_id = start_resp.json()["session_id"]

    resp = test_client.post("/interview/respond", json={
        "session_id": session_id,
        "answer_text": "I honestly don't know the answer to this question.",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "spoken_response" in data
    assert len(data["spoken_response"]) > 0


# =============================================================================
# 4. End Interview & Report Retrieval Tests
# =============================================================================

def test_interview_end_generates_report(test_client):
    """Verifies POST /interview/end concludes the session and populates the performance report."""
    start_resp = test_client.post("/interview/start", json={
        "candidate_name": "Morgan Freeman",
        "role": "Staff Engineer",
        "experience_level": "Senior",
        "interview_type": "technical",
    })
    session_id = start_resp.json()["session_id"]

    test_client.post("/interview/respond", json={
        "session_id": session_id,
        "answer_text": "I have built multi-region event pipelines with Kafka and Flink.",
    })

    end_resp = test_client.post("/interview/end", json={"session_id": session_id})
    assert end_resp.status_code == 200, f"Expected 200, got: {end_resp.text}"
    data = end_resp.json()
    assert data["session_id"] == session_id
    assert data["status"] == "completed"
    assert "report" in data
    report = data["report"]
    assert "overall_score" in report
    assert "dimension_scores" in report


def test_interview_report_uncompleted_session_returns_400(test_client):
    """Verifies that fetching report for an uncompleted session returns HTTP 400."""
    start_resp = test_client.post("/interview/start", json={
        "candidate_name": "Active Candidate",
        "role": "Product Manager",
        "experience_level": "Senior",
        "interview_type": "hr",
    })
    session_id = start_resp.json()["session_id"]

    report_resp = test_client.get(f"/interview/report/{session_id}")
    assert report_resp.status_code == 400, f"Expected 400 for uncompleted session report, got {report_resp.status_code}"
    assert "not yet completed" in report_resp.json()["detail"].lower()


def test_interview_report_retrieval_success(test_client):
    """Verifies GET /interview/report/{session_id} returns all required schema fields."""
    start_resp = test_client.post("/interview/start", json={
        "candidate_name": "Chris Nolan",
        "role": "Data Engineer",
        "experience_level": "Mid-level",
        "interview_type": "technical",
    })
    session_id = start_resp.json()["session_id"]

    test_client.post("/interview/respond", json={
        "session_id": session_id,
        "answer_text": "I build real-time ETL pipelines with Apache Kafka, Spark Streaming, and Delta Lake.",
    })
    test_client.post("/interview/end", json={"session_id": session_id})

    report_resp = test_client.get(f"/interview/report/{session_id}")
    assert report_resp.status_code == 200
    report = report_resp.json()

    # Verify report structure per docs/08_AGENT_PROMPTS.md
    assert "overall_score" in report
    assert 1.0 <= float(report["overall_score"]) <= 10.0

    dim_scores = report["dimension_scores"]
    for dim in ["relevance", "clarity", "depth", "examples"]:
        assert dim in dim_scores
        assert 1.0 <= float(dim_scores[dim]) <= 10.0

    assert isinstance(report["strengths"], list) and len(report["strengths"]) >= 1
    assert isinstance(report["weaknesses"], list) and len(report["weaknesses"]) >= 1
    assert isinstance(report["improvement_tips"], list) and len(report["improvement_tips"]) >= 1
    assert "coach_recommendation" in report and len(report["coach_recommendation"]) > 0
    assert "summary" in report and len(report["summary"]) > 0


# =============================================================================
# 5. Error Handling Tests (404 & 422)
# =============================================================================

def test_interview_nonexistent_session_id_returns_404(test_client):
    """Verifies that non-existent session IDs return HTTP 404 across all endpoints."""
    bad_id = str(uuid.uuid4())

    # Respond on non-existent session
    resp1 = test_client.post("/interview/respond", json={
        "session_id": bad_id,
        "answer_text": "Text for invalid session",
    })
    assert resp1.status_code == 404

    # End non-existent session
    resp2 = test_client.post("/interview/end", json={
        "session_id": bad_id,
    })
    assert resp2.status_code == 404

    # Report for non-existent session
    resp3 = test_client.get(f"/interview/report/{bad_id}")
    assert resp3.status_code == 404


def test_interview_respond_missing_session_id_raises_422(test_client):
    """Verifies that omitting session_id in POST /interview/respond raises 422."""
    resp = test_client.post("/interview/respond", json={
        "answer_text": "Answer without session ID",
    })
    assert resp.status_code == 422


# =============================================================================
# 6. Full Lifecycle Integration Tests
# =============================================================================

def test_interview_full_lifecycle_hr_track(test_client):
    """Full lifecycle: start -> respond across multiple questions -> end -> retrieve report."""
    start_payload = {
        "candidate_name": "Sarah Chen",
        "role": "Junior Software Developer",
        "experience_level": "Junior",
        "interview_type": "hr",
    }
    start_resp = test_client.post("/interview/start", json=start_payload)
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]

    hr_answers = [
        "I recently graduated with a degree in Computer Science and interned at a software agency.",
        "When our capstone team disagreed on SQL vs Mongo, I benchmarked performance and presented the data.",
        "Through that project I learned proactive communication and data-driven decisions avoid conflict.",
        "When I accidentally broke a staging build, I promptly notified the team, reverted, and added tests.",
        "In three years I hope to grow into a senior backend developer and mentor junior engineers.",
    ]

    for ans in hr_answers:
        resp = test_client.post("/interview/respond", json={
            "session_id": session_id,
            "answer_text": ans,
        })
        assert resp.status_code == 200
        assert "spoken_response" in resp.json()
        if resp.json().get("is_complete"):
            break

    end_resp = test_client.post("/interview/end", json={"session_id": session_id})
    assert end_resp.status_code == 200

    report_resp = test_client.get(f"/interview/report/{session_id}")
    assert report_resp.status_code == 200
    report = report_resp.json()
    assert report["overall_score"] > 0
    assert len(report["strengths"]) >= 1
    assert len(report["improvement_tips"]) >= 1


# =============================================================================
# 7. Agent Unit Tests (InterviewSession, Rubrics, Prompts, Serialization)
# =============================================================================

def test_interview_session_agent_unit():
    """Unit tests for InterviewSession state machine, prompts, and score updates."""
    session = InterviewSession(
        candidate_name="Agent Tester",
        role="Backend Engineer",
        experience_level="Senior",
        interview_type="technical",
    )
    assert session.current_question_index == 0
    assert session.follow_up_count == 0
    assert not session.is_complete

    # Test prompt generation
    tech_prompt = session.get_system_prompt()
    assert "VOXPREP's professional AI interviewer" in tech_prompt
    assert "Agent Tester" in tech_prompt
    assert "Backend Engineer" in tech_prompt

    # Test HR prompt
    hr_session = InterviewSession(
        candidate_name="HR Candidate",
        role="HR Specialist",
        experience_level="Mid-level",
        interview_type="hr",
    )
    hr_prompt = hr_session.get_system_prompt()
    assert "conducting a structured HR interview" in hr_prompt

    # Test start_session
    opening = run_sync(session.start_session())
    assert "Agent Tester" in opening
    assert len(session.current_question) > 0

    # Test process_answer
    result = run_sync(session.process_answer(
        "I build distributed microservices using FastAPI, Redis, Kafka, and PostgreSQL with strong consistency."
    ))
    assert "spoken_response" in result
    assert result["follow_up_or_next"] == "follow_up"
    assert session.follow_up_count == 1
    assert session.current_question_index == 0
    assert len(session.question_history) == 1

    # Next answer must advance question index and reset follow_up_count
    result2 = run_sync(session.process_answer(
        "For partitioning, we use Kafka key-based routing and hash ring distribution."
    ))
    assert result2["follow_up_or_next"] == "next"
    assert session.follow_up_count == 0
    assert session.current_question_index == 1

    # Serialization roundtrip
    data_dict = session.to_dict()
    restored = InterviewSession.from_dict(data_dict)
    assert restored.session_id == session.session_id
    assert restored.candidate_name == session.candidate_name
    assert restored.current_question_index == session.current_question_index
    assert restored.follow_up_count == session.follow_up_count


def test_rubric_evaluation_heuristics():
    """Unit test for offline rubric heuristic scoring."""
    # Evasive answer
    evasive_scores = _evaluate_mock_answer_heuristics("I don't know", "What is an index?")
    assert evasive_scores["depth"] <= 3.0
    assert evasive_scores["examples"] <= 2.0

    # Rich answer with keywords
    rich_answer = (
        "In our microservice architecture, we use FastAPI and Kafka with PostgreSQL. "
        "We tuned PgBouncer for connection pooling to decrease latency and increase throughput."
    )
    rich_scores = _evaluate_mock_answer_heuristics(rich_answer, "How do you scale databases?")
    for dim in ["relevance", "clarity", "depth", "examples"]:
        assert 1.0 <= rich_scores[dim] <= 10.0
    assert rich_scores["depth"] >= 7.0


# =============================================================================
# 8. Report Service Unit Tests
# =============================================================================

def test_report_service_generation_and_normalization():
    """Unit tests for report generation, JSON parsing, and fallbacks."""
    sample_session = {
        "candidate_name": "Unit Candidate",
        "role": "QA Engineer",
        "interview_type": "technical",
        "question_history": [
            {
                "question": "Explain testing strategies.",
                "answer": "I implement unit, integration, and end-to-end tests using pytest and Playwright.",
                "scores": {"relevance": 8.5, "clarity": 8.0, "depth": 8.0, "examples": 8.0},
            }
        ],
    }

    report = run_sync(generate_report(sample_session))
    assert 1.0 <= float(report["overall_score"]) <= 10.0
    assert "dimension_scores" in report
    for dim in ["relevance", "clarity", "depth", "examples"]:
        assert dim in report["dimension_scores"]
    assert len(report["strengths"]) >= 1
    assert len(report["weaknesses"]) >= 1
    assert len(report["improvement_tips"]) >= 1
    assert len(report["areas_for_improvement"]) >= 1
    assert len(report["action_items"]) >= 1

    # Test JSON parser on markdown code fence
    fence_json = '```json\n{"overall_score": 8.5, "dimension_scores": {"relevance": 8.0, "clarity": 8.0, "depth": 8.0, "examples": 8.0}}\n```'
    parsed = parse_llm_report_json(fence_json)
    assert parsed is not None
    assert parsed["overall_score"] == 8.5

    # Test normalization when score is on 100-point scale
    normalized = normalize_and_validate_report({"overall_score": 85.0}, sample_session)
    assert normalized["overall_score"] == 8.5


# =============================================================================
# 9. Persistence Unit Tests
# =============================================================================

def test_session_persistence_crud():
    """Unit tests for Supabase session persistence helpers."""
    sess_id = str(uuid.uuid4())
    session_data = {
        "id": sess_id,
        "candidate_name": "Persistence Tester",
        "role": "Data Engineer",
        "experience_level": "Senior",
        "interview_type": "technical",
    }

    # Create
    created = run_sync(create_interview_session(session_data))
    assert created["id"] == sess_id
    assert created["role"] == "Data Engineer"
    assert created["role_applied"] == "Data Engineer"
    assert created["status"] == "in_progress"

    # Get
    fetched = run_sync(get_interview_session(sess_id))
    assert fetched is not None
    assert fetched["candidate_name"] == "Persistence Tester"

    # Update
    updated = run_sync(update_interview_session(sess_id, {"question_count": 2}))
    assert updated is not None
    assert updated["question_count"] == 2
    assert updated["current_question_index"] == 2

    # Finalize
    dummy_report = {"overall_score": 8.0, "strengths": ["Strong coding skills"]}
    finalized = run_sync(finalize_interview_session(sess_id, dummy_report))
    assert finalized is not None
    assert finalized["is_complete"] is True
    assert finalized["status"] == "completed"
    assert finalized["report"] == dummy_report
