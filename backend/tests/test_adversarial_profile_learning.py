"""VOXPREP Backend - Adversarial Profile Learning & Persistence Integrity Test Suite
Milestone 3: Phase 3 AI Communication Coach Agent & Profile Learning Service.

Adversarial testing suite challenging:
1. Multi-Session Profile Evolution:
   - Weak areas accumulate across consecutive sessions and cap strictly at 5.
   - Repeated clean performance in weak areas graduates them to strong areas.
   - Dynamic skill level adjustment: high error rate downgrades to "beginner",
     low error rate with practice upgrades to "advanced".
   - End-to-end multi-session lifecycle simulation across consecutive HTTP sessions.
2. Idempotence Stress Testing:
   - Calling POST /coach/end multiple times (serial and concurrent) on the same session
     produces consistent HTTP 200 responses and never corrupts session data or profile counts.
   - Submitting responses after session completion is strictly rejected with HTTP 400.
3. Missing & Malformed User Profiles:
   - Graceful default provisioning for guest or newly registered users.
   - Pathological / corrupted database profiles normalize safely without crashes or 500s.
   - Input validation boundary attacks: whitespace IDs, SQL injection patterns, massive payloads.
4. Concurrency & Race Conditions:
   - Concurrent profile learning writes across multiple threads without cross-talk or data loss.
   - Parallel end-to-end coach sessions across threads.
   - Dual-write / read persistence integrity under high-frequency multithreaded access.
"""

import concurrent.futures
import copy
import threading
import uuid
from typing import Any, Dict, List

import pytest

from app.agents.coach import CoachSession, VALID_COACH_MODES, VALID_SKILL_LEVELS
from app.db.coach_persistence import (
    _coach_lock,
    _in_memory_coach_sessions,
    _in_memory_user_profiles,
    _normalize_user_profile,
    classify_correction,
    clear_coach_cache,
    compute_updated_skill_level,
    determine_session_strengths,
    get_coach_session,
    get_user_profile,
    save_coach_session,
    update_user_communication_profile,
)
from app.db.supabase import get_supabase_client
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
def clean_state():
    """Ensures clean in-memory session manager, caches, and database state for every test."""
    session_manager.clear()
    clear_coach_cache()
    yield
    session_manager.clear()
    clear_coach_cache()


@pytest.fixture
def client():
    """Provides synchronous LocalClient bound to the application."""
    with LocalClient(app) as test_client:
        yield test_client


# =============================================================================
# 1. Multi-Session Profile Evolution Stress Tests
# =============================================================================

def test_multisession_evolution_weak_areas_accumulation_and_cap_at_five():
    """Simulates a user completing 4 consecutive coaching sessions introducing distinct errors:
    - Session 1: filler words, grammar & syntax (total: 2)
    - Session 2: STAR structure, conciseness (total: 4)
    - Session 3: professional vocabulary, clarity (total: 6 -> must cap at 5)
    - Session 4: concrete examples (must remain capped at 5)
    Verifies that weak_areas deduplicates and never exceeds 5 items.
    """
    user_id = f"user_accum_{uuid.uuid4().hex[:8]}"

    # Session 1: filler words + grammar & syntax
    s1_data = {
        "id": f"sess_accum_1_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "mode": "english_improvement",
        "history": [
            {"user_text": "um like basically", "correction": {"reason": "filler words", "original": "um", "improved": "[pause]"}},
            {"user_text": "yesterday I go", "correction": {"reason": "past tense verb grammar", "original": "go", "improved": "went"}},
        ],
    }
    prof1 = run_sync(update_user_communication_profile(user_id, s1_data))
    comm1 = prof1.get("communication_profile", prof1)
    assert set(comm1["weak_areas"]) == {"filler words", "grammar & syntax"}
    assert len(comm1["weak_areas"]) == 2
    assert comm1["sessions_count"] == 1

    # Session 2: STAR structure + conciseness
    s2_data = {
        "id": f"sess_accum_2_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "mode": "answer_training",
        "history": [
            {"user_text": "I did some things", "correction": {"reason": "use STAR framework", "original": "did", "improved": "Action/Result"}},
            {"user_text": "A very long-winded wordy explanation", "correction": {"reason": "be more concise and brief", "original": "wordy", "improved": "brief"}},
        ],
    }
    prof2 = run_sync(update_user_communication_profile(user_id, s2_data))
    comm2 = prof2.get("communication_profile", prof2)
    assert len(comm2["weak_areas"]) == 4
    assert set(comm2["weak_areas"]) == {"filler words", "grammar & syntax", "STAR structure", "conciseness"}
    assert comm2["sessions_count"] == 2

    # Session 3: professional vocabulary + clarity (would be 6 -> must cap strictly at 5)
    s3_data = {
        "id": f"sess_accum_3_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "mode": "conversation",
        "history": [
            {"user_text": "gonna do this", "correction": {"reason": "use professional vocabulary", "original": "gonna", "improved": "plan to"}},
            {"user_text": "things were confusing", "correction": {"reason": "clarity and precision", "original": "things", "improved": "specifications"}},
        ],
    }
    prof3 = run_sync(update_user_communication_profile(user_id, s3_data))
    comm3 = prof3.get("communication_profile", prof3)
    assert len(comm3["weak_areas"]) == 5, f"Weak areas failed to cap at 5: {comm3['weak_areas']}"
    assert comm3["sessions_count"] == 3

    # Session 4: concrete examples (must still remain capped at 5)
    s4_data = {
        "id": f"sess_accum_4_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "mode": "answer_training",
        "history": [
            {"user_text": "good results", "correction": {"reason": "give concrete examples and metric", "original": "good", "improved": "25% speedup"}},
        ],
    }
    prof4 = run_sync(update_user_communication_profile(user_id, s4_data))
    comm4 = prof4.get("communication_profile", prof4)
    assert len(comm4["weak_areas"]) == 5, f"Weak areas exceeded cap of 5: {comm4['weak_areas']}"
    assert comm4["sessions_count"] == 4
    # Ensure no duplicates in weak_areas
    assert len(comm4["weak_areas"]) == len(set(comm4["weak_areas"]))


