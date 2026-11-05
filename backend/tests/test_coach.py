"""VOXPREP Backend - AI Communication Coach Agent Unit & Integration Tests
Milestone 3: Phase 3 AI Communication Coach Agent, Session Management, and Profile Learning.

Verifies:
1. Coach start across all 3 supported modes:
   - "conversation" (HTTP 200)
   - "answer_training" (HTTP 200)
   - "english_improvement" (HTTP 200)
2. Coach response evaluation:
   - Clear answer receiving positive reinforcement (correction=None)
   - Grammatical / structural flaws receiving constructive correction (original, improved, reason)
   - Max 1-2 corrections per exchange guardrail enforcement
   - Conversational guardrails (terse answers, "I don't know")
3. Session conclusion (POST /coach/end):
   - Persistence to Supabase coach_sessions
   - Updates to user communication profile (skill_level, weak_areas, strong_areas, sessions_count)
   - Idempotent termination handling
   - Weak area graduation and skill level adaptation
4. Error handling & boundary conditions:
   - Invalid coaching mode returns HTTP 400
   - Empty user_id returns HTTP 400
   - Missing coach session returns HTTP 404
   - Empty user_text returns HTTP 400
   - Responding to completed session returns HTTP 400
   - Missing required payload fields returns HTTP 422
5. Direct agent & persistence unit tests using run_sync (no asyncio socket dependencies).
"""

import uuid
import pytest

from app.agents.coach import (
    CoachSession,
    VALID_COACH_MODES,
    _evaluate_mock_coach_heuristics,
    _extract_json_from_llm_response,
)
from app.db.coach_persistence import (
    classify_correction,
    clear_coach_cache,
    compute_updated_skill_level,
    determine_session_strengths,
    get_coach_session,
    get_user_profile,
    save_coach_session,
    update_user_communication_profile,
)
from app.main import app
from app.routers.coach import session_manager
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
    """Ensures clean in-memory session manager and caches for every test function."""
    session_manager.clear()
    clear_coach_cache()
    yield
    session_manager.clear()
    clear_coach_cache()


@pytest.fixture
def test_client():
    """Provides synchronous LocalClient bound to the application."""
    with LocalClient(app) as client:
        yield client


@pytest.fixture
def sample_user_id():
    """Returns standard seeded demo user UUID."""
    return "00000000-0000-0000-0000-000000000001"


# =============================================================================
# 1. Coach Session Start Tests
# =============================================================================

def test_coach_start_conversation_mode(test_client, sample_user_id):
    """Verifies that conversation mode initializes with friendly conversational prompt."""
    payload = {
        "user_id": sample_user_id,
        "mode": "conversation",
    }
    response = test_client.post("/coach/start", json=payload)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    data = response.json()
    assert "session_id" in data
    assert "opening_message" in data
    assert data.get("mode") == "conversation"
    assert len(data["session_id"]) > 0
    assert len(data["opening_message"]) > 0


def test_coach_start_answer_training_mode(test_client, sample_user_id):
    """Verifies that answer training mode initializes with STAR framework guidance."""
    payload = {
        "user_id": sample_user_id,
        "mode": "answer_training",
    }
    response = test_client.post("/coach/start", json=payload)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    data = response.json()
    assert "session_id" in data
    assert "opening_message" in data
    assert data.get("mode") == "answer_training"
    assert "STAR" in data["opening_message"] or "interview" in data["opening_message"].lower()


def test_coach_start_english_improvement_mode(test_client, sample_user_id):
    """Verifies that english improvement mode initializes with grammar/phrasing prompt."""
    payload = {
        "user_id": sample_user_id,
        "mode": "english_improvement",
    }
    response = test_client.post("/coach/start", json=payload)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    data = response.json()
    assert "session_id" in data
    assert "opening_message" in data
    assert data.get("mode") == "english_improvement"
    assert len(data["opening_message"]) > 0


def test_coach_start_persists_session(test_client, sample_user_id):
    """Verifies that starting a coach session writes record to coach_sessions persistence."""
    payload = {
        "user_id": sample_user_id,
        "mode": "conversation",
    }
    response = test_client.post("/coach/start", json=payload)
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    persisted = run_sync(get_coach_session(session_id))
    assert persisted is not None
    assert persisted["id"] == session_id
    assert persisted["user_id"] == sample_user_id
    assert persisted["mode"] == "conversation"
    assert persisted["is_complete"] is False


