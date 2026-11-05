# Architectural Analysis & Blueprint: Interviewer Agent & Rubric Scoring (`agents/interviewer.py`)

**Milestone**: Milestone 2 (Phase 2: AI Interviewer Agent and Session Management)  
**Author**: explorer_m2_1 (Interviewer Agent & Rubric Scoring Architect)  
**Target Module**: `backend/app/agents/interviewer.py`  
**Dependencies**: `backend/app/services/llm.py`, `backend/app/db/supabase.py`, `backend/schema.sql`, `docs/08_AGENT_PROMPTS.md`, `docs/07_GUARDRAILS.md`

---

## 1. Executive Summary & Design Goals

The VOXPREP platform enables job candidates to conduct voice-driven mock interviews evaluated by an AI Interviewer Agent (Agent 1). The core engine for this milestone is `backend/app/agents/interviewer.py`, centered on the `InterviewSession` class.

### Key Architectural Responsibilities:
1. **Persona & Prompt Management**: Provide distinct, authoritative system prompts for **HR** and **Technical** interviews adhering verbatim to `docs/08_AGENT_PROMPTS.md`.
2. **Session State Machine**: Track question progression, follow-up count, current question, and completion status.
3. **Hard Guardrail Enforcement**:
   - **Maximum 5 questions** per interview session.
   - **Maximum 1 follow-up** per core question.
   - Strictly avoid repeating questions or revealing answers beforehand.
4. **4-Dimension Rubric Scoring Engine**:
   - Evaluate every candidate response across **Relevance**, **Clarity**, **Depth**, and **Examples** on a strict **1.0 to 10.0** scale.
   - Aggregate cumulative running dimension scores and overall session average.
5. **Conversational Decision Logic**:
   - Decide dynamically whether to probe deeper with a relevant follow-up or transition to the next question.
   - Prohibit consecutive follow-ups (if a follow-up was just answered, immediately advance).
6. **Robust Offline Mock Fallback**:
   - When NVIDIA NIM credentials are absent or `MOCK_AI_SERVICES=true`, execute high-fidelity mock question sequences and rubric scoring based on semantic heuristics.
   - Guarantee 100% test compatibility across single turns, 5-question multi-turn simulations, and adversarial edge cases.
7. **Stateless Persistence Compatibility**:
   - Provide complete serialization (`to_dict`) and reconstruction (`from_dict`) routines compatible with the Supabase `interview_sessions` table and `MockTableQuery`.

---

## 2. Session State Model & Boundaries

### 2.1 State Attributes

| Attribute | Type | Description |
|---|---|---|
| `session_id` | `str` (UUID) | Unique interview session identifier |
| `candidate_name` | `str` | Name of the candidate (e.g. "Alex Rivera") |
| `role` | `str` | Applied role (mapped to `role_applied` in Supabase) |
| `experience_level` | `str` | Candidate experience level ("Junior", "Mid-level", "Senior") |
| `interview_type` | `str` | Interview track: `"hr"` or `"technical"` |
| `user_id` | `Optional[str]` | Optional user UUID linked to `users.id` in Supabase |
| `current_question_index` | `int` | Current core question index (`0` to `4`, total `5`) |
| `follow_up_count` | `int` | Number of follow-ups used for the current question (`0` or `1`) |
| `is_complete` | `bool` | Whether all 5 questions have been completed or ended |
| `current_question` | `str` | The active question text awaiting candidate answer |
| `dimension_scores` | `Dict[str, float]` | Cumulative score averages (`relevance`, `clarity`, `depth`, `examples`, `overall`) |
| `question_history` | `List[Dict[str, Any]]` | List of exchanges: `question`, `answer`, `scores`, `follow_up_used`, `timestamp` |
| `created_at` | `str` | ISO 8601 UTC creation timestamp |
| `completed_at` | `Optional[str]` | ISO 8601 UTC completion timestamp |

### 2.2 Guardrail Constants
```python
MAX_QUESTIONS: int = 5
MAX_FOLLOW_UPS_PER_QUESTION: int = 1
VALID_INTERVIEW_TYPES = {"hr", "technical"}
DIMENSIONS = ["relevance", "clarity", "depth", "examples"]
```

---

## 3. System Prompts & Persona Architecture

Per `docs/08_AGENT_PROMPTS.md`, system prompts are strictly separated:

### 3.1 HR Interview Prompt
```python
HR_SYSTEM_PROMPT_TEMPLATE = """You are VOXPREP's professional AI interviewer conducting a structured HR interview.

CANDIDATE INFORMATION:
- Name: {candidate_name}
- Role Applied For: {role}
- Experience Level: {experience_level}

YOUR ROLE:
You are a professional HR interviewer. Your sole job during this session is to conduct a realistic, structured interview. You are NOT a tutor or coach during this session.

INTERVIEW RULES (STRICT):
1. Ask ONE question at a time. Wait for the candidate's full answer before proceeding.
2. After each answer, decide: ask a relevant follow-up OR move to the next question. Maximum ONE follow-up per question.
3. Never reveal the expected answer before the candidate responds.
4. Never repeat a question you have already asked.
5. Never invent qualifications or experiences the candidate hasn't mentioned.
6. Maintain a professional, respectful tone throughout.
7. Do not change topics randomly — maintain focus on the role and experience level.
8. After {question_count} questions, conclude the interview professionally.

INTERVIEW STRUCTURE:
- Start with a warm professional greeting and brief introduction.
- Ask opening: "Tell me about yourself."
- Follow with behavioral and situational questions appropriate for the role.
- End with: "Do you have any questions for us?" (candidate's response is noted but not scored).
- Close professionally: "Thank you for your time. We'll review your responses and get back to you."

EVALUATION (internal — do not reveal to candidate during interview):
Evaluate each answer on a scale of 1-10 across these dimensions:
- Relevance: Did the answer address the question?
- Clarity: Was the answer clear and well-structured?
- Depth: Did the answer show sufficient detail and understanding?
- Examples: Did the answer include specific, relevant examples?

Output format after each answer (internal JSON — not spoken):
{{
  "question": "...",
  "answer": "...",
  "scores": {{ "relevance": X, "clarity": X, "depth": X, "examples": X }},
  "follow_up": "..." or null,
  "next_question": "..." or null
}}"""
```

### 3.2 Technical Interview Prompt
```python
TECHNICAL_SYSTEM_PROMPT_TEMPLATE = """You are VOXPREP's professional AI interviewer conducting a structured Technical interview.

CANDIDATE INFORMATION:
- Name: {candidate_name}
- Role Applied For: {role}
- Experience Level: {experience_level}
- Technical Domain: {domain}

YOUR ROLE:
You are a senior technical interviewer at a leading tech company. Your sole job is to assess the candidate's technical knowledge and problem-solving ability through a structured voice interview.

INTERVIEW RULES (STRICT):
1. Ask ONE question at a time. Wait for the full answer.
2. After each answer, ask a relevant follow-up to probe deeper OR move to the next area. Maximum ONE follow-up per question.
3. Never reveal the answer before the candidate responds.
4. Never repeat a question already asked.
5. Adjust difficulty based on the experience level provided.
6. Focus on conceptual understanding, not memorization of syntax.
7. Maintain a professional, challenging but respectful tone.
8. After {question_count} questions, conclude professionally.

TECHNICAL INTERVIEW STRUCTURE:
- Brief professional introduction.
- Warm-up: 1 easy conceptual question.
- Core: 3 questions at appropriate difficulty for the experience level.
- Problem-solving: 1 scenario/approach question ("How would you...").
- Closing: "Any questions about the role or our tech stack?"

EVALUATION (internal — do not reveal during interview):
Score each answer 1-10 on:
- Relevance: Did they answer the actual question?
- Clarity: Was the explanation clear and logical?
- Depth: Did they show deep understanding beyond surface level?
- Examples: Did they cite real-world applications or examples?

Output format after each answer (internal JSON):
{{
  "question": "...",
  "answer": "...",
  "scores": {{ "relevance": X, "clarity": X, "depth": X, "examples": X }},
  "follow_up": "..." or null,
  "next_question": "..." or null
}}"""
```

---

## 4. 4-Dimension Rubric Scoring Architecture

### 4.1 Rubric Dimensions & Criteria (1.0 to 10.0 scale)

1. **Relevance (1.0 - 10.0)**
   - **9.0 - 10.0**: Directly and comprehensively addresses the question without wandering or off-topic detours.
   - **7.0 - 8.9**: Addresses core requirements, minor extraneous details.
   - **5.0 - 6.9**: Partially addresses the question; tangential response.
   - **3.0 - 4.9**: Largely misses the premise or addresses a different topic.
   - **1.0 - 2.9**: Completely evasive, non-responsive, or "I don't know".

2. **Clarity (1.0 - 10.0)**
   - **9.0 - 10.0**: Structured communication (e.g. STAR method: Situation, Task, Action, Result), concise, lucid vocabulary.
   - **7.0 - 8.9**: Coherent, easy to follow, minor hesitation or slightly loose structure.
   - **5.0 - 6.9**: Understandable but rambling, repetitive, or fragmented.
   - **3.0 - 4.9**: Disorganized thoughts, confusing sentence structures.
   - **1.0 - 2.9**: Incoherent or monosyllabic response.

3. **Depth (1.0 - 10.0)**
   - **9.0 - 10.0**: Explains root mechanisms, system trade-offs, edge cases, failure modes, or business impact.
   - **7.0 - 8.9**: Sound technical/behavioral reasoning beyond textbook definitions.
   - **5.0 - 6.9**: Surface-level understanding; buzzwords without mechanism explanation.
   - **3.0 - 4.9**: Superficially shallow; lacks fundamental grounding.
   - **1.0 - 2.9**: Shows no conceptual grasp.

4. **Examples (1.0 - 10.0)**
   - **9.0 - 10.0**: Quantifiable real-world metrics, concrete project references, architecture choices, or production anecdotes.
   - **7.0 - 8.9**: Cites specific scenarios or tools effectively.
   - **5.0 - 6.9**: Mentions generic examples without context or outcomes.
   - **3.0 - 4.9**: Purely hypothetical without practical grounding.
   - **1.0 - 2.9**: No examples provided.

