"""VOXPREP Backend - Adversarial Report Stress & State Validation Tests
Milestone 2: Phase 2 AI Interviewer Agent and Session Management.

Adversarial test suite challenging:
1. Malformed and Adversarial LLM JSON Parser Stress:
   - Truncated JSON outputs, markdown code fence variations (```json, ```, raw braces),
     single-line comments inside JSON, trailing commas, non-dict outputs.
   - Verification that `generate_report` NEVER raises an unhandled exception and
     always returns a valid report dictionary matching the VOXPREP report schema.
2. Score Scaling and Normalization Boundaries:
   - LLM responses returning 0, negative scores, 100-point percentages (e.g. 85),
     and string numbers ("8.5", "10.0") verifying strict normalization to [1.0, 10.0].
   - Verification of backward compatibility aliasing:
     `weaknesses` mirrors `areas_for_improvement`, and `improvement_tips` mirrors `action_items`.
3. Router Report State Validation:
   - GET /interview/report/{session_id} on non-existent session_id -> HTTP 404.
   - GET /interview/report/{session_id} on active (in_progress) session -> HTTP 400 with helpful message.
   - POST /interview/end on already ended session -> idempotent HTTP 200 without data corruption.
"""

import json
import uuid
from typing import Any, Dict, List
import pytest