# =============================================================================
# 2. Coach Response & Feedback Tests
# =============================================================================

def test_coach_respond_clear_answer_no_correction(test_client, sample_user_id):
    """Verifies that fluent, clear speech receives positive feedback with correction=None."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    payload = {
        "session_id": session_id,
        "user_text": "I really enjoy hiking on mountain trails during clear weekend mornings.",
    }
    response = test_client.post("/coach/respond", json=payload)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    data = response.json()

    assert "coach_message" in data
    assert "next_prompt" in data
    assert data.get("correction") is None
    assert len(data["coach_message"]) > 0
    assert len(data["next_prompt"]) > 0


def test_coach_respond_with_correction_structured(test_client, sample_user_id):
    """Verifies that grammatical flaws receive structured correction with original, improved, reason."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "english_improvement",
    })
    session_id = start_resp.json()["session_id"]

    payload = {
        "session_id": session_id,
        "user_text": "Yesterday I was go to the market and met my colleagues.",
    }
    response = test_client.post("/coach/respond", json=payload)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    data = response.json()

    assert "coach_message" in data
    assert "next_prompt" in data
    correction = data.get("correction")
    assert correction is not None, "Expected correction for grammatical error 'was go'"
    assert "original" in correction
    assert "improved" in correction
    assert "reason" in correction
    assert "was go" in correction["original"].lower()
    assert "went" in correction["improved"].lower()
    assert len(correction["reason"]) > 0


def test_coach_respond_irregular_verb_correction(test_client, sample_user_id):
    """Verifies that irregular verb error ('buyed') receives structured correction ('bought')."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "english_improvement",
    })
    session_id = start_resp.json()["session_id"]

    payload = {
        "session_id": session_id,
        "user_text": "I buyed a new mechanical keyboard yesterday.",
    }
    response = test_client.post("/coach/respond", json=payload)
    assert response.status_code == 200
    data = response.json()
    correction = data.get("correction")
    assert correction is not None
    assert "buyed" in correction["original"].lower()
    assert "bought" in correction["improved"].lower()


def test_coach_respond_uncountable_noun_correction(test_client, sample_user_id):
    """Verifies that uncountable noun error ('fishes') receives structured correction ('fish')."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "english_improvement",
    })
    session_id = start_resp.json()["session_id"]

    payload = {
        "session_id": session_id,
        "user_text": "We saw many fishes swimming in the mountain river.",
    }
    response = test_client.post("/coach/respond", json=payload)
    assert response.status_code == 200
    data = response.json()
    correction = data.get("correction")
    assert correction is not None
    assert "fishes" in correction["original"].lower()
    assert "fish" in correction["improved"].lower()


def test_coach_respond_filler_words_correction(test_client, sample_user_id):
    """Verifies that excessive filler words receive constructive coaching on deliberate pauses."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "english_improvement",
    })
    session_id = start_resp.json()["session_id"]

    payload = {
        "session_id": session_id,
        "user_text": "Um, like, basically I worked on the database migration last month.",
    }
    response = test_client.post("/coach/respond", json=payload)
    assert response.status_code == 200
    data = response.json()
    correction = data.get("correction")
    assert correction is not None
    assert "pause" in correction["improved"].lower() or "filler" in correction["original"].lower()


def test_coach_respond_answer_training_star_guidance(test_client, sample_user_id):
    """Verifies that unstructured interview answers receive STAR framework guidance."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "answer_training",
    })
    session_id = start_resp.json()["session_id"]

    payload = {
        "session_id": session_id,
        "user_text": "I worked on a frontend project for a few months with some coworkers.",
    }
    response = test_client.post("/coach/respond", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "coach_message" in data
    assert "STAR" in data["coach_message"] or (data.get("correction") and "STAR" in data["correction"]["improved"])


def test_coach_respond_answer_training_structured_with_metrics(test_client, sample_user_id):
    """Verifies that structured interview answers with metrics receive praise and no corrections."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "answer_training",
    })
    session_id = start_resp.json()["session_id"]

    payload = {
        "session_id": session_id,
        "user_text": (
            "In my previous role, our team faced high latency (Situation). My task was to optimize queries (Task). "
            "I led the caching layer rewrite (Action), which improved throughput by 40% (Result)."
        ),
    }
    response = test_client.post("/coach/respond", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data.get("correction") is None
    assert "excellent" in data["coach_message"].lower() or "structured" in data["coach_message"].lower()


def test_coach_respond_guardrail_terse_answer(test_client, sample_user_id):
    """Verifies guardrail: 1-word answer receives gentle prompt to expand ideas without penalty."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    response = test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "Good",
    })
    assert response.status_code == 200
    data = response.json()
    assert data.get("correction") is None
    assert "tell me a little bit more" in data["coach_message"].lower() or "more" in data["coach_message"].lower()