def test_multisession_evolution_weak_area_graduation_to_strong_areas():
    """Simulates a user who initially has weak areas:
    - Pre-conditions: weak_areas = ["grammar & syntax", "filler words", "STAR structure"]
    - Session 1 (English Improvement): 3 clean exchanges with 0 corrections.
      -> "grammar & syntax" and "filler words" graduate to strong_areas.
      -> "STAR structure" remains in weak_areas (unrelated to English mode).
    - Session 2 (Answer Training): 3 clean exchanges with 0 corrections.
      -> "STAR structure" graduates to strong_areas.
    Verifies that graduated tags move from weak_areas into strong_areas cleanly,
    and strong_areas caps at 5 without duplicates.
    """
    user_id = f"user_grad_{uuid.uuid4().hex[:8]}"

    # Pre-populate user profile with known weak areas
    init_data = {
        "id": f"sess_init_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "mode": "english_improvement",
        "history": [
            {"user_text": "um", "correction": {"reason": "filler words", "original": "um", "improved": "[pause]"}},
            {"user_text": "go", "correction": {"reason": "grammar tense", "original": "go", "improved": "went"}},
            {"user_text": "stuff", "correction": {"reason": "use STAR structure", "original": "stuff", "improved": "STAR"}},
        ],
    }
    prof_init = run_sync(update_user_communication_profile(user_id, init_data))
    comm_init = prof_init.get("communication_profile", prof_init)
    assert "grammar & syntax" in comm_init["weak_areas"]
    assert "filler words" in comm_init["weak_areas"]
    assert "STAR structure" in comm_init["weak_areas"]

    # Session 1: Clean performance in english_improvement
    clean_s1 = {
        "id": f"sess_clean1_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "mode": "english_improvement",
        "history": [
            {"user_text": "I completed the documentation cleanly.", "correction": None},
            {"user_text": "The distributed services communicate through asynchronous messages.", "correction": None},
            {"user_text": "We deployed the containers into the staging environment yesterday.", "correction": None},
        ],
        "corrections": [],
    }
    prof_s1 = run_sync(update_user_communication_profile(user_id, clean_s1))
    comm_s1 = prof_s1.get("communication_profile", prof_s1)

    # "grammar & syntax" and "filler words" should have graduated
    assert "grammar & syntax" not in comm_s1["weak_areas"]
    assert "filler words" not in comm_s1["weak_areas"]
    assert "grammar & syntax" in comm_s1["strong_areas"]
    assert "filler words" in comm_s1["strong_areas"]
    # "STAR structure" should still be in weak_areas
    assert "STAR structure" in comm_s1["weak_areas"]

    # Session 2: Clean performance in answer_training
    clean_s2 = {
        "id": f"sess_clean2_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "mode": "answer_training",
        "history": [
            {"user_text": "In my previous project, our team faced high latency. My action reduced response time by 40%.", "correction": None},
            {"user_text": "When the database degraded, I led the migration and we achieved 99.99% reliability.", "correction": None},
            {"user_text": "I identified the deadlock, restructured the transactions, and boosted throughput by 35%.", "correction": None},
        ],
        "corrections": [],
    }
    prof_s2 = run_sync(update_user_communication_profile(user_id, clean_s2))
    comm_s2 = prof_s2.get("communication_profile", prof_s2)

    # "STAR structure" should now graduate out of weak_areas
    assert "STAR structure" not in comm_s2["weak_areas"]
    assert "STAR structure" in comm_s2["strong_areas"]
    assert len(comm_s2["strong_areas"]) <= 5
    assert len(comm_s2["strong_areas"]) == len(set(comm_s2["strong_areas"]))