from app.main import app
from app.routers.interview import session_manager
from app.services import llm, report
from app.services.report import (
    generate_fallback_report,
    generate_report,
    normalize_and_validate_report,
    parse_llm_report_json,
    _clean_json_quirks,
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


SAMPLE_SESSION_DATA = {
    "session_id": "test-session-adversarial-001",
    "candidate_name": "Jordan Adversary",
    "role": "Distributed Systems Engineer",
    "role_applied": "Distributed Systems Engineer",
    "experience_level": "Senior",
    "interview_type": "technical",
    "question_history": [
        {
            "question": "How do you handle distributed consensus under network partitions?",
            "answer": "We use Raft consensus with etcd, establishing leader lease timeouts and quorum-based writes to prevent split-brain scenarios.",
            "scores": {"relevance": 8.5, "clarity": 8.0, "depth": 8.5, "examples": 8.0},
        },
        {
            "question": "How do you manage eventual consistency in read-heavy architectures?",
            "answer": "We deploy asynchronous replication with read-through Redis caching and CQRS patterns, accepting momentary replication lag bounded by SLAs.",
            "scores": {"relevance": 9.0, "clarity": 8.5, "depth": 8.0, "examples": 8.0},
        },
    ],
}


def assert_valid_report_schema(result: Dict[str, Any]):
    """Validates that a generated report conforms strictly to the VOXPREP schema."""
    assert isinstance(result, dict), f"Report must be a dict, got {type(result)}"

    # 1. Overall Score
    assert "overall_score" in result, "Missing 'overall_score'"
    overall = float(result["overall_score"])
    assert 1.0 <= overall <= 10.0, f"'overall_score' {overall} not in range [1.0, 10.0]"

    # 2. Dimension Scores
    assert "dimension_scores" in result, "Missing 'dimension_scores'"
    dims = result["dimension_scores"]
    assert isinstance(dims, dict), f"'dimension_scores' must be dict, got {type(dims)}"
    for dim_name in ["relevance", "clarity", "depth", "examples"]:
        assert dim_name in dims, f"Missing dimension '{dim_name}' in dimension_scores"
        dim_score = float(dims[dim_name])
        assert 1.0 <= dim_score <= 10.0, f"Dimension '{dim_name}' score {dim_score} not in range [1.0, 10.0]"

    # 3. Strengths
    assert "strengths" in result, "Missing 'strengths'"
    assert isinstance(result["strengths"], list), "'strengths' must be a list"
    assert len(result["strengths"]) >= 1, "'strengths' must contain at least 1 item"

    # 4. Areas for Improvement and Backward Compatibility Weaknesses
    assert "areas_for_improvement" in result, "Missing 'areas_for_improvement'"
    assert isinstance(result["areas_for_improvement"], list), "'areas_for_improvement' must be a list"
    assert len(result["areas_for_improvement"]) >= 1, "'areas_for_improvement' must contain at least 1 item"

    assert "weaknesses" in result, "Missing backward-compatibility 'weaknesses'"
    assert result["weaknesses"] == result["areas_for_improvement"], "'weaknesses' does not mirror 'areas_for_improvement'"

    # 5. Action Items and Backward Compatibility Improvement Tips
    assert "action_items" in result, "Missing 'action_items'"
    assert isinstance(result["action_items"], list), "'action_items' must be a list"
    assert len(result["action_items"]) >= 1, "'action_items' must contain at least 1 item"

    assert "improvement_tips" in result, "Missing backward-compatibility 'improvement_tips'"
    assert result["improvement_tips"] == result["action_items"], "'improvement_tips' does not mirror 'action_items'"

    # 6. Recommendation & Summary
    assert "coach_recommendation" in result, "Missing 'coach_recommendation'"
    assert isinstance(result["coach_recommendation"], str) and len(result["coach_recommendation"]) > 0

    assert "summary" in result, "Missing 'summary'"
    assert isinstance(result["summary"], str) and len(result["summary"]) > 0

    # 7. Question Breakdown
    assert "question_breakdown" in result, "Missing 'question_breakdown'"
    assert isinstance(result["question_breakdown"], list), "'question_breakdown' must be a list"


# =============================================================================
# PART 1: Malformed and Adversarial LLM JSON Parser Stress Tests
# =============================================================================

@pytest.mark.parametrize(
    "truncated_raw",
    [
        '{"overall_score": 8.5, "strengths": [',
        '{"overall_score": 8.5',
        '{"dimension_scores": {"relevance": 8.0, "clar',
        '```json\n{"overall_score": 7.5, "summary": "Candida',
        '{"strengths": ["Clear communication"',
        '{"overall_score":',
        '{',
        '{"',
    ],
)
def test_adversarial_parser_truncated_json(monkeypatch, truncated_raw):
    """Verifies that truncated LLM outputs never crash parse_llm_report_json or generate_report."""
    # 1. Directly challenge parse_llm_report_json
    parsed = parse_llm_report_json(truncated_raw)
    assert parsed is None, f"Expected None for truncated input '{truncated_raw}', got {parsed}"

    # 2. Challenge generate_report with forced non-mock mode
    async def mock_truncated_chat(messages, system_prompt):
        return truncated_raw

    monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
    monkeypatch.setattr(llm, "chat", mock_truncated_chat)

    # Must never raise an unhandled exception and must return a valid report
    result = run_sync(generate_report(SAMPLE_SESSION_DATA))
    assert_valid_report_schema(result)


@pytest.mark.parametrize(
    "fence_input,expected_overall",
    [
        # Standard markdown fence
        ('```json\n{"overall_score": 8.2, "summary": "Solid"}\n```', 8.2),
        # Code fence without language identifier
        ('```\n{"overall_score": 7.9, "summary": "Good fundamentals"}\n```', 7.9),
        # Uppercase JSON identifier
        ('```JSON\n{"overall_score": 9.1, "summary": "Exceptional"}\n```', 9.1),
        # Fence surrounded by verbose assistant text
        (
            'Here is the candidate performance evaluation report:\n\n'
            '```json\n{"overall_score": 8.7, "strengths": ["Excellent distributed systems depth"]}\n```\n\n'
            'Let me know if you would like any follow-up analysis.',
            8.7,
        ),
        # Extra whitespace and newlines inside fence
        ('```json\n\n\n   {"overall_score": 7.3}   \n\n```', 7.3),
    ],
)
def test_adversarial_parser_code_fence_variations(monkeypatch, fence_input, expected_overall):
    """Verifies that markdown code fence variations are robustly extracted and parsed."""
    parsed = parse_llm_report_json(fence_input)
    assert parsed is not None, f"Failed to parse fence input: {fence_input}"
    assert parsed["overall_score"] == expected_overall

    async def mock_fence_chat(messages, system_prompt):
        return fence_input

    monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
    monkeypatch.setattr(llm, "chat", mock_fence_chat)

    result = run_sync(generate_report(SAMPLE_SESSION_DATA))
    assert_valid_report_schema(result)
    assert result["overall_score"] == expected_overall


def test_adversarial_parser_raw_braces_without_fences(monkeypatch):
    """Verifies that raw JSON embedded in freeform conversational text is extracted and parsed."""
    raw_embedded = (
        "Thank you for submitting the session data. After careful evaluation, here is the assessment: "
        '{"overall_score": 8.4, "coach_recommendation": "Interview Answer Training", "summary": "Great clarity"} '
        "This concludes the performance evaluation."
    )
    parsed = parse_llm_report_json(raw_embedded)
    assert parsed is not None
    assert parsed["overall_score"] == 8.4

    async def mock_embedded_chat(messages, system_prompt):
        return raw_embedded

    monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
    monkeypatch.setattr(llm, "chat", mock_embedded_chat)

    result = run_sync(generate_report(SAMPLE_SESSION_DATA))
    assert_valid_report_schema(result)
    assert result["overall_score"] == 8.4


def test_adversarial_parser_single_line_comments(monkeypatch):
    """Verifies that single-line JavaScript-style comments inside JSON are stripped and parsed."""
    commented_json = """
    {
        // Overall candidate score
        "overall_score": 8.6,
        "dimension_scores": {
            "relevance": 9.0, // High relevance to role
            "clarity": 8.5,   // Clear presentation
            "depth": 8.0,
            "examples": 8.5
        },
        // Identified strengths
        "strengths": [
            "Strong command of distributed systems", // Point 1
            "Effective explanation of consensus protocols"
        ],
        "summary": "Candidate displayed strong problem solving." // End summary
    }
    """
    parsed = parse_llm_report_json(commented_json)
    assert parsed is not None
    assert parsed["overall_score"] == 8.6
    assert parsed["dimension_scores"]["relevance"] == 9.0

    async def mock_comment_chat(messages, system_prompt):
        return f"```json\n{commented_json}\n```"

    monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
    monkeypatch.setattr(llm, "chat", mock_comment_chat)

    result = run_sync(generate_report(SAMPLE_SESSION_DATA))
    assert_valid_report_schema(result)
    assert result["overall_score"] == 8.6


def test_adversarial_parser_trailing_commas(monkeypatch):
    """Verifies that trailing commas in objects and arrays are gracefully sanitized."""
    trailing_comma_json = """
    {
        "overall_score": 8.1,
        "dimension_scores": {
            "relevance": 8.0,
            "clarity": 8.0,
            "depth": 8.0,
            "examples": 8.0,
        },
        "strengths": [
            "Good concurrency knowledge",
            "Structured responses",
        ],
        "summary": "Solid technical capability.",
    }
    """
    parsed = parse_llm_report_json(trailing_comma_json)
    assert parsed is not None
    assert parsed["overall_score"] == 8.1

    async def mock_trailing_chat(messages, system_prompt):
        return trailing_comma_json

    monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
    monkeypatch.setattr(llm, "chat", mock_trailing_chat)

    result = run_sync(generate_report(SAMPLE_SESSION_DATA))
    assert_valid_report_schema(result)
    assert result["overall_score"] == 8.1


@pytest.mark.parametrize(
    "non_dict_raw",
    [
        "[1, 2, 3]",
        '["item1", "item2", "item3"]',
        '"Just a standalone JSON string without an object"',
        "42",
        "3.14159",
        "true",
        "false",
        "null",
        "",
        "   \n  \t  ",
        "This is completely unformatted raw English without any JSON braces whatsoever.",
        "<html><body><h1>502 Bad Gateway</h1><p>NVIDIA NIM Gateway Timeout</p></body></html>",
        "{invalid: json without quotes or proper structure}}",
    ],
)
def test_adversarial_parser_non_dict_and_garbage_outputs(monkeypatch, non_dict_raw):
    """Verifies that non-dict or garbage LLM outputs return None in parser and trigger safe fallback in generate_report."""
    parsed = parse_llm_report_json(non_dict_raw)
    assert parsed is None, f"Expected None for non-dict input '{non_dict_raw}', got {parsed}"

    async def mock_garbage_chat(messages, system_prompt):
        return non_dict_raw

    monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
    monkeypatch.setattr(llm, "chat", mock_garbage_chat)

    # Must never raise an unhandled exception and must return a valid report
    result = run_sync(generate_report(SAMPLE_SESSION_DATA))
    assert_valid_report_schema(result)


def test_adversarial_parser_list_wrapping_dict_handled(monkeypatch):
    """Verifies that an LLM returning a JSON array wrapping a dict is safely handled without exceptions."""
    list_wrapped = '[{"overall_score": 8.0, "strengths": ["Strong domain knowledge"]}]'
    
    async def mock_list_chat(messages, system_prompt):
        return list_wrapped

    monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
    monkeypatch.setattr(llm, "chat", mock_list_chat)

    result = run_sync(generate_report(SAMPLE_SESSION_DATA))
    assert_valid_report_schema(result)
    assert result["overall_score"] == 8.0


def test_adversarial_generate_report_never_raises_on_llm_exception(monkeypatch):
    """Verifies that even if the LLM client raises network or runtime exceptions, generate_report succeeds."""
    async def mock_crashing_chat(messages, system_prompt):
        raise ConnectionResetError("NVIDIA NIM connection dropped unexpectedly.")

    monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
    monkeypatch.setattr(llm, "chat", mock_crashing_chat)

    result = run_sync(generate_report(SAMPLE_SESSION_DATA))
    assert_valid_report_schema(result)


# =============================================================================
# PART 2: Score Scaling and Normalization Boundaries
# =============================================================================

def test_score_normalization_zero_and_negative():
    """Verifies that 0 and negative scores are strictly clamped to minimum 1.0."""
    raw = {
        "overall_score": 0,
        "dimension_scores": {
            "relevance": 0,
            "clarity": -5.0,
            "depth": -0.1,
            "examples": -100.0,
        },
    }
    result = normalize_and_validate_report(raw, SAMPLE_SESSION_DATA)
    assert_valid_report_schema(result)

    assert result["overall_score"] == 1.0, f"Expected 1.0 for 0 overall_score, got {result['overall_score']}"
    for dim, score in result["dimension_scores"].items():
        assert score == 1.0, f"Expected 1.0 for zero/negative dimension '{dim}', got {score}"


@pytest.mark.parametrize(
    "percentage_score,expected_normalized",
    [
        (85, 8.5),
        (85.0, 8.5),
        (100, 10.0),
        (100.0, 10.0),
        (72.0, 7.2),
        (95.5, 9.6),
        (50.0, 5.0),
    ],
)
def test_score_normalization_100_point_percentages(monkeypatch, percentage_score, expected_normalized):
    """Verifies that 100-point percentage scores (> 10.0) are normalized to the [1.0, 10.0] scale."""
    raw = {
        "overall_score": percentage_score,
        "dimension_scores": {
            "relevance": 8.0,
            "clarity": 8.0,
            "depth": 8.0,
            "examples": 8.0,
        },
    }
    result = normalize_and_validate_report(raw, SAMPLE_SESSION_DATA)
    assert_valid_report_schema(result)
    assert result["overall_score"] == expected_normalized

    # Also test via generate_report with LLM JSON response
    async def mock_percentage_chat(messages, system_prompt):
        return json.dumps(raw)

    monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
    monkeypatch.setattr(llm, "chat", mock_percentage_chat)

    rep = run_sync(generate_report(SAMPLE_SESSION_DATA))
    assert_valid_report_schema(rep)
    assert rep["overall_score"] == expected_normalized


@pytest.mark.parametrize(
    "string_score,expected_float",
    [
        ("8.5", 8.5),
        ("9", 9.0),
        ("10.0", 10.0),
        ("1.0", 1.0),
        ("85", 8.5),  # Percentage as string
        ("100", 10.0),
        ("0", 1.0),   # Zero as string -> clamp to 1.0
        ("-3.5", 1.0), # Negative as string -> clamp to 1.0
    ],
)
def test_score_normalization_string_numbers(monkeypatch, string_score, expected_float):
    """Verifies that numbers encoded as strings in LLM JSON are coerced and normalized cleanly."""
    raw = {
        "overall_score": string_score,
        "dimension_scores": {
            "relevance": "8.5",
            "clarity": "9.0",
            "depth": "7.5",
            "examples": "8.0",
        },
    }
    result = normalize_and_validate_report(raw, SAMPLE_SESSION_DATA)
    assert_valid_report_schema(result)
    assert result["overall_score"] == expected_float
    assert result["dimension_scores"]["relevance"] == 8.5
    assert result["dimension_scores"]["clarity"] == 9.0

    async def mock_string_chat(messages, system_prompt):
        return json.dumps(raw)

    monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
    monkeypatch.setattr(llm, "chat", mock_string_chat)

    rep = run_sync(generate_report(SAMPLE_SESSION_DATA))
    assert_valid_report_schema(rep)
    assert rep["overall_score"] == expected_float


def test_score_normalization_extreme_excessive_values():
    """Verifies that excessively high numbers (e.g. 500, 10000) are clamped to 10.0 maximum."""
    raw = {
        "overall_score": 500.0,
        "dimension_scores": {
            "relevance": 200.0,
            "clarity": 1000.0,
            "depth": 50.0,
            "examples": 99.0,
        },
    }
    result = normalize_and_validate_report(raw, SAMPLE_SESSION_DATA)
    assert_valid_report_schema(result)
    assert result["overall_score"] == 10.0
    for dim, score in result["dimension_scores"].items():
        assert score == 10.0


def test_score_normalization_invalid_or_missing_types():
    """Verifies that non-numeric, null, or completely missing score values fallback gracefully to valid floats."""
    raw_none = {
        "overall_score": None,
        "dimension_scores": "not a dict",
    }
    res_none = normalize_and_validate_report(raw_none, SAMPLE_SESSION_DATA)
    assert_valid_report_schema(res_none)
    assert 1.0 <= res_none["overall_score"] <= 10.0

    raw_invalid_str = {
        "overall_score": "not-a-number",
        "dimension_scores": {},
    }
    res_invalid = normalize_and_validate_report(raw_invalid_str, SAMPLE_SESSION_DATA)
    assert_valid_report_schema(res_invalid)
    assert 1.0 <= res_invalid["overall_score"] <= 10.0


def test_backward_compatibility_aliasing_bidirectional():
    """Verifies that weaknesses <-> areas_for_improvement and improvement_tips <-> action_items mirror bidirectionally."""
    # Case A: LLM supplies modern fields
    raw_modern = {
        "overall_score": 8.0,
        "areas_for_improvement": ["Elaborate on disaster recovery protocols."],
        "action_items": ["Practice framing architecture trade-offs under latency constraints."],
    }
    res_modern = normalize_and_validate_report(raw_modern, SAMPLE_SESSION_DATA)
    assert res_modern["areas_for_improvement"] == ["Elaborate on disaster recovery protocols."]
    assert res_modern["weaknesses"] == ["Elaborate on disaster recovery protocols."]
    assert res_modern["action_items"] == ["Practice framing architecture trade-offs under latency constraints."]
    assert res_modern["improvement_tips"] == ["Practice framing architecture trade-offs under latency constraints."]

    # Case B: LLM supplies legacy fields
    raw_legacy = {
        "overall_score": 8.0,
        "weaknesses": ["Quantify distributed database throughput benchmarks."],
        "improvement_tips": ["Adopt STAR method for situational behavioral responses."],
    }
    res_legacy = normalize_and_validate_report(raw_legacy, SAMPLE_SESSION_DATA)
    assert res_legacy["weaknesses"] == ["Quantify distributed database throughput benchmarks."]
    assert res_legacy["areas_for_improvement"] == ["Quantify distributed database throughput benchmarks."]
    assert res_legacy["improvement_tips"] == ["Adopt STAR method for situational behavioral responses."]
    assert res_legacy["action_items"] == ["Adopt STAR method for situational behavioral responses."]

    # Case C: Fallback report maintains perfect mirror
    fallback = generate_fallback_report(SAMPLE_SESSION_DATA)
    assert fallback["weaknesses"] == fallback["areas_for_improvement"]
    assert fallback["improvement_tips"] == fallback["action_items"]


# =============================================================================
# PART 3: Router Report State Validation
# =============================================================================

def test_router_get_report_nonexistent_session_returns_404(test_client):
    """Calling GET /interview/report/{session_id} on a non-existent session_id must return HTTP 404."""
    random_uuid = str(uuid.uuid4())
    resp = test_client.get(f"/interview/report/{random_uuid}")
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()

    # Also test arbitrary non-UUID string
    resp_bad_id = test_client.get("/interview/report/non-existent-session-id-12345")
    assert resp_bad_id.status_code == 404


def test_router_get_report_active_session_returns_400(test_client):
    """Calling GET /interview/report/{session_id} on an active, uncompleted session must return HTTP 400 with helpful error."""
    # Start session
    start_resp = test_client.post("/interview/start", json={
        "candidate_name": "Active Session Tester",
        "role": "Site Reliability Engineer",
        "experience_level": "Senior",
        "interview_type": "technical",
    })
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]

    # Immediately try to fetch report while session is freshly created
    report_resp_immediate = test_client.get(f"/interview/report/{session_id}")
    assert report_resp_immediate.status_code == 400, f"Expected 400 for fresh active session, got {report_resp_immediate.status_code}"
    detail_immediate = report_resp_immediate.json()["detail"].lower()
    assert "not yet completed" in detail_immediate or "complete the interview" in detail_immediate

    # Submit an answer (session is in-progress)
    ans_resp = test_client.post("/interview/respond", json={
        "session_id": session_id,
        "answer_text": "I set up Prometheus metrics, Grafana alerts, and automated runbooks for incident management.",
    })
    assert ans_resp.status_code == 200

    # Try to fetch report again mid-interview
    report_resp_mid = test_client.get(f"/interview/report/{session_id}")
    assert report_resp_mid.status_code == 400, f"Expected 400 for in-progress session, got {report_resp_mid.status_code}"
    detail_mid = report_resp_mid.json()["detail"].lower()
    assert "not yet completed" in detail_mid or "complete the interview" in detail_mid