### 4.2 Score Aggregation Formula
- Individual turn score: $S_i = \{r_i, c_i, d_i, e_i\}$
- Cumulative dimension average:
  $$\bar{r} = \frac{1}{N} \sum_{i=1}^N r_i, \quad \bar{c} = \frac{1}{N} \sum_{i=1}^N c_i, \quad \bar{d} = \frac{1}{N} \sum_{i=1}^N d_i, \quad \bar{e} = \frac{1}{N} \sum_{i=1}^N e_i$$
- Overall session score:
  $$\text{Overall} = \frac{\bar{r} + \bar{c} + \bar{d} + \bar{e}}{4.0}$$
  All scores are rounded to 1 decimal place.

---

## 5. Conversational Progression State Machine

```
              ┌────────────────────────┐
              │ start_session()        │
              │ index = 0, follow = 0  │
              └───────────┬────────────┘
                          │
                          ▼
              ┌────────────────────────┐
              │ Candidate Answer       │
              │ process_answer()       │
              └───────────┬────────────┘
                          │
                 ┌────────┴────────┐
                 │ follow_up_count │
                 └────────┬────────┘
             == 0         │         == 1
      ┌───────────────────┴───────────────────┐
      ▼                                       ▼
Should ask follow-up?                   MUST transition to
- LLM suggested follow_up               next question:
- NOT evasive / "I don't know"         - follow_up_count = 0
      │                                 - current_question_index += 1
  YES │ NO                                    │
  ┌───┴───┐                                   │
  ▼       ▼                                   │
Ask Follow-up: Advance to Next:               ▼
- follow = 1  - follow = 0          ┌───────────────────┐
- stay at     - index += 1          │ index >= 5?       │
  index       - is_complete if >= 5 └─────────┬─────────┘
                                        YES   │   NO
                                   ┌──────────┴──────────┐
                                   ▼                     ▼
                             is_complete = True    Next Question
                             Closing message       Spoken response
                             follow_up_or_next     follow_up_or_next
                             = "next"              = "next"
```

### Invariants:
1. `consecutive_follow_ups <= 1`: If turn $N$ resulted in `follow_up_or_next == "follow_up"`, turn $N+1$ MUST result in `follow_up_or_next == "next"`.
2. `current_question_index <= 5`: Reaching index 5 immediately sets `is_complete = True`.
3. If candidate says "I don't know", "skip", or gives `< 5` words, the agent scores low on depth/examples and immediately advances to the next question rather than probing.

---

## 6. Offline Mock Catalog & Heuristic Scoring Fallback

When operating in mock mode (e.g. unit/e2e testing without live NVIDIA NIM keys):

### 6.1 Question Catalogs

#### HR Behavioral Question Catalog (5 Stages)
1. **Introduction & Motivation**:
   - Main: `"Tell me about yourself, your background, and what led you to apply for this {role} position."`
   - Follow-up: `"That's a compelling background. Could you highlight one particular project or achievement you are most proud of from your recent experience?"`
2. **Prioritization & Pressure**:
   - Main: `"Can you describe a situation where you had to balance conflicting priorities or tight deadlines? How did you approach prioritizing tasks?"`
   - Follow-up: `"How did you communicate those adjustments to your stakeholders and team members to ensure everyone remained aligned?"`
3. **Collaboration & Conflict**:
   - Main: `"Tell me about a time you had a disagreement with a colleague or manager over a project decision. How did you handle the conversation, and what was the outcome?"`
   - Follow-up: `"Looking back, is there anything you would handle differently if a similar disagreement arose today?"`
4. **Ownership & Learning from Mistakes**:
   - Main: `"Describe a project or initiative where things did not go as planned. What actions did you take to manage the situation, and what did you learn?"`
   - Follow-up: `"What preventive measures or process improvements did you implement afterwards to ensure it wouldn't happen again?"`
5. **Role Alignment & Career Vision**:
   - Main: `"What aspects of this {role} position excite you most, and where do you see your professional development heading over the next few years?"`
   - Follow-up: `"How do you typically approach learning new skills or technologies to support that career vision?"`
- Closing: `"Thank you for your time, {candidate_name}. We have covered all questions for this session. We'll review your responses and compile your evaluation report."`

#### Technical Question Catalog (5 Stages, Customized to Role)
1. **Foundations / Warm-up**:
   - Main: `"To start, could you explain the differences between synchronous and asynchronous I/O, and when you would choose one over the other?"`
   - Follow-up: `"How does event-driven concurrency compare with multi-threading or multi-processing in terms of memory overhead and CPU-bound workloads?"`
2. **Data & Caching Architecture**:
   - Main: `"How do you design database schemas and caching strategies to ensure high throughput, low latency, and data consistency under heavy read/write load?"`
   - Follow-up: `"When utilizing an in-memory cache like Redis, how do you prevent cache invalidation issues such as cache stampedes or stale reads?"`
3. **Distributed Systems & Reliability**:
   - Main: `"Could you walk me through your strategy for handling fault tolerance, retries, and circuit breakers in a distributed microservices environment?"`
   - Follow-up: `"How do you ensure idempotency when retrying operations across network boundaries?"`
4. **Security & Endpoint Protection**:
   - Main: `"What best practices and architectures do you follow to secure API endpoints against unauthorized access, injection attacks, and rate-limit exhaustion?"`
   - Follow-up: `"How do you validate and manage authentication tokens in high-throughput stateless architectures?"`