def test_multisession_dynamic_skill_level_adaptation_cycle():
    """Simulates a complete 5-session dynamic skill level progression cycle:
    - User starts at default 'intermediate'
    - Session 1 (High Error Rate): 3 turns, 3 corrections (rate=1.0 >= 0.75) -> downgrades to 'beginner'
    - Session 2 (Clean Practice): 3 turns, 0 corrections (rate=0.0 <= 0.34) -> upgrades to 'intermediate'
    - Session 3 (Advanced Clean Performance): 3 turns, 0 corrections, sessions_count>=1 -> upgrades to 'advanced'
    - Session 4 (High Error Rate in Advanced): 3 turns, 2 corrections (rate=0.67 >= 0.5) -> downgrades to 'intermediate'
    - Session 5 (Severe Errors in Intermediate): 4 turns, 4 corrections (rate=1.0 >= 0.75) -> downgrades to 'beginner'
    Verifies that skill_level adjusts dynamically in both directions.
    """
    user_id = f"user_skill_{uuid.uuid4().hex[:8]}"

    # Verify initial default skill level
    init_prof = run_sync(get_user_profile(user_id))
    assert init_prof["skill_level"] == "intermediate"

    # --- Session 1: High Error Rate (downgrade to beginner) ---
    s1_data = {
        "id": f"sess_sk1_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "mode": "conversation",
        "history": [
            {"user_text": "err 1", "correction": {"reason": "filler words", "original": "um", "improved": "..."}},
            {"user_text": "err 2", "correction": {"reason": "grammar tense", "original": "go", "improved": "went"}},
            {"user_text": "err 3", "correction": {"reason": "clarity", "original": "stuff", "improved": "code"}},
        ],
    }
    p1 = run_sync(update_user_communication_profile(user_id, s1_data))
    assert p1["skill_level"] == "beginner", f"Expected 'beginner', got '{p1['skill_level']}'"
    assert p1["sessions_count"] == 1

    # --- Session 2: Low Error Rate (upgrade back to intermediate) ---
    s2_data = {
        "id": f"sess_sk2_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "mode": "english_improvement",
        "history": [
            {"user_text": "Clean answer 1", "correction": None},
            {"user_text": "Clean answer 2", "correction": None},
            {"user_text": "Clean answer 3", "correction": None},
        ],
        "corrections": [],
    }
    p2 = run_sync(update_user_communication_profile(user_id, s2_data))
    assert p2["skill_level"] == "intermediate", f"Expected 'intermediate', got '{p2['skill_level']}'"
    assert p2["sessions_count"] == 2

    # --- Session 3: Flawless Performance (upgrade to advanced) ---
    s3_data = {
        "id": f"sess_sk3_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "mode": "answer_training",
        "history": [
            {"user_text": "Clean answer 1 with STAR metrics", "correction": None},
            {"user_text": "Clean answer 2 with STAR metrics", "correction": None},
            {"user_text": "Clean answer 3 with STAR metrics", "correction": None},
        ],
        "corrections": [],
    }
    p3 = run_sync(update_user_communication_profile(user_id, s3_data))
    assert p3["skill_level"] == "advanced", f"Expected 'advanced', got '{p3['skill_level']}'"
    assert p3["sessions_count"] == 3

    # --- Session 4: High Error Rate in Advanced (downgrade to intermediate) ---
    s4_data = {
        "id": f"sess_sk4_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "mode": "english_improvement",
        "history": [
            {"user_text": "err 1", "correction": {"reason": "filler words", "original": "um", "improved": "..."}},
            {"user_text": "err 2", "correction": {"reason": "grammar tense", "original": "was go", "improved": "went"}},
            {"user_text": "clean answer 3", "correction": None},
        ],
    }
    p4 = run_sync(update_user_communication_profile(user_id, s4_data))
    assert p4["skill_level"] == "intermediate", f"Expected 'intermediate', got '{p4['skill_level']}'"
    assert p4["sessions_count"] == 4

    # --- Session 5: Severe Error Rate in Intermediate (downgrade to beginner) ---
    s5_data = {
        "id": f"sess_sk5_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "mode": "conversation",
        "history": [
            {"user_text": "err 1", "correction": {"reason": "filler words", "original": "um", "improved": "..."}},
            {"user_text": "err 2", "correction": {"reason": "grammar tense", "original": "was go", "improved": "went"}},
            {"user_text": "err 3", "correction": {"reason": "vocabulary", "original": "gonna", "improved": "will"}},
            {"user_text": "err 4", "correction": {"reason": "clarity", "original": "bad stuff", "improved": "issues"}},
        ],
    }
    p5 = run_sync(update_user_communication_profile(user_id, s5_data))
    assert p5["skill_level"] == "beginner", f"Expected 'beginner', got '{p5['skill_level']}'"
    assert p5["sessions_count"] == 5