def test_coach_respond_guardrail_frustrated_answer(test_client, sample_user_id):
    """Verifies guardrail: 'I don't know' response receives warm encouragement and easier prompt."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    response = test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "I don't know what to say.",
    })
    assert response.status_code == 200
    data = response.json()
    assert data.get("correction") is None
    assert "no worries" in data["coach_message"].lower() or "easier" in data["coach_message"].lower()


def test_coach_respond_max_corrections_guardrail(test_client, sample_user_id):
    """Verifies rule: Coach provides at most 1-2 corrections per exchange to avoid overwhelming candidate."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "english_improvement",
    })
    session_id = start_resp.json()["session_id"]

    # Utterance deliberately packed with multiple grammatical and syntax errors
    flawed_text = (
        "Yesterday I was go to store and I buyed many fishes and then "
        "he do not know where is car and we was very sad."
    )
    response = test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": flawed_text,
    })
    assert response.status_code == 200
    data = response.json()

    correction = data.get("correction")
    if correction:
        if isinstance(correction, list):
            assert len(correction) <= 2, f"Exceeded max 2 corrections: {len(correction)}"
        elif isinstance(correction, dict):
            assert "original" in correction
            assert "improved" in correction


def test_coach_respond_persists_exchanges(test_client, sample_user_id):
    """Verifies that consecutive responses are properly accumulated and persisted."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "I enjoy playing tennis and reading technical books.",
    })
    test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "Yes, I usually play twice a week with my friends.",
    })

    persisted = run_sync(get_coach_session(session_id))
    assert persisted is not None
    assert len(persisted.get("history", [])) == 2


# =============================================================================
# 3. Session End & Profile Learning Tests
# =============================================================================

def test_coach_end_session_success(test_client, sample_user_id):
    """Verifies that ending a session returns completion status, summary, and updated profile."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "english_improvement",
    })
    session_id = start_resp.json()["session_id"]

    test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "I was go to office yesterday.",
    })

    end_resp = test_client.post("/coach/end", json={"session_id": session_id})
    assert end_resp.status_code == 200, f"Expected 200, got: {end_resp.text}"
    data = end_resp.json()

    assert data.get("session_id") == session_id
    assert data.get("status") == "completed"
    assert "summary" in data
    assert "profile_updated" in data
    assert "updated_profile" in data  # Dual-compatibility key

    summary = data["summary"]
    assert "exchanges_count" in summary
    assert summary["exchanges_count"] >= 1

    profile = data["profile_updated"]
    assert "skill_level" in profile
    assert "weak_areas" in profile and isinstance(profile["weak_areas"], list)
    assert "strong_areas" in profile and isinstance(profile["strong_areas"], list)


def test_coach_end_persists_to_coach_sessions(test_client, sample_user_id):
    """Verifies that coach session record in database is marked completed with summary."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "Hello coach, I am ready to practice.",
    })

    test_client.post("/coach/end", json={"session_id": session_id})

    persisted = run_sync(get_coach_session(session_id))
    assert persisted is not None
    assert persisted["is_complete"] is True
    assert persisted["status"] == "completed"
    assert persisted.get("summary") is not None


def test_coach_end_updates_user_profile(test_client, sample_user_id):
    """Verifies that user's persistent communication profile is updated upon session completion."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "english_improvement",
    })
    session_id = start_resp.json()["session_id"]

    test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "Yesterday I was go to the market.",
    })

    test_client.post("/coach/end", json={"session_id": session_id})

    profile = run_sync(get_user_profile(sample_user_id))
    comm_prof = profile.get("communication_profile", profile)
    assert comm_prof["sessions_count"] >= 1


