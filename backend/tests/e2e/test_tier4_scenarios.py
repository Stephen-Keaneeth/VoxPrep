"""Tier 4: Real-World Application Scenarios.

Comprehensive multi-turn end-to-end simulations mirroring real candidate interactions:
1. Full Candidate Technical Interview Simulation (Senior Backend Engineer, 5 questions + follow-up, rubric validation, final report).
2. Full Candidate HR Behavioral Interview Simulation (Junior Developer, STAR method behavioral drill, comprehensive report).
3. Multi-Turn Coach Conversational Drill (ESL Candidate, 4 conversation exchanges, supportive corrections, profile progression).
"""

import uuid
import pytest


def test_scenario_full_technical_interview_simulation(client):
    """Scenario 1: Full Technical Interview Simulation.
    
    Candidate: Alex Rivera, applying for Senior Backend Engineer.
    Conducts a complete 5-question technical interview with follow-up probing,
    validates the 4-dimension scoring, concludes the session, and verifies the full analytical report.
    """
    # 1. Start Technical Interview
    start_payload = {
        "candidate_name": "Alex Rivera",
        "role": "Senior Backend Engineer",
        "experience_level": "Senior",
        "interview_type": "technical",
    }
    start_resp = client.post("/interview/start", json=start_payload)
    assert start_resp.status_code == 200, f"Start interview failed: {start_resp.text}"
    start_data = start_resp.json()
    session_id = start_data["session_id"]
    assert "opening_message" in start_data
    assert len(start_data["opening_message"]) > 0

    # 2. Simulate 5 realistic technical answers + follow-ups
    interview_dialogue = [
        # Q1: Warm-up / Stack
        "I have spent 7 years building high-concurrency backend services using Python, FastAPI, and Go. "
        "My core architecture patterns involve event-driven microservices with Apache Kafka and PostgreSQL.",

        # Follow-up on Q1
        "To manage database connection pooling under high load, we deployed PgBouncer in transaction pooling mode "
        "and scaled read replicas with asynchronous streaming replication.",

        # Q2: System Design / Caching
        "When designing a distributed caching layer, we employ Redis clusters with write-through caching. "
        "To prevent cache stampede during high-traffic spikes, we use probabilistic early expiration and distributed mutex locks.",

        # Q3: Concurrency / Transactions
        "For financial ledger processing, we strictly enforce PostgreSQL SERIALIZABLE isolation levels, "
        "relying on retry loops with exponential jitter to handle serialization failures gracefully without data loss.",

        # Q4: Reliability / Fault Tolerance
        "We implement the Circuit Breaker pattern using Resilience4j principles and configure dead-letter queues (DLQ) "
        "for any message that fails three consumption attempts.",

        # Q5: Troubleshooting / Observability
        "To isolate a memory leak in a Python container, I use tracemalloc and py-spy to capture memory allocations and flame graphs, "
        "correlating with Prometheus container RSS metrics.",
    ]

    is_complete = False
    turns_executed = 0

    for idx, answer in enumerate(interview_dialogue):
        if is_complete:
            break
        resp = client.post("/interview/respond", json={
            "session_id": session_id,
            "answer_text": answer,
        })
        assert resp.status_code == 200, f"Turn {idx + 1} failed: {resp.text}"
        data = resp.json()
        turns_executed += 1
        assert "spoken_response" in data
        assert len(data["spoken_response"]) > 0
        is_complete = data.get("is_complete", False)

    # 3. End session and generate comprehensive evaluation report
    end_resp = client.post("/interview/end", json={"session_id": session_id})
    assert end_resp.status_code == 200, f"End interview failed: {end_resp.text}"

    # 4. Validate complete report
    report_resp = client.get(f"/interview/report/{session_id}")
    assert report_resp.status_code == 200, f"Report retrieval failed: {report_resp.text}"
    report = report_resp.json()

    # Verify report completeness per docs/08_AGENT_PROMPTS.md
    assert "overall_score" in report
    overall = float(report["overall_score"])
    assert 1.0 <= overall <= 10.0, f"Overall score out of range: {overall}"

    dim_scores = report["dimension_scores"]
    for dim in ["relevance", "clarity", "depth", "examples"]:
        assert dim in dim_scores, f"Missing dimension {dim}"
        score = float(dim_scores[dim])
        assert 1.0 <= score <= 10.0, f"Dimension {dim} score {score} out of bounds"

    assert len(report.get("strengths", [])) >= 1, "Expected at least 1 strength noted"
    assert len(report.get("weaknesses", [])) >= 1, "Expected at least 1 constructive weakness noted"
    assert len(report.get("improvement_tips", [])) >= 1, "Expected actionable improvement tips"
    assert "coach_recommendation" in report
    assert "summary" in report