def test_router_end_session_idempotence(test_client):
    """Ending an already ended session multiple times must be strictly idempotent without data corruption."""
    # 1. Initialize and conduct a turn
    start_resp = test_client.post("/interview/start", json={
        "candidate_name": "Idempotent Tester",
        "role": "Cloud Security Architect",
        "experience_level": "Principal",
        "interview_type": "technical",
    })
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]

    ans_resp = test_client.post("/interview/respond", json={
        "session_id": session_id,
        "answer_text": "I implement zero-trust network access, SPIFFE/SPIRE workload identities, and KMS envelope encryption.",
    })
    assert ans_resp.status_code == 200

    # 2. End session the first time
    end_resp_1 = test_client.post("/interview/end", json={"session_id": session_id})
    assert end_resp_1.status_code == 200, f"First end failed: {end_resp_1.text}"
    data_1 = end_resp_1.json()
    assert data_1["status"] == "completed"
    assert "report" in data_1
    report_1 = data_1["report"]
    assert_valid_report_schema(report_1)

    # 3. End session a second time (idempotent call)
    end_resp_2 = test_client.post("/interview/end", json={"session_id": session_id})
    assert end_resp_2.status_code == 200, f"Second end failed: {end_resp_2.text}"
    data_2 = end_resp_2.json()
    assert data_2["status"] == "completed"
    assert "report" in data_2
    report_2 = data_2["report"]

    # Assert exact report stability (no corruption or score mutation across calls)
    assert report_2["overall_score"] == report_1["overall_score"]
    assert report_2["dimension_scores"] == report_1["dimension_scores"]
    assert report_2["strengths"] == report_1["strengths"]
    assert report_2["areas_for_improvement"] == report_1["areas_for_improvement"]

    # 4. End session a third time
    end_resp_3 = test_client.post("/interview/end", json={"session_id": session_id})
    assert end_resp_3.status_code == 200
    data_3 = end_resp_3.json()
    assert data_3["status"] == "completed"
    assert data_3["report"]["overall_score"] == report_1["overall_score"]

    # 5. Fetch report via GET /interview/report/{session_id} and confirm consistency
    get_report_resp = test_client.get(f"/interview/report/{session_id}")
    assert get_report_resp.status_code == 200
    fetched_report = get_report_resp.json()
    assert_valid_report_schema(fetched_report)
    assert fetched_report["overall_score"] == report_1["overall_score"]
    assert fetched_report["dimension_scores"] == report_1["dimension_scores"]
    assert fetched_report["strengths"] == report_1["strengths"]