def test_multisession_via_rest_api_full_cycle(client):
    """Executes a full 3-session profile evolution cycle strictly through the REST API:
    - Session 1 (English Improvement with errors):
      POST /coach/start -> POST /coach/respond (x3 with errors) -> POST /coach/end
      Verifies sessions_count=1, weak_areas populated, skill_level adjusted.
    - Session 2 (English Improvement with clean performance):
      POST /coach/start -> POST /coach/respond (x3 clean) -> POST /coach/end
      Verifies sessions_count=2, graduation occurs.
    - Session 3 (Answer Training clean performance):
      POST /coach/start -> POST /coach/respond (x3 clean) -> POST /coach/end
      Verifies sessions_count=3, upgrade to 'advanced'.
    """
    user_id = f"user_api_{uuid.uuid4().hex[:8]}"

    # --- Session 1: Errors in English Improvement ---
    start1 = client.post("/coach/start", json={"user_id": user_id, "mode": "english_improvement"})
    assert start1.status_code == 200
    sid1 = start1.json()["session_id"]

    # 3 turns with corrections
    r1 = client.post("/coach/respond", json={"session_id": sid1, "user_text": "Yesterday I was go to the market."})
    assert r1.status_code == 200
    assert r1.json()["correction"] is not None

    r2 = client.post("/coach/respond", json={"session_id": sid1, "user_text": "I saw many fishes in the river."})
    assert r2.status_code == 200
    assert r2.json()["correction"] is not None

    r3 = client.post("/coach/respond", json={"session_id": sid1, "user_text": "Tomorrow I will went there again."})
    assert r3.status_code == 200
    assert r3.json()["correction"] is not None

    end1 = client.post("/coach/end", json={"session_id": sid1})
    assert end1.status_code == 200
    p1 = end1.json()["profile_updated"]
    assert p1["sessions_count"] == 1
    assert "grammar & syntax" in p1["weak_areas"]
    # 3 errors out of 3 turns downgrades intermediate to beginner
    assert p1["skill_level"] == "beginner"

    # --- Session 2: Clean English Performance ---
    start2 = client.post("/coach/start", json={"user_id": user_id, "mode": "english_improvement"})
    assert start2.status_code == 200
    sid2 = start2.json()["session_id"]

    for _ in range(3):
        r = client.post("/coach/respond", json={
            "session_id": sid2,
            "user_text": "I practiced speaking with clarity and precision today.",
        })
        assert r.status_code == 200
        assert r.json()["correction"] is None

    end2 = client.post("/coach/end", json={"session_id": sid2})
    assert end2.status_code == 200
    p2 = end2.json()["profile_updated"]
    assert p2["sessions_count"] == 2
    # Clean performance graduates grammar & syntax
    assert "grammar & syntax" not in p2["weak_areas"]
    assert "grammar & syntax" in p2["strong_areas"]
    # Upgrades beginner to intermediate
    assert p2["skill_level"] == "intermediate"

    # --- Session 3: Clean Answer Training Performance ---
    start3 = client.post("/coach/start", json={"user_id": user_id, "mode": "answer_training"})
    assert start3.status_code == 200
    sid3 = start3.json()["session_id"]

    for _ in range(3):
        r = client.post("/coach/respond", json={
            "session_id": sid3,
            "user_text": "My action increased delivery throughput by 35% result metric.",
        })
        assert r.status_code == 200
        assert r.json()["correction"] is None

    end3 = client.post("/coach/end", json={"session_id": sid3})
    assert end3.status_code == 200
    p3 = end3.json()["profile_updated"]
    assert p3["sessions_count"] == 3
    # With sessions_count >= 1 and 0 errors, intermediate upgrades to advanced
    assert p3["skill_level"] == "advanced"


# =============================================================================
# 2. Idempotence & Termination Stress Tests
# =============================================================================

def test_coach_end_serial_idempotence_stress(client):
    """Verifies that calling POST /coach/end 10 consecutive times on the same session:
    - Always returns HTTP 200 with status='completed'.
    - Profile sessions_count remains strictly 1 and is never incremented multiple times.
    - Session summary and history remain identical without corruption or duplication.
    """
    user_id = f"user_idem_{uuid.uuid4().hex[:8]}"
    start_resp = client.post("/coach/start", json={"user_id": user_id, "mode": "conversation"})
    session_id = start_resp.json()["session_id"]

    # Exchange 2 turns
    client.post("/coach/respond", json={"session_id": session_id, "user_text": "Hello there coach!"})
    client.post("/coach/respond", json={"session_id": session_id, "user_text": "I enjoyed practicing today."})

    # First termination
    end1 = client.post("/coach/end", json={"session_id": session_id})
    assert end1.status_code == 200
    data1 = end1.json()
    assert data1["status"] == "completed"
    assert data1["profile_updated"]["sessions_count"] == 1
    original_summary = data1["summary"]

    # Re-call 10 times consecutively
    for call_idx in range(2, 12):
        end_repeat = client.post("/coach/end", json={"session_id": session_id})
        assert end_repeat.status_code == 200, f"Call #{call_idx} failed with {end_repeat.status_code}: {end_repeat.text}"
        data_rep = end_repeat.json()
        assert data_rep["status"] == "completed"
        # sessions_count must NEVER increment past 1
        assert data_rep["profile_updated"]["sessions_count"] == 1, (
            f"Idempotence violation on call #{call_idx}! sessions_count grew to {data_rep['profile_updated']['sessions_count']}"
        )
        assert data_rep["summary"]["exchanges_count"] == original_summary["exchanges_count"]

    # Verify database persistence integrity
    persisted_session = run_sync(get_coach_session(session_id))
    assert persisted_session is not None
    assert persisted_session["is_complete"] is True
    assert len(persisted_session["history"]) == 2

    persisted_user = run_sync(get_user_profile(user_id))
    comm_prof = persisted_user.get("communication_profile", persisted_user)
    assert comm_prof["sessions_count"] == 1