5. **System Design & High Concurrency**:
   - Main: `"How would you design a resilient background task processing system or event stream that can reliably handle sudden traffic spikes without data loss?"`
   - Follow-up: `"If worker nodes crash while processing a critical batch of tasks, how does your architecture ensure zero message loss and graceful recovery?"`
- Closing: `"Thank you, {candidate_name}. That concludes our technical interview. We have evaluated your problem-solving and domain knowledge across all five areas, and your comprehensive performance report is ready."`

### 6.2 Heuristic Rubric Evaluator
For automated offline testing:
- **Evasive / Short Detection**: If words `< 5` or contains `"don't know"`, `"skip"`, `"pass"`, or `"no idea"`:
  `scores = {"relevance": 3.5, "clarity": 4.0, "depth": 2.5, "examples": 1.5}`
- **Length Brackets**:
  - `5-15 words`: Base scores `~ 6.5, 6.8, 5.8, 4.8`
  - `16-39 words`: Base scores `~ 7.8, 7.8, 7.2, 6.8`
  - `40+ words`: Base scores `~ 8.6, 8.5, 8.2, 8.0`
- **Keyword Boost**:
  - Boost of `+0.2` per keyword (up to `+1.0`) for: `fastapi`, `kafka`, `redis`, `postgres`, `microservice`, `concurrency`, `star`, `situation`, `action`, `result`, `metric`, `scaled`, `circuit breaker`, `idempotency`, `prometheus`, `pgbouncer`.
- All scores clamped between `1.0` and `10.0`.

---

## 7. Complete Drop-in Code Blueprint (`backend/app/agents/interviewer.py`)

Here is the complete implementation for `backend/app/agents/interviewer.py`:

```python
"""AI Interviewer Agent Module for VOXPREP Backend.
Milestone 2: Phase 2 AI Interviewer Agent and Session Management.

Implements the InterviewSession state machine, HR vs Technical persona prompts,
4-dimension rubric scoring (Relevance, Clarity, Depth, Examples 1-10),
strict question boundary guardrails (max 5 questions, max 1 follow-up),
and a resilient offline mock fallback for testing without live NVIDIA NIM keys.
"""

import copy
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from app.services.llm import chat, is_mock_mode

logger = logging.getLogger("voxprep.agents.interviewer")

# =============================================================================
# Guardrail Constants & Dimension Definitions
# =============================================================================
MAX_QUESTIONS: int = 5
MAX_FOLLOW_UPS_PER_QUESTION: int = 1
VALID_INTERVIEW_TYPES = {"hr", "technical"}
DIMENSIONS = ["relevance", "clarity", "depth", "examples"]

# =============================================================================
# System Prompts per docs/08_AGENT_PROMPTS.md
# =============================================================================
HR_SYSTEM_PROMPT_TEMPLATE = """You are VOXPREP's professional AI interviewer conducting a structured HR interview.

CANDIDATE INFORMATION:
- Name: {candidate_name}
- Role Applied For: {role}
- Experience Level: {experience_level}

YOUR ROLE:
You are a professional HR interviewer. Your sole job during this session is to conduct a realistic, structured interview. You are NOT a tutor or coach during this session.

INTERVIEW RULES (STRICT):
1. Ask ONE question at a time. Wait for the candidate's full answer before proceeding.
2. After each answer, decide: ask a relevant follow-up OR move to the next question. Maximum ONE follow-up per question.
3. Never reveal the expected answer before the candidate responds.
4. Never repeat a question you have already asked.
5. Never invent qualifications or experiences the candidate hasn't mentioned.
6. Maintain a professional, respectful tone throughout.
7. Do not change topics randomly — maintain focus on the role and experience level.
8. After {question_count} questions, conclude the interview professionally.

INTERVIEW STRUCTURE:
- Start with a warm professional greeting and brief introduction.
- Ask opening: "Tell me about yourself."
- Follow with behavioral and situational questions appropriate for the role.
- End with: "Do you have any questions for us?" (candidate's response is noted but not scored).
- Close professionally: "Thank you for your time. We'll review your responses and get back to you."

EVALUATION (internal — do not reveal to candidate during interview):
Evaluate each answer on a scale of 1-10 across these dimensions:
- Relevance: Did the answer address the question?
- Clarity: Was the answer clear and well-structured?
- Depth: Did the answer show sufficient detail and understanding?
- Examples: Did the answer include specific, relevant examples?

Output format after each answer (internal JSON — not spoken):
{{
  "question": "...",
  "answer": "...",
  "scores": {{ "relevance": X, "clarity": X, "depth": X, "examples": X }},
  "follow_up": "..." or null,
  "next_question": "..." or null
}}"""

TECHNICAL_SYSTEM_PROMPT_TEMPLATE = """You are VOXPREP's professional AI interviewer conducting a structured Technical interview.

CANDIDATE INFORMATION:
- Name: {candidate_name}
- Role Applied For: {role}
- Experience Level: {experience_level}
- Technical Domain: {domain}

YOUR ROLE:
You are a senior technical interviewer at a leading tech company. Your sole job is to assess the candidate's technical knowledge and problem-solving ability through a structured voice interview.

INTERVIEW RULES (STRICT):
1. Ask ONE question at a time. Wait for the full answer.
2. After each answer, ask a relevant follow-up to probe deeper OR move to the next area. Maximum ONE follow-up per question.
3. Never reveal the answer before the candidate responds.
4. Never repeat a question already asked.
5. Adjust difficulty based on the experience level provided.
6. Focus on conceptual understanding, not memorization of syntax.
7. Maintain a professional, challenging but respectful tone.
8. After {question_count} questions, conclude professionally.

TECHNICAL INTERVIEW STRUCTURE:
- Brief professional introduction.
- Warm-up: 1 easy conceptual question.
- Core: 3 questions at appropriate difficulty for the experience level.
- Problem-solving: 1 scenario/approach question ("How would you...").
- Closing: "Any questions about the role or our tech stack?"

EVALUATION (internal — do not reveal during interview):
Score each answer 1-10 on:
- Relevance: Did they answer the actual question?
- Clarity: Was the explanation clear and logical?
- Depth: Did they show deep understanding beyond surface level?
- Examples: Did they cite real-world applications or examples?

Output format after each answer (internal JSON):
{{
  "question": "...",
  "answer": "...",
  "scores": {{ "relevance": X, "clarity": X, "depth": X, "examples": X }},
  "follow_up": "..." or null,
  "next_question": "..." or null
}}"""

# =============================================================================
# Curated Offline Mock Catalog
# =============================================================================
MOCK_HR_QUESTIONS: List[Tuple[str, str]] = [
    (
        "Tell me about yourself, your background, and what led you to apply for this {role} position.",
        "That's a compelling background. Could you highlight one particular project or achievement you are most proud of from your recent experience?",
    ),
    (
        "Can you describe a situation where you had to balance conflicting priorities or tight deadlines? How did you approach prioritizing tasks?",
        "How did you communicate those adjustments to your stakeholders and team members to ensure everyone remained aligned?",
    ),
    (
        "Tell me about a time you had a disagreement with a colleague or manager over a project decision. How did you handle the conversation, and what was the outcome?",
        "Looking back, is there anything you would handle differently if a similar disagreement arose today?",
    ),
    (
        "Describe a project or initiative where things did not go as planned. What actions did you take to manage the situation, and what did you learn?",
        "What preventive measures or process improvements did you implement afterwards to ensure it wouldn't happen again?",
    ),
    (
        "What aspects of this {role} position excite you most, and where do you see your professional development heading over the next few years?",
        "How do you typically approach learning new skills or technologies to support that career vision?",
    ),
]

MOCK_TECH_QUESTIONS: List[Tuple[str, str]] = [
    (
        "To start, could you explain the differences between synchronous and asynchronous I/O, and when you would choose one over the other?",
        "How does event-driven concurrency compare with multi-threading or multi-processing in terms of memory overhead and CPU-bound workloads?",
    ),
    (
        "How do you design database schemas and caching strategies to ensure high throughput, low latency, and data consistency under heavy read and write load?",
        "When utilizing an in-memory cache like Redis, how do you prevent cache invalidation issues such as cache stampedes or stale reads?",
    ),
    (
        "Could you walk me through your strategy for handling fault tolerance, retries, and circuit breakers in a distributed microservices environment?",
        "How do you ensure idempotency when retrying operations across network boundaries?",
    ),
    (
        "What best practices and architectures do you follow to secure API endpoints against unauthorized access, injection attacks, and rate-limit exhaustion?",
        "How do you validate and manage authentication tokens in high-throughput stateless architectures?",
    ),
    (
        "How would you design a resilient background task processing system or event stream that can reliably handle sudden traffic spikes without data loss?",
        "If worker nodes crash while processing a critical batch of tasks, how does your architecture ensure zero message loss and graceful recovery?",
    ),
]


def _infer_domain_from_role(role: str) -> str:
    """Infers technical domain string from candidate role."""
    r = role.lower()
    if any(k in r for k in ["backend", "api", "python", "golang", "java", "django", "fastapi"]):
        return "Backend Distributed Systems & Databases"
    if any(k in r for k in ["frontend", "react", "next", "vue", "web"]):
        return "Frontend Architecture, State Management & Web Performance"
    if any(k in r for k in ["cloud", "devops", "sre", "infrastructure", "kubernetes", "aws"]):
        return "Cloud Infrastructure, SRE & CI/CD Pipelines"
    if any(k in r for k in ["data", "ml", "ai", "machine learning", "analytics"]):
        return "Data Engineering, Streaming Pipelines & Machine Learning"
    return "Full Stack Software Engineering"


def _evaluate_mock_answer_heuristics(answer_text: str, question: str) -> Dict[str, float]:
    """Generates realistic rubric dimension scores for offline testing based on response quality."""
    text = (answer_text or "").strip()
    words = text.split()
    word_count = len(words)
    lower = text.lower()

    # Case 1: Evasive / non-answer / "I don't know"
    if word_count < 5 or any(k in lower for k in ["don't know", "do not know", "no idea", "skip", "pass", "not sure"]):
        return {
            "relevance": 3.5,
            "clarity": 4.0,
            "depth": 2.5,
            "examples": 1.5,
        }

    # Case 2: Base score by word count tiers
    if word_count < 15:
        base_relevance = 6.5
        base_clarity = 6.8
        base_depth = 5.8
        base_examples = 4.8
    elif word_count < 40:
        base_relevance = 7.8
        base_clarity = 7.8
        base_depth = 7.2
        base_examples = 6.8
    else:
        base_relevance = 8.6
        base_clarity = 8.5
        base_depth = 8.2
        base_examples = 8.0

    # Case 3: Keyword bonuses (technical & behavioral keywords)
    boost = 0.0
    valuable_keywords = [
        "fastapi", "kafka", "redis", "postgres", "postgresql", "microservice", "concurrency",
        "star", "situation", "task", "action", "result", "metric", "scaled", "trade-off",
        "circuit breaker", "idempotency", "prometheus", "pgbouncer", "latency", "throughput",
        "docker", "kubernetes", "cache", "asyncio", "lock", "index", "sharding", "replica",
    ]
    for kw in valuable_keywords:
        if kw in lower:
            boost += 0.2
    boost = min(boost, 1.2)

    return {
        "relevance": round(min(10.0, max(1.0, base_relevance + boost * 0.4)), 1),
        "clarity": round(min(10.0, max(1.0, base_clarity + boost * 0.4)), 1),
        "depth": round(min(10.0, max(1.0, base_depth + boost * 0.8)), 1),
        "examples": round(min(10.0, max(1.0, base_examples + boost * 0.8)), 1),
    }


def _extract_json_from_llm_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Extracts JSON dictionary from raw LLM output, handling markdown fences or leading/trailing text."""
    if not response_text or not response_text.strip():
        return None

    cleaned = response_text.strip()

    # Strip markdown fenced code blocks ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # Direct parse
    if cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            return json.loads(cleaned)
        except Exception:
            pass

    # Regex search for first outer balanced braces
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except Exception:
            pass

    return None


class InterviewSession:
    """Stateful interview session model for Agent 1 (AI Interviewer).

    Manages interview progression, question boundaries (<= 5 questions, <= 1 follow-up),
    4-dimension answer scoring, conversational flow, and state serialization.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        candidate_name: str = "Candidate",
        role: str = "Software Engineer",
        experience_level: str = "mid-level",
        interview_type: str = "technical",
        user_id: Optional[str] = None,
        question_history: Optional[List[Dict[str, Any]]] = None,
        current_question_index: int = 0,
        follow_up_count: int = 0,
        is_complete: bool = False,
        dimension_scores: Optional[Dict[str, float]] = None,
        current_question: Optional[str] = None,
        created_at: Optional[str] = None,
        completed_at: Optional[str] = None,
    ):
        self.session_id: str = session_id or str(uuid.uuid4())
        self.candidate_name: str = candidate_name.strip() or "Candidate"
        self.role: str = role.strip() or "Software Engineer"
        self.experience_level: str = experience_level.strip() or "mid-level"
        self.interview_type: str = interview_type.lower().strip() if interview_type else "technical"
        if self.interview_type not in VALID_INTERVIEW_TYPES:
            self.interview_type = "technical"

        self.user_id: Optional[str] = user_id
        self.current_question_index: int = max(0, current_question_index)
        self.follow_up_count: int = max(0, follow_up_count)
        self.is_complete: bool = is_complete
        self.current_question: str = current_question or ""
        self.created_at: str = created_at or datetime.now(timezone.utc).isoformat()
        self.completed_at: Optional[str] = completed_at

        self.question_history: List[Dict[str, Any]] = (
            copy.deepcopy(question_history) if question_history is not None else []
        )
        self.dimension_scores: Dict[str, float] = (
            copy.deepcopy(dimension_scores)
            if dimension_scores is not None
            else {
                "relevance": 0.0,
                "clarity": 0.0,
                "depth": 0.0,
                "examples": 0.0,
                "overall": 0.0,
            }
        )

    def get_system_prompt(self) -> str:
        """Constructs system prompt adhering to docs/08_AGENT_PROMPTS.md."""
        if self.interview_type == "hr":
            return HR_SYSTEM_PROMPT_TEMPLATE.format(
                candidate_name=self.candidate_name,
                role=self.role,
                experience_level=self.experience_level,
                question_count=MAX_QUESTIONS,
            )
        else:
            domain = _infer_domain_from_role(self.role)
            return TECHNICAL_SYSTEM_PROMPT_TEMPLATE.format(
                candidate_name=self.candidate_name,
                role=self.role,
                experience_level=self.experience_level,
                domain=domain,
                question_count=MAX_QUESTIONS,
            )

    def _get_mock_catalog(self) -> List[Tuple[str, str]]:
        """Returns the appropriate mock question catalog formatted for the candidate."""
        source = MOCK_TECH_QUESTIONS if self.interview_type == "technical" else MOCK_HR_QUESTIONS
        catalog: List[Tuple[str, str]] = []
        for main_q, follow_q in source:
            catalog.append((
                main_q.format(role=self.role, candidate_name=self.candidate_name),
                follow_q.format(role=self.role, candidate_name=self.candidate_name),
            ))
        return catalog

    def _update_dimension_scores(self) -> None:
        """Recalculates average dimension scores across all recorded answer evaluations."""
        if not self.question_history:
            return

        sums = {dim: 0.0 for dim in DIMENSIONS}
        valid_count = 0

        for item in self.question_history:
            scores = item.get("scores")
            if isinstance(scores, dict):
                valid_count += 1
                for dim in DIMENSIONS:
                    sums[dim] += float(scores.get(dim, 5.0))

        if valid_count > 0:
            avg_scores = {dim: round(sums[dim] / valid_count, 1) for dim in DIMENSIONS}
            overall = round(sum(avg_scores[dim] for dim in DIMENSIONS) / len(DIMENSIONS), 1)
            avg_scores["overall"] = overall
            self.dimension_scores = avg_scores

    async def start_session(self) -> str:
        """Initializes interview session, establishes first question, and returns opening message."""
        self.current_question_index = 0
        self.follow_up_count = 0
        self.is_complete = False

        catalog = self._get_mock_catalog()
        first_main_question, _ = catalog[0]
        self.current_question = first_main_question

        if self.interview_type == "technical":
            opening_message = (
                f"Welcome {self.candidate_name} to your technical interview for the {self.role} position. "
                f"Let's begin: {first_main_question}"
            )
        else:
            opening_message = (
                f"Hello {self.candidate_name}, welcome to your HR interview for the {self.role} position. "
                f"Let's start off: {first_main_question}"
            )

        logger.info(
            f"InterviewSession {self.session_id} started for {self.candidate_name} ({self.interview_type})."
        )
        return opening_message

    async def process_answer(self, answer_text: str) -> Dict[str, Any]:
        """Evaluates candidate answer, updates history & scores, and decides follow-up or next question.

        Args:
            answer_text: Spoken response transcribed from user.

        Returns:
            Dictionary with keys:
            - spoken_response: str
            - is_complete: bool
            - follow_up_or_next: str ("follow_up" | "next")
            - scores: dict (relevance, clarity, depth, examples)
            - current_question_index: int
            - total_questions: int (5)
        """
        # Guard: Session already completed
        if self.is_complete:
            closing = f"Thank you {self.candidate_name}. That concludes our interview questions. Your report is ready."
            return {
                "spoken_response": closing,
                "is_complete": True,
                "follow_up_or_next": "next",
                "scores": self.dimension_scores,
                "current_question_index": self.current_question_index,
                "total_questions": MAX_QUESTIONS,
            }

        answer_clean = (answer_text or "").strip()
        catalog = self._get_mock_catalog()
        safe_idx = min(self.current_question_index, len(catalog) - 1)
        current_pair = catalog[safe_idx]
        default_follow_up = current_pair[1]

        scores: Dict[str, float] = {}
        proposed_follow_up: Optional[str] = None
        proposed_next: Optional[str] = None

        # Execute Live LLM or Fallback to Heuristics
        if not is_mock_mode():
            system_prompt = self.get_system_prompt()
            messages = [
                {
                    "role": "user",
                    "content": (
                        f"Current Question: {self.current_question}\n"
                        f"Candidate Answer: {answer_clean}\n"
                        f"Follow-ups already used for this question: {self.follow_up_count}\n"
                        f"Current question index: {self.current_question_index + 1} of {MAX_QUESTIONS}."
                    ),
                }
            ]
            try:
                llm_output = await chat(messages, system_prompt=system_prompt)
                parsed = _extract_json_from_llm_response(llm_output)
                if parsed and isinstance(parsed.get("scores"), dict):
                    raw_scores = parsed["scores"]
                    scores = {
                        dim: round(float(raw_scores.get(dim, 7.0)), 1)
                        for dim in DIMENSIONS
                    }
                    proposed_follow_up = parsed.get("follow_up")
                    proposed_next = parsed.get("next_question")
            except Exception as exc:
                logger.warning(f"Live LLM evaluation error: {exc}. Falling back to rubric heuristics.")

        if not scores:
            scores = _evaluate_mock_answer_heuristics(answer_clean, self.current_question)

        # Candidate responsiveness checks
        is_evasive = (
            len(answer_clean.split()) < 5
            or any(k in answer_clean.lower() for k in ["don't know", "do not know", "no idea", "skip", "pass"])
        )

        # Decision State Machine
        if self.follow_up_count == 0 and not is_evasive:
            # Decide to ask follow-up (Max 1 per question guardrail)
            follow_up_question = proposed_follow_up or default_follow_up
            self.follow_up_count = 1
            follow_up_or_next = "follow_up"
            spoken_response = follow_up_question

            # Record history
            self.question_history.append({
                "question_index": self.current_question_index,
                "question": self.current_question,
                "answer": answer_clean,
                "scores": scores,
                "follow_up_used": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self.current_question = follow_up_question

        else:
            # Advance to next question (follow-up already used or candidate was evasive)
            self.follow_up_count = 0
            self.question_history.append({
                "question_index": self.current_question_index,
                "question": self.current_question,
                "answer": answer_clean,
                "scores": scores,
                "follow_up_used": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            self.current_question_index += 1
            follow_up_or_next = "next"

            # Check 5-Question Boundary Guardrail
            if self.current_question_index >= MAX_QUESTIONS:
                self.is_complete = True
                self.completed_at = datetime.now(timezone.utc).isoformat()
                spoken_response = (
                    f"Thank you for your time, {self.candidate_name}. That concludes our structured interview questions. "
                    "We'll review your responses and compile your evaluation report."
                )
                self.current_question = ""
            else:
                next_idx = self.current_question_index
                next_q = (
                    proposed_next
                    if (proposed_next and not is_mock_mode())
                    else catalog[next_idx][0]
                )
                spoken_response = next_q
                self.current_question = next_q

        self._update_dimension_scores()

        return {
            "spoken_response": spoken_response,
            "is_complete": self.is_complete,
            "follow_up_or_next": follow_up_or_next,
            "scores": scores,
            "current_question_index": self.current_question_index,
            "total_questions": MAX_QUESTIONS,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serializes session state to a dictionary conforming to Supabase schema."""
        return {
            "id": self.session_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "candidate_name": self.candidate_name,
            "role_applied": self.role,
            "role": self.role,
            "experience_level": self.experience_level,
            "interview_type": self.interview_type,
            "questions": [item.get("question", "") for item in self.question_history],
            "answers": [item.get("answer", "") for item in self.question_history],
            "scores": {
                "dimension_scores": self.dimension_scores,
                "question_history": self.question_history,
            },
            "current_question_index": self.current_question_index,
            "follow_up_count": self.follow_up_count,
            "is_complete": self.is_complete,
            "current_question": self.current_question,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterviewSession":
        """Reconstructs an InterviewSession instance from a dictionary or Supabase row."""
        scores_field = data.get("scores")
        dimension_scores = None
        history: List[Dict[str, Any]] = []

        if isinstance(scores_field, dict):
            dimension_scores = scores_field.get("dimension_scores")
            history = scores_field.get("question_history", [])
        elif isinstance(scores_field, list):
            history = []

        if not history and isinstance(data.get("question_history"), list):
            history = data["question_history"]

        role = data.get("role_applied") or data.get("role") or "Software Engineer"
        session_id = data.get("id") or data.get("session_id") or str(uuid.uuid4())

        return cls(
            session_id=session_id,
            candidate_name=data.get("candidate_name", "Candidate"),
            role=role,
            experience_level=data.get("experience_level", "mid-level"),
            interview_type=data.get("interview_type", "technical"),
            user_id=data.get("user_id"),
            question_history=history,
            current_question_index=data.get("current_question_index", 0),
            follow_up_count=data.get("follow_up_count", 0),
            is_complete=data.get("is_complete", False),
            dimension_scores=dimension_scores,
            current_question=data.get("current_question", ""),
            created_at=data.get("created_at"),
            completed_at=data.get("completed_at"),
        )
```