def test_coach_end_idempotent(test_client, sample_user_id):
    """Verifies that calling POST /coach/end multiple times succeeds idempotently without error."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    resp1 = test_client.post("/coach/end", json={"session_id": session_id})
    assert resp1.status_code == 200
    data1 = resp1.json()

    resp2 = test_client.post("/coach/end", json={"session_id": session_id})
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data1["session_id"] == data2["session_id"]
    assert data1["status"] == data2["status"] == "completed"


def test_coach_profile_graduation_on_clean_session(test_client):
    """Verifies that 0 corrections across multiple exchanges graduates weak areas to strong areas."""
    user_id = str(uuid.uuid4())

    # Seed user with weak area
    user_prof = run_sync(get_user_profile(user_id))
    run_sync(update_user_communication_profile(user_id, {
        "mode": "english_improvement",
        "history": [{
            "user_text": "was go",
            "correction": {"original": "was go", "improved": "went", "reason": "grammar tense"},
        }],
    }))

    # Now run clean session in english_improvement
    start_resp = test_client.post("/coach/start", json={
        "user_id": user_id,
        "mode": "english_improvement",
    })
    sid = start_resp.json()["session_id"]

    # 3 clean turns
    test_client.post("/coach/respond", json={"session_id": sid, "user_text": "I went to work early today."})
    test_client.post("/coach/respond", json={"session_id": sid, "user_text": "I completed all tasks efficiently."})
    test_client.post("/coach/respond", json={"session_id": sid, "user_text": "Then I relaxed with my family in the evening."})

    end_resp = test_client.post("/coach/end", json={"session_id": sid})
    assert end_resp.status_code == 200
    profile = end_resp.json()["profile_updated"]

    # Verify that grammar & syntax graduated to strong_areas
    assert "grammar & syntax" in profile["strong_areas"] or "grammatical accuracy" in profile["strong_areas"]


# =============================================================================
# 4. Boundary & Error Condition Tests (400, 404, 422)
# =============================================================================

def test_coach_start_invalid_mode_returns_400(test_client, sample_user_id):
    """Verifies that unsupported or arbitrary modes return HTTP 400 Bad Request."""
    payload = {
        "user_id": sample_user_id,
        "mode": "hostile_cross_examination",
    }
    response = test_client.post("/coach/start", json=payload)
    assert response.status_code == 400, f"Expected 400 for invalid mode, got: {response.status_code}"
    assert "invalid coach mode" in response.text.lower() or "mode" in response.text.lower()


def test_coach_start_empty_user_id_returns_400(test_client):
    """Verifies that whitespace-only user_id returns HTTP 400 Bad Request."""
    payload = {
        "user_id": "   ",
        "mode": "conversation",
    }
    response = test_client.post("/coach/start", json=payload)
    assert response.status_code == 400


def test_coach_respond_empty_user_text_returns_400(test_client, sample_user_id):
    """Verifies that empty user_text returns HTTP 400 Bad Request."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    # Empty string
    resp1 = test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "",
    })
    assert resp1.status_code == 400

    # Whitespace only
    resp2 = test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "   \n\t  ",
    })
    assert resp2.status_code == 400


def test_coach_respond_missing_session_returns_404(test_client):
    """Verifies that submitting response to non-existent session UUID returns HTTP 404."""
    non_existent_sid = str(uuid.uuid4())
    payload = {
        "session_id": non_existent_sid,
        "user_text": "Hello coach?",
    }
    response = test_client.post("/coach/respond", json=payload)
    assert response.status_code == 404
    assert "not found" in response.text.lower()