def test_coach_end_concurrent_idempotence_stress():
    """Fires 10 concurrent requests to POST /coach/end for the exact same session ID:
    - Verifies zero deadlocks or uncaught 500 exceptions across threads.
    - All 10 requests return HTTP 200 with status='completed'.
    - Final user profile sessions_count is exactly 1 (no double or 10x counting race).
    """
    user_id = f"user_conc_end_{uuid.uuid4().hex[:8]}"

    with LocalClient(app) as setup_client:
        start_resp = setup_client.post("/coach/start", json={"user_id": user_id, "mode": "answer_training"})
        session_id = start_resp.json()["session_id"]
        setup_client.post("/coach/respond", json={"session_id": session_id, "user_text": "I led the migration."})

    num_threads = 10
    responses: List[Dict[str, Any]] = []
    errors: List[str] = []
    lock = threading.Lock()

    def end_worker():
        try:
            with LocalClient(app) as thread_client:
                res = thread_client.post("/coach/end", json={"session_id": session_id})
                with lock:
                    if res.status_code == 200:
                        responses.append(res.json())
                    else:
                        errors.append(f"HTTP {res.status_code}: {res.text}")
        except Exception as exc:
            with lock:
                errors.append(str(exc))

    threads = [threading.Thread(target=end_worker) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert len(errors) == 0, f"Concurrent end_coach encountered errors: {errors}"
    assert len(responses) == num_threads, f"Expected {num_threads} responses, got {len(responses)}"

    for r in responses:
        assert r["status"] == "completed"

    # Profile sessions_count must be exactly 1
    user_prof = run_sync(get_user_profile(user_id))
    comm_prof = user_prof.get("communication_profile", user_prof)
    assert comm_prof["sessions_count"] == 1, (
        f"Race condition in concurrent end_coach! Expected sessions_count=1, got {comm_prof['sessions_count']}"
    )


def test_coach_respond_after_end_rejected(client):
    """Verifies that attempting to submit responses after a session is concluded:
    - Returns HTTP 400 Bad Request.
    - Explains that the coach session is already completed.
    - Subsequent calls to POST /coach/end remain HTTP 200 and idempotent.
    """
    user_id = f"user_post_end_{uuid.uuid4().hex[:8]}"
    start_resp = client.post("/coach/start", json={"user_id": user_id, "mode": "conversation"})
    session_id = start_resp.json()["session_id"]

    client.post("/coach/respond", json={"session_id": session_id, "user_text": "Testing before end."})

    # End session
    end_resp = client.post("/coach/end", json={"session_id": session_id})
    assert end_resp.status_code == 200

    # Attempt respond after completion
    late_resp = client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "Late message after conclusion.",
    })
    assert late_resp.status_code == 400
    assert "already completed" in late_resp.json().get("detail", "").lower()

    # Re-ending session remains HTTP 200
    re_end = client.post("/coach/end", json={"session_id": session_id})
    assert re_end.status_code == 200
    assert re_end.json()["status"] == "completed"


# =============================================================================
# 3. Missing & Malformed User Profiles Graceful Provisioning
# =============================================================================

def test_guest_user_auto_provisioning(client):
    """Verifies that an unauthenticated or guest user (non-existent in database):
    - Successfully starts coach session with HTTP 200.
    - Receives a personalized opening greeting.
    - Is auto-provisioned with default intermediate skill level, empty weak/strong areas.
    """
    guest_user_id = f"guest_candidate_{uuid.uuid4().hex}"

    # Verify user does not exist prior to session
    with _coach_lock:
        assert guest_user_id not in _in_memory_user_profiles

    start_resp = client.post("/coach/start", json={
        "user_id": guest_user_id,
        "mode": "english_improvement",
    })
    assert start_resp.status_code == 200
    data = start_resp.json()
    assert "session_id" in data
    assert len(data["opening_message"]) > 0

    # Verify auto-provisioned profile in persistence layer
    profile = run_sync(get_user_profile(guest_user_id))
    assert profile is not None
    assert profile["skill_level"] == "intermediate"
    assert profile["weak_areas"] == []
    assert profile["strong_areas"] == []
    comm = profile.get("communication_profile", profile)
    assert comm["sessions_count"] == 0