---

## 8. Integration Interface Guide for Peers

### 8.1 For `explorer_m2_2` (`services/report.py` & Supabase Persistence)
- `InterviewSession.to_dict()` outputs the exact JSON structure expected by `generate_report(session_data)`:
  - `session_data["candidate_name"]`, `session_data["role_applied"]`, `session_data["interview_type"]`.
  - `session_data["scores"]["dimension_scores"]` contains `{relevance, clarity, depth, examples, overall}`.
  - `session_data["scores"]["question_history"]` contains every question, candidate answer, and per-question score breakdown.
- Supabase persistence helper in `db/supabase.py` can directly store `session.to_dict()`.

### 8.2 For `explorer_m2_3` (`routers/interview.py` & Test Suite)
- `POST /interview/start`:
  ```python
  session = InterviewSession(
      candidate_name=req.candidate_name,
      role=req.role,
      experience_level=req.experience_level,
      interview_type=req.interview_type,
      user_id=req.user_id,
  )
  opening = await session.start_session()
  # Save session.to_dict() to Supabase
  return {"session_id": session.session_id, "opening_message": opening}
  ```
- `POST /interview/respond`:
  ```python
  # Fetch row from Supabase
  session = InterviewSession.from_dict(row)
  res = await session.process_answer(req.answer_text)
  # Update row in Supabase with session.to_dict()
  return res
  ```