def test_router_end_nonexistent_session_returns_404(test_client):
    """Calling POST /interview/end on a non-existent session_id must return HTTP 404."""
    random_uuid = str(uuid.uuid4())
    resp = test_client.post("/interview/end", json={"session_id": random_uuid})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_router_respond_after_session_ended_is_safe(test_client):
    """Submitting an answer after session is completed returns is_complete=True gracefully without data corruption."""
    start_resp = test_client.post("/interview/start", json={
        "candidate_name": "Post-Completion Candidate",
        "role": "Backend Engineer",
        "experience_level": "Senior",
        "interview_type": "technical",
    })
    session_id = start_resp.json()["session_id"]

    # End session
    end_resp = test_client.post("/interview/end", json={"session_id": session_id})
    assert end_resp.status_code == 200
    orig_report = end_resp.json()["report"]

    # Submit an answer to the completed session
    respond_resp = test_client.post("/interview/respond", json={
        "session_id": session_id,
        "answer_text": "An extra answer submitted after interview was marked complete.",
    })
    assert respond_resp.status_code == 200
    assert respond_resp.json()["is_complete"] is True

    # Report retrieved after must still be intact and valid
    report_resp = test_client.get(f"/interview/report/{session_id}")
    assert report_resp.status_code == 200
    current_report = report_resp.json()
    assert current_report["overall_score"] == orig_report["overall_score"]