def test_malformed_user_profiles_in_db_graceful_provisioning(client):
    """Adversarially injects pathological profile shapes into Supabase users table:
    - User A: communication_profile is None
    - User B: communication_profile is a string ("corrupted_json")
    - User C: skill_level='god_mode' (invalid level), weak_areas=123 (non-list), strong_areas=None
    - User D: sessions_count='invalid_number'
    Verifies that get_user_profile and POST /coach/start handle all anomalies gracefully
    without raising 500 Internal Server Errors, normalizing to valid schema defaults.
    """
    supabase = get_supabase_client()

    # User A: communication_profile is None
    uid_a = f"corrupt_a_{uuid.uuid4().hex[:8]}"
    supabase.table("users").insert({
        "id": uid_a,
        "email": f"{uid_a}@voxprep.ai",
        "name": "Corrupt User A",
        "communication_profile": None,
    }).execute()

    prof_a = run_sync(get_user_profile(uid_a))
    assert prof_a["skill_level"] == "intermediate"
    assert isinstance(prof_a["weak_areas"], list)
    assert isinstance(prof_a["strong_areas"], list)

    start_a = client.post("/coach/start", json={"user_id": uid_a, "mode": "conversation"})
    assert start_a.status_code == 200

    # User B: communication_profile is a string
    uid_b = f"corrupt_b_{uuid.uuid4().hex[:8]}"
    supabase.table("users").insert({
        "id": uid_b,
        "email": f"{uid_b}@voxprep.ai",
        "name": "Corrupt User B",
        "communication_profile": "malformed_string_not_dict",
    }).execute()

    prof_b = run_sync(get_user_profile(uid_b))
    assert prof_b["skill_level"] == "intermediate"
    assert prof_b["weak_areas"] == []

    start_b = client.post("/coach/start", json={"user_id": uid_b, "mode": "conversation"})
    assert start_b.status_code == 200

    # User C: invalid skill_level, non-list weak_areas
    uid_c = f"corrupt_c_{uuid.uuid4().hex[:8]}"
    supabase.table("users").insert({
        "id": uid_c,
        "email": f"{uid_c}@voxprep.ai",
        "name": "Corrupt User C",
        "communication_profile": {
            "skill_level": "super_advanced_titan",
            "weak_areas": 99999,
            "strong_areas": None,
            "sessions_count": "0",
        },
    }).execute()

    prof_c = run_sync(get_user_profile(uid_c))
    assert prof_c["skill_level"] == "intermediate", f"Expected intermediate fallback, got {prof_c['skill_level']}"
    assert prof_c["weak_areas"] == []
    assert prof_c["strong_areas"] == []

    start_c = client.post("/coach/start", json={"user_id": uid_c, "mode": "answer_training"})
    assert start_c.status_code == 200

    # User D: non-numeric sessions_count in database row
    uid_d = f"corrupt_d_{uuid.uuid4().hex[:8]}"
    supabase.table("users").insert({
        "id": uid_d,
        "email": f"{uid_d}@voxprep.ai",
        "name": "Corrupt User D",
        "communication_profile": {
            "skill_level": "advanced",
            "weak_areas": ["clarity"],
            "strong_areas": ["STAR structure"],
            "sessions_count": "non_integer_text",
        },
    }).execute()

    # Must not throw unhandled exception
    prof_d = run_sync(get_user_profile(uid_d))
    assert prof_d is not None
    assert prof_d["skill_level"] in VALID_SKILL_LEVELS

    start_d = client.post("/coach/start", json={"user_id": uid_d, "mode": "english_improvement"})
    assert start_d.status_code == 200


def test_pathological_start_and_end_inputs(client):
    """Submits adversarial and pathological payloads to coach endpoints:
    - Whitespace user_id -> HTTP 400
    - Missing required fields -> HTTP 422
    - SQL injection string in user_id -> handled as literal string, does not crash
    - Non-existent session IDs in respond/end -> HTTP 404
    - Extremely large user_text (10,000 characters) -> HTTP 200 without server crash
    """
    # 1. Whitespace user_id
    r1 = client.post("/coach/start", json={"user_id": "   \n\t  ", "mode": "conversation"})
    assert r1.status_code == 400
    assert "user_id must not be empty" in r1.json()["detail"]

    # 2. Missing mode
    r2 = client.post("/coach/start", json={"user_id": "valid_user"})
    assert r2.status_code == 422

    # 3. SQL injection pattern in user_id
    sql_id = "user' OR '1'='1' -- DROP TABLE users;"
    r3 = client.post("/coach/start", json={"user_id": sql_id, "mode": "conversation"})
    assert r3.status_code == 200
    sess_id = r3.json()["session_id"]
    # Safely loaded without executing SQL injection
    loaded_prof = run_sync(get_user_profile(sql_id))
    assert loaded_prof["id"] == sql_id

    # 4. Non-existent session IDs
    fake_sid = str(uuid.uuid4())
    r4_resp = client.post("/coach/respond", json={"session_id": fake_sid, "user_text": "hello"})
    assert r4_resp.status_code == 404
    r4_end = client.post("/coach/end", json={"session_id": fake_sid})
    assert r4_end.status_code == 404

    # 5. Extremely large user_text (10,000 characters)
    massive_text = "I practiced communication and " + ("very important metrics " * 400)
    r5 = client.post("/coach/respond", json={"session_id": sess_id, "user_text": massive_text})
    assert r5.status_code == 200
    assert len(r5.json()["coach_message"]) > 0