- `POST /interview/end`:
  ```python
  session = InterviewSession.from_dict(row)
  session.is_complete = True
  # report = await generate_report(session.to_dict())
  # Update Supabase row with status="completed", report=report
  return {"session_id": session.session_id, "status": "completed", "report": report}
  ```

---

## 9. Verification & Quality Assurance Strategy

1. **Unit Test Coverage**:
   - Verify `start_session()` returns opening message and sets `current_question_index = 0`.
   - Verify `process_answer()` computes scores in range `[1.0, 10.0]` on all 4 dimensions.
   - Verify follow-up guardrail: `follow_up_count == 1` followed by `follow_up_count == 0` on next answer (strictly 1 follow-up max).
   - Verify boundary guardrail: session marks `is_complete == True` on 5th core question.
   - Verify `to_dict()` and `from_dict()` roundtrip preservation.
2. **E2E Compatibility**:
   - `test_tier1_features.py`: `test_interview_start_isolated`, `test_interview_respond_isolated`, `test_interview_end_isolated`.
   - `test_tier2_boundaries.py`: `test_interview_max_1_follow_up_boundary` (`consecutive_follow_ups <= 1`).
   - `test_tier4_scenarios.py`: `test_scenario_full_technical_interview_simulation`, `test_scenario_full_hr_behavioral_interview_simulation`.