def test_scenario_full_hr_behavioral_interview_simulation(client):
    """Scenario 2: Full HR Behavioral Interview Simulation.
    
    Candidate: Sarah Chen, applying for Junior Software Developer.
    Conducts an HR behavioral interview focusing on collaboration, conflict resolution,
    and STAR method responses.
    """
    # 1. Start HR Interview
    start_payload = {
        "candidate_name": "Sarah Chen",
        "role": "Junior Software Developer",
        "experience_level": "Junior",
        "interview_type": "hr",
    }
    start_resp = client.post("/interview/start", json=start_payload)
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]

    # 2. Behavioral questions & STAR answers
    hr_answers = [
        # Opening / Background
        "I recently graduated with a degree in Computer Science and completed a 6-month internship where I contributed to frontend bug fixes.",
        # Behavioral: Conflict / Collaboration
        "In our capstone project, two team members disagreed on whether to use SQL or MongoDB. Situation: deadline was approaching. "
        "Task: resolve the disagreement. Action: I benchmarked query requirements and presented data to the team. Result: we agreed on SQL.",
        # Follow-up
        "Through that experience, I learned that objective data and proactive listening prevent team friction.",
        # Overcoming Failure
        "During my internship, I accidentally pushed code that broke a staging build. I immediately notified the team, reverted the commit, "
        "and added automated pre-commit tests to ensure it would not happen again.",
        # 3-year vision
        "In three years, I hope to grow into a Mid-level full stack engineer who mentors incoming interns and owns core features.",
    ]

    for ans in hr_answers:
        resp = client.post("/interview/respond", json={
            "session_id": session_id,
            "answer_text": ans,
        })
        assert resp.status_code == 200
        assert "spoken_response" in resp.json()
        if resp.json().get("is_complete"):
            break

    # 3. End HR Interview
    end_resp = client.post("/interview/end", json={"session_id": session_id})
    assert end_resp.status_code == 200

    # 4. Validate Report
    report_resp = client.get(f"/interview/report/{session_id}")
    assert report_resp.status_code == 200
    report = report_resp.json()
    assert report["overall_score"] > 0
    assert "strengths" in report
    assert "improvement_tips" in report


def test_scenario_multi_turn_coach_conversational_progression(client):
    """Scenario 3: Multi-Turn Communication Coach Drill.
    
    User: Practicing natural conversational English.
    Simulates a 4-turn drill, validates supportive feedback and gentle grammar corrections,
    ends the session, and verifies profile update with learning progression.
    """
    user_id = str(uuid.uuid4())

    # 1. Start Coach Session
    start_resp = client.post("/coach/start", json={
        "user_id": user_id,
        "mode": "conversation",
    })
    assert start_resp.status_code == 200
    coach_sid = start_resp.json()["session_id"]
    assert "opening_message" in start_resp.json()

    # 2. Turn 1: Utterance with common ESL mistake
    turn1_resp = client.post("/coach/respond", json={
        "session_id": coach_sid,
        "user_text": "On Sunday I was go to park with friends and we played tennis.",
    })
    assert turn1_resp.status_code == 200
    turn1_data = turn1_resp.json()
    assert "coach_message" in turn1_data
    assert "next_prompt" in turn1_data

    # 3. Turn 2: User adopts correction
    turn2_resp = client.post("/coach/respond", json={
        "session_id": coach_sid,
        "user_text": "Yes, I went to the park and the weather was very sunny.",
    })
    assert turn2_resp.status_code == 200
    turn2_data = turn2_resp.json()
    assert "coach_message" in turn2_data

    # 4. Turn 3: Continuing conversation
    turn3_resp = client.post("/coach/respond", json={
        "session_id": coach_sid,
        "user_text": "After playing tennis, we had lunch at an Italian restaurant.",
    })
    assert turn3_resp.status_code == 200

    # 5. Turn 4: Final wrap-up utterance
    turn4_resp = client.post("/coach/respond", json={
        "session_id": coach_sid,
        "user_text": "I really enjoyed spending time outdoors and relaxing.",
    })
    assert turn4_resp.status_code == 200

    # 6. End Coach Session
    end_resp = client.post("/coach/end", json={"session_id": coach_sid})
    assert end_resp.status_code == 200
    end_data = end_resp.json()

    # 7. Verify session summary and profile progression
    assert "summary" in end_data
    summary = end_data["summary"]
    assert summary.get("exchanges_count") == 4, f"Expected 4 exchanges, got: {summary.get('exchanges_count')}"
    assert "key_learnings" in summary
    assert "encouragement" in summary

    assert "updated_profile" in end_data
    profile = end_data["updated_profile"]
    assert profile.get("sessions_count", 0) >= 1
    assert "weak_areas" in profile
    assert "strong_areas" in profile