def test_coach_respond_to_completed_session_returns_400(test_client, sample_user_id):
    """Verifies that attempting to respond to an already terminated session returns HTTP 400."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    test_client.post("/coach/end", json={"session_id": session_id})

    response = test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "Can I still speak?",
    })
    assert response.status_code == 400
    assert "already completed" in response.text.lower()


def test_coach_end_missing_session_returns_404(test_client):
    """Verifies that ending a non-existent session returns HTTP 404."""
    non_existent_sid = str(uuid.uuid4())
    response = test_client.post("/coach/end", json={"session_id": non_existent_sid})
    assert response.status_code == 404
    assert "not found" in response.text.lower()


def test_coach_validation_missing_fields_returns_422(test_client):
    """Verifies that omitting required schema parameters raises HTTP 422 Unprocessable Entity."""
    # 1. Missing mode in start
    resp1 = test_client.post("/coach/start", json={"user_id": str(uuid.uuid4())})
    assert resp1.status_code == 422

    # 2. Missing user_id in start
    resp2 = test_client.post("/coach/start", json={"mode": "conversation"})
    assert resp2.status_code == 422

    # 3. Missing session_id in respond
    resp3 = test_client.post("/coach/respond", json={"user_text": "Sample text"})
    assert resp3.status_code == 422

    # 4. Missing session_id in end
    resp4 = test_client.post("/coach/end", json={})
    assert resp4.status_code == 422


# =============================================================================
# 5. Direct Unit Tests (via run_sync)
# =============================================================================

def test_coach_session_unit_modes_via_run_sync():
    """Directly tests CoachSession lifecycle and prompt construction across all modes."""
    for mode in ["conversation", "answer_training", "english_improvement"]:
        session = CoachSession(
            session_id=str(uuid.uuid4()),
            user_id="unit-tester",
            mode=mode,
        )
        opening = run_sync(session.start_session())
        assert isinstance(opening, str)
        assert len(opening) > 0

        # Process standard response
        res = run_sync(session.process_response("I practiced speaking today."))
        assert "coach_message" in res
        assert "next_prompt" in res
        assert "correction" in res

        # End session
        end_data = run_sync(session.end_session())
        assert end_data["status"] == "completed"
        assert "summary" in end_data


def test_coach_persistence_unit_via_run_sync():
    """Directly tests database persistence CRUD and normalization via run_sync."""
    sess_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    # 1. Save initial session
    data = {
        "id": sess_id,
        "user_id": user_id,
        "mode": "english_improvement",
        "history": [{"user_text": "Hello", "coach_message": "Hi"}],
    }
    saved = run_sync(save_coach_session(sess_id, data))
    assert saved["id"] == sess_id
    assert saved["is_complete"] is False

    # 2. Retrieve session
    loaded = run_sync(get_coach_session(sess_id))
    assert loaded is not None
    assert loaded["mode"] == "english_improvement"

    # 3. Update communication profile
    profile_result = run_sync(update_user_communication_profile(user_id, {
        "id": sess_id,
        "user_id": user_id,
        "mode": "english_improvement",
        "history": [{
            "user_text": "was go",
            "correction": {
                "original": "was go",
                "improved": "went",
                "reason": "past tense verb",
            },
        }],
    }))
    comm_prof = profile_result.get("communication_profile", profile_result)
    assert comm_prof["sessions_count"] >= 1


def test_classify_correction_taxonomy():
    """Verifies that all 7 taxonomy categories are correctly classified."""
    assert classify_correction({"reason": "filler words like um", "original": "um", "improved": "[pause]"}) == "filler words"
    assert classify_correction({"reason": "use STAR framework", "original": "xyz", "improved": "STAR"}) == "STAR structure"
    assert classify_correction({"reason": "be more concise and brief", "original": "xyz", "improved": "abc"}) == "conciseness"
    assert classify_correction({"reason": "past tense verb agreement", "original": "was go", "improved": "went"}) == "grammar & syntax"
    assert classify_correction({"reason": "use professional vocabulary", "original": "gonna", "improved": "intend to"}) == "professional vocabulary"
    assert classify_correction({"reason": "improves clarity and removes ambiguity", "original": "thing", "improved": "API endpoint"}) == "clarity"
    assert classify_correction({"reason": "provide specific concrete examples and metric", "original": "good", "improved": "99.9% uptime"}) == "concrete examples"


def test_compute_updated_skill_level_logic():
    """Verifies that skill level progression transitions properly."""
    # Beginner to intermediate with low correction rate
    assert compute_updated_skill_level("beginner", 0.2, 3, 1) == "intermediate"

    # Intermediate to advanced with zero corrections
    assert compute_updated_skill_level("intermediate", 0.0, 3, 1) == "advanced"

    # Intermediate to beginner with high correction rate
    assert compute_updated_skill_level("intermediate", 0.8, 3, 1) == "beginner"

    # Advanced demoted to intermediate on high error rate
    assert compute_updated_skill_level("advanced", 0.6, 3, 1) == "intermediate"
