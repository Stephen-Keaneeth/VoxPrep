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
        report: Optional[Dict[str, Any]] = None,
    ):
        self.session_id: str = session_id or str(uuid.uuid4())
        self.candidate_name: str = (candidate_name or "Candidate").strip()
        self.role: str = (role or "Software Engineer").strip()
        self.experience_level: str = (experience_level or "mid-level").strip()
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
        self.report: Optional[Dict[str, Any]] = copy.deepcopy(report) if report else None

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

    async def start_session(
        self,
        candidate_name: Optional[str] = None,
        role: Optional[str] = None,
        experience: Optional[str] = None,
        interview_type: Optional[str] = None,
    ) -> str:
        """Initializes interview session, establishes first question, and returns opening message."""
        if candidate_name:
            self.candidate_name = candidate_name.strip()
        if role:
            self.role = role.strip()
        if experience:
            self.experience_level = experience.strip()
        if interview_type:
            val = interview_type.lower().strip()
            if val in VALID_INTERVIEW_TYPES:
                self.interview_type = val

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
            - question_index: int
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
                "question_index": self.current_question_index,
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

        # Candidate responsiveness checks per docs/07_GUARDRAILS.md
        words = answer_clean.split()
        is_one_word = len(words) <= 1
        is_evasive = (
            len(words) < 5
            or any(k in answer_clean.lower() for k in [
                "don't know", "do not know", "no idea", "skip", "pass", "not sure", "honestly don't know"
            ])
        )

        # Decision State Machine
        if is_one_word and self.follow_up_count == 0:
            # Candidate gave 1-word answer: ask for elaboration once
            self.follow_up_count = 1
            follow_up_or_next = "follow_up"
            spoken_response = "Could you please elaborate a bit more on that?"
            self.question_history.append({
                "question_index": self.current_question_index,
                "question": self.current_question,
                "answer": answer_clean,
                "scores": scores,
                "follow_up_used": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self.current_question = spoken_response

        elif self.follow_up_count == 0 and not is_evasive:
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
            # Advance to next question (follow-up already used or candidate was evasive / "I don't know")
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
                if is_evasive:
                    spoken_response = f"Understood, let's move forward. {next_q}"
                else:
                    spoken_response = next_q
                self.current_question = next_q

        self._update_dimension_scores()

        return {
            "spoken_response": spoken_response,
            "is_complete": self.is_complete,
            "follow_up_or_next": follow_up_or_next,
            "scores": scores,
            "question_index": self.current_question_index,
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
            "question_count": self.current_question_index,
            "follow_up_count": self.follow_up_count,
            "is_complete": self.is_complete,
            "status": "completed" if self.is_complete else "in_progress",
            "current_question": self.current_question,
            "report": self.report,
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
        elif not history and isinstance(data.get("history"), list):
            history = data["history"]

        role = data.get("role_applied") or data.get("role") or "Software Engineer"
        session_id = data.get("id") or data.get("session_id") or str(uuid.uuid4())
        is_comp = data.get("is_complete")
        if is_comp is None and data.get("status") == "completed":
            is_comp = True

        idx = data.get("current_question_index")
        if idx is None:
            idx = data.get("question_count", 0)

        return cls(
            session_id=session_id,
            candidate_name=data.get("candidate_name", "Candidate"),
            role=role,
            experience_level=data.get("experience_level", "mid-level"),
            interview_type=data.get("interview_type", "technical"),
            user_id=data.get("user_id"),
            question_history=history,
            current_question_index=int(idx or 0),
            follow_up_count=int(data.get("follow_up_count", 0)),
            is_complete=bool(is_comp),
            dimension_scores=dimension_scores,
            current_question=data.get("current_question", ""),
            created_at=data.get("created_at"),
            completed_at=data.get("completed_at"),
            report=data.get("report"),
        )