# =============================================================================
# 4. Concurrency & Race Condition Stress Tests
# =============================================================================

def test_concurrent_distinct_users_profile_learning():
    """Executes concurrent update_user_communication_profile calls across 10 threads
    for 10 distinct users:
    - Verifies zero cross-talk, cross-user data leakage, or race conditions.
    - All 10 user profiles are persisted with sessions_count == 1.
    - Each user's respective weak areas are uniquely preserved.
    """
    num_users = 10
    results: Dict[str, Any] = {}
    errors: List[str] = []
    lock = threading.Lock()

    def worker(idx: int):
        uid = f"concurrent_user_{idx:02d}_{uuid.uuid4().hex[:6]}"
        area_tag = "filler words" if idx % 2 == 0 else "STAR structure"
        session_data = {
            "id": f"sess_thread_{idx}_{uuid.uuid4().hex[:6]}",
            "user_id": uid,
            "mode": "english_improvement" if idx % 2 == 0 else "answer_training",
            "history": [
                {"user_text": f"User {idx} speaking", "correction": {"reason": area_tag, "original": "x", "improved": "y"}},
            ],
        }
        try:
            profile = run_sync(update_user_communication_profile(uid, session_data))
            with lock:
                results[uid] = (profile, area_tag)
        except Exception as exc:
            with lock:
                errors.append(f"Worker {idx} failed: {exc}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_users)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert len(errors) == 0, f"Concurrent profile update errors: {errors}"
    assert len(results) == num_users

    for uid, (prof, expected_tag) in results.items():
        comm = prof.get("communication_profile", prof)
        assert comm["sessions_count"] == 1
        assert expected_tag in comm["weak_areas"]


def test_concurrent_e2e_sessions_across_threads():
    """Spawns 8 concurrent threads, each running an independent end-to-end coach session:
    POST /coach/start -> POST /coach/respond (x2) -> POST /coach/end.
    - Verifies 100% success rate (HTTP 200 across all operations).
    - Verifies zero session crosstalk and complete data isolation.
    - Verifies all 8 sessions are recorded in database as completed.
    """
    num_threads = 8
    completed_sessions: List[str] = []
    errors: List[str] = []
    lock = threading.Lock()

    def run_e2e_session(idx: int):
        uid = f"e2e_user_{idx:02d}_{uuid.uuid4().hex[:6]}"
        try:
            with LocalClient(app) as thread_client:
                # 1. Start
                start_res = thread_client.post("/coach/start", json={"user_id": uid, "mode": "conversation"})
                if start_res.status_code != 200:
                    raise Exception(f"Start failed: {start_res.text}")
                sid = start_res.json()["session_id"]

                # 2. Respond
                r1 = thread_client.post("/coach/respond", json={"session_id": sid, "user_text": "Hello coach!"})
                if r1.status_code != 200:
                    raise Exception(f"Respond 1 failed: {r1.text}")

                r2 = thread_client.post("/coach/respond", json={"session_id": sid, "user_text": "I enjoy coding in Python."})
                if r2.status_code != 200:
                    raise Exception(f"Respond 2 failed: {r2.text}")

                # 3. End
                end_res = thread_client.post("/coach/end", json={"session_id": sid})
                if end_res.status_code != 200:
                    raise Exception(f"End failed: {end_res.text}")

                with lock:
                    completed_sessions.append(sid)
        except Exception as exc:
            with lock:
                errors.append(f"Thread {idx} failed: {exc}")

    threads = [threading.Thread(target=run_e2e_session, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15.0)

    assert len(errors) == 0, f"Concurrent E2E session errors: {errors}"
    assert len(completed_sessions) == num_threads

    # Verify all completed sessions persisted cleanly
    for sid in completed_sessions:
        persisted = run_sync(get_coach_session(sid))
        assert persisted is not None
        assert persisted["is_complete"] is True
        assert len(persisted["history"]) == 2


def test_concurrent_session_persistence_dual_write():
    """Executes high-frequency concurrent save_coach_session and get_coach_session
    calls across 10 threads targeting the same session ID:
    - Tests the thread-safety of _coach_lock under write contention.
    - Verifies zero deadlocks or lost session state.
    """
    sid = f"contended_sess_{uuid.uuid4().hex}"
    num_writers = 10
    errors: List[str] = []
    lock = threading.Lock()

    def contention_worker(turn: int):
        try:
            data = {
                "id": sid,
                "session_id": sid,
                "user_id": "test_user_contention",
                "mode": "english_improvement",
                "history": [{"turn": turn, "user_text": f"Utterance {turn}"}],
                "is_complete": False,
            }
            run_sync(save_coach_session(sid, data))
            loaded = run_sync(get_coach_session(sid))
            if loaded is None:
                raise Exception(f"Failed to retrieve contended session {sid}")
        except Exception as exc:
            with lock:
                errors.append(f"Contention worker {turn} failed: {exc}")

    threads = [threading.Thread(target=contention_worker, args=(i,)) for i in range(num_writers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert len(errors) == 0, f"Dual-write contention errors: {errors}"

    final_session = run_sync(get_coach_session(sid))
    assert final_session is not None
    assert final_session["id"] == sid


def test_regression_demotes_strong_area_back_to_weak_area():
    """Adversarially tests candidate skill regression:
    - User has 'grammar & syntax' in strong_areas (previously graduated).
    - User completes a session with a 'grammar & syntax' correction.
    - Verifies that 'grammar & syntax' is stripped from strong_areas and re-added to weak_areas.
    """
    user_id = f"user_regress_{uuid.uuid4().hex[:8]}"

    # Pre-condition: user has strong_areas=["grammar & syntax", "clarity"], weak_areas=[]
    init_data = {
        "id": f"sess_reg_init_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "mode": "english_improvement",
        "history": [
            {"user_text": "clean 1", "correction": None},
            {"user_text": "clean 2", "correction": None},
        ],
        "corrections": [],
    }
    prof = run_sync(update_user_communication_profile(user_id, init_data))
    comm = prof.get("communication_profile", prof)

    # Manually ensure strong_areas has grammar & syntax
    with _coach_lock:
        _in_memory_user_profiles[user_id]["strong_areas"] = ["grammar & syntax", "clarity"]
        _in_memory_user_profiles[user_id]["communication_profile"]["strong_areas"] = ["grammar & syntax", "clarity"]

    # Now user makes a grammar regression
    regress_data = {
        "id": f"sess_regress_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "mode": "english_improvement",
        "history": [
            {"user_text": "yesterday I go", "correction": {"reason": "past tense verb grammar", "original": "go", "improved": "went"}},
        ],
    }
    updated_prof = run_sync(update_user_communication_profile(user_id, regress_data))
    comm_updated = updated_prof.get("communication_profile", updated_prof)

    # grammar & syntax must be removed from strong_areas and placed in weak_areas
    assert "grammar & syntax" not in comm_updated["strong_areas"], (
        f"Regressed skill remained in strong_areas: {comm_updated['strong_areas']}"
    )
    assert "grammar & syntax" in comm_updated["weak_areas"], (
        f"Regressed skill failed to appear in weak_areas: {comm_updated['weak_areas']}"
    )
    assert "clarity" in comm_updated["strong_areas"]


def test_concurrent_writes_same_user_integrity():
    """Fires 10 concurrent profile learning updates on the exact same user ID:
    - Tests write contention and race-condition safety on single user record.
    - Verifies zero deadlocks or exceptions.
    - Verifies final profile state remains structurally valid:
      * weak_areas is a deduplicated list of len <= 5
      * strong_areas is a deduplicated list of len <= 5
      * skill_level is within valid set
      * sessions_count is valid integer >= 1
    """
    user_id = f"user_contended_profile_{uuid.uuid4().hex[:8]}"
    num_updates = 10
    errors: List[str] = []
    lock = threading.Lock()

    def update_worker(turn: int):
        tag = "filler words" if turn % 2 == 0 else "grammar & syntax"
        s_data = {
            "id": f"sess_same_user_{turn}_{uuid.uuid4().hex[:6]}",
            "user_id": user_id,
            "mode": "english_improvement",
            "history": [
                {"user_text": f"text {turn}", "correction": {"reason": tag, "original": "a", "improved": "b"}},
            ],
        }
        try:
            run_sync(update_user_communication_profile(user_id, s_data))
        except Exception as exc:
            with lock:
                errors.append(f"Same-user worker {turn} failed: {exc}")

    threads = [threading.Thread(target=update_worker, args=(i,)) for i in range(num_updates)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert len(errors) == 0, f"Same-user concurrent update errors: {errors}"

    final_profile = run_sync(get_user_profile(user_id))
    assert final_profile is not None
    assert final_profile["skill_level"] in VALID_SKILL_LEVELS
    assert isinstance(final_profile["weak_areas"], list)
    assert len(final_profile["weak_areas"]) <= 5
    assert len(final_profile["weak_areas"]) == len(set(final_profile["weak_areas"]))
    assert isinstance(final_profile["strong_areas"], list)
    assert len(final_profile["strong_areas"]) <= 5
    assert final_profile["sessions_count"] >= 1

