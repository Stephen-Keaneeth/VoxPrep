"""AI Communication Coach Agent Module for VOXPREP Backend.
Milestone 3: Phase 3 AI Communication Coach Agent.

Implements the CoachSession state machine, supporting 3 pedagogical modes:
- "conversation": General conversational fluency, natural cadence, and confidence.
- "answer_training": STAR method structure, conciseness, and impact metrics.
- "english_improvement": Grammar, vocabulary, phrasing, and filler word reduction.

Adheres strictly to docs/08_AGENT_PROMPTS.md, docs/07_GUARDRAILS.md, and
docs/05_ACCEPTANCE_CRITERIA.md. Provides a resilient offline mock catalog
for deterministic test execution without live NVIDIA NIM keys.
"""

import copy
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from app.db.coach_persistence import (
    get_coach_session,
    get_user_profile,
    save_coach_session,
    update_user_communication_profile,
    VALID_COACH_MODES,
    VALID_SKILL_LEVELS,
)
from app.db.supabase import get_supabase_client
from app.services.llm import chat, is_mock_mode

logger = logging.getLogger("voxprep.agents.coach")

MAX_CORRECTIONS_PER_EXCHANGE: int = 2

# =============================================================================
# System Prompts per docs/08_AGENT_PROMPTS.md
# =============================================================================
COACH_BASE_PROMPT_TEMPLATE = """You are VOXPREP's AI Communication Coach — a friendly, patient, and supportive language mentor.

USER PROFILE:
- Name: {user_name}
- Skill Level: {skill_level} (beginner / intermediate / advanced)
- Known Weak Areas: {weak_areas}
- Known Strong Areas: {strong_areas}
- Mode: {mode}

YOUR PERSONALITY:
- Warm, encouraging, and supportive
- Never judgmental or condescending
- Patient — celebrate small wins
- Clear and simple in your explanations

CORE RULES:
1. Never interrupt while the user is speaking. Always wait for them to finish.
2. After the user speaks, provide feedback AFTER acknowledging their response.
3. Focus on the 1-2 most impactful corrections per exchange — not every mistake.
4. Always provide a BETTER ALTERNATIVE for any corrected phrase.
5. Explain WHY the alternative is better in simple terms.
6. Adapt difficulty to the user's skill level.
7. Do not repeat the same exercise more than twice in a session.
8. Never claim to detect emotions or confidence from voice.
9. End the session with a positive, specific summary of what was practiced.

CORRECTION FORMAT (when you correct something):
"[Acknowledge what they said]. One small improvement: instead of saying '[their phrase]', you could say '[better alternative]'. This sounds more natural because [brief reason]. Want to try it?"

OUTPUT FORMAT per exchange (internal JSON — not spoken):
{{
  "coach_message": "<what you say to the user>",
  "user_response_text": "<STT output of user's response>",
  "correction": {{
    "original": "<user's phrase that could be improved>",
    "improved": "<better alternative>",
    "reason": "<brief explanation>"
  }} or null,
  "next_prompt": "<your next message/challenge to the user>"
}}"""

MODE_INSTRUCTIONS = {
    "conversation": """
MODE SPECIFIC INSTRUCTIONS: Conversation Practice Mode
- Engage in a natural conversation on everyday topics (travel, hobbies, food, plans, daily routines).
- Ask open-ended questions. Respond naturally to what the user shares.
- Focus on conversational fluency, natural cadence, and confidence.
- Gradually introduce more complex topics if the user is responding well.
- Only correct noticeable grammatical flaws or awkward idioms; prioritize conversational momentum over perfection.""",

    "answer_training": """
MODE SPECIFIC INSTRUCTIONS: Interview Answer Training Mode
- Give the user common interview questions and help them structure better answers.
- Teach and reinforce the STAR method (Situation, Task, Action, Result) through practice.
- After each answer, evaluate structure, conciseness, and impact metrics.
- If the answer lacks structure, guide them on which part of STAR was missing.
- Help them make their answers concise and metric-driven (e.g. quantifying results).
- Sample questions to rotate through (adjusted for skill level):
  - "Tell me about yourself."
  - "What is your greatest strength?"
  - "Describe a challenge you overcame."
  - "Where do you see yourself in 5 years?" """,

    "english_improvement": """
MODE SPECIFIC INSTRUCTIONS: English Improvement Mode
- Focus on grammar, sentence structure, vocabulary, and natural-sounding English phrasing.
- Detect and reduce filler words ("um", "like", "you know", "basically", "so yeah").
- Engage in structured exercises: sentence completion, correction practice, topic discussions.
- Be gentle. Strictly limit corrections to at most 1-2 items per exchange.
- Provide simple, clear grammar explanations and natural native idioms.
- Build from simple to complex based on the user's level ({skill_level}).""",
}

# =============================================================================
# Curated Opening Prompts & Messages
# =============================================================================
OPENING_MESSAGES = {
    "conversation": (
        "Hello {name}! I'm your VOXPREP AI Communication Coach. "
        "In this session, we'll practice natural, relaxed conversation on everyday topics to boost your spoken fluency and confidence. "
        "To get started, how was your day today, or is there a favorite hobby you've been spending time on lately?"
    ),
    "answer_training": (
        "Welcome {name}! I'm your AI Communication Coach for Interview Answer Training. "
        "Here, we'll practice structuring your responses using the STAR method (Situation, Task, Action, Result) so your answers are clear, concise, and memorable. "
        "Let's begin with a classic question: Could you tell me a little bit about yourself and your background?"
    ),
    "english_improvement": (
        "Hi {name}! I'm your AI Communication Coach for English Improvement. "
        "We'll focus on grammar, vocabulary, and natural phrasing at a comfortable pace. "
        "Let's start with a warm-up: could you tell me about something you did yesterday or a recent activity you enjoyed?"
    ),
}

OPENING_PROMPTS = {
    "conversation": "How was your day today, or is there a favorite hobby you've been spending time on lately?",
    "answer_training": "Could you tell me a little bit about yourself, your background, and your key areas of expertise?",
    "english_improvement": "Could you tell me about something you did yesterday or a recent activity you enjoyed?",
}


# =============================================================================
# Helper Utilities & Mock Catalog
# =============================================================================

def _extract_json_from_llm_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Extracts JSON dictionary from raw LLM output, handling markdown code fences."""
    if not response_text or not response_text.strip():
        return None

    cleaned = response_text.strip()

    # Match ```json ... ``` code blocks
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # Direct JSON parse
    if cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            return json.loads(cleaned)
        except Exception:
            pass

    # Regex search for outer balanced braces
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except Exception:
            pass

    return None


def _evaluate_mock_coach_heuristics(
    mode: str,
    user_text: str,
    current_prompt: str,
    user_profile: Dict[str, Any],
) -> Dict[str, Any]:
    """Generates deterministic, high-quality feedback and corrections for offline tests."""
    clean = (user_text or "").strip()
    lower = clean.lower()
    words = clean.split()

    # Guardrail 1: Terse / 1-word answer
    if len(words) <= 1:
        return {
            "coach_message": "Thanks for sharing! Can you tell me a little bit more about that so we can practice expanding your ideas?",
            "correction": None,
            "next_prompt": "What is one specific detail or example you can add to that?",
        }

    # Guardrail 2: Frustrated or "I don't know"
    if any(k in lower for k in ["don't know", "do not know", "no idea", "not sure", "skip"]):
        return {
            "coach_message": "No worries at all! Let's try something a bit easier to get the momentum going.",
            "correction": None,
            "next_prompt": "What is your favorite food or meal to enjoy after a busy day?",
        }

    # Mode 1: English Improvement (Grammar, Vocabulary, Phrasing, Filler words)
    if mode == "english_improvement":
        if "was go" in lower:
            return {
                "coach_message": (
                    "That sounds like a great experience! One small improvement: instead of saying 'was go', "
                    "you could say 'went'. This sounds more natural because it's the simple past tense. Want to try it?"
                ),
                "correction": {
                    "original": "was go",
                    "improved": "went",
                    "reason": "Use simple past tense 'went' for a completed past action.",
                },
                "next_prompt": "Next, what do you usually like to do when you have free time on the weekend?",
            }
        elif "was read" in lower:
            return {
                "coach_message": (
                    "That's wonderful! One small grammar tip: instead of 'was read', saying 'read' "
                    "sounds much more natural for a completed action."
                ),
                "correction": {
                    "original": "was read",
                    "improved": "read",
                    "reason": "Use simple past tense 'read' for a completed past action.",
                },
                "next_prompt": "What was the most interesting concept you learned from that book?",
            }
        elif "buyed" in lower:
            return {
                "coach_message": (
                    "Nice! One quick note on vocabulary: instead of saying 'buyed', we say 'bought'. "
                    "'Buy' is an irregular verb in English. Great effort!"
                ),
                "correction": {
                    "original": "buyed",
                    "improved": "bought",
                    "reason": "'Buy' is an irregular verb whose past tense form is 'bought'.",
                },
                "next_prompt": "What is something interesting you bought recently?",
            }
        elif "fishes" in lower:
            return {
                "coach_message": (
                    "That's wonderful! One small grammar tip: 'fish' is usually uncountable when talking about animals or food. "
                    "Instead of 'fishes', saying 'a lot of fish' sounds much more natural."
                ),
                "correction": {
                    "original": "fishes",
                    "improved": "fish",
                    "reason": "'Fish' is typically an uncountable plural noun in standard English.",
                },
                "next_prompt": "What do you enjoy most about nature or outdoor activities?",
            }
        elif "will went" in lower:
            return {
                "coach_message": (
                    "I love that forward-looking plan! One small tweak: instead of 'will went', say 'will go'. "
                    "After modal verbs like 'will', always use the base form of the verb."
                ),
                "correction": {
                    "original": "will went",
                    "improved": "will go",
                    "reason": "Use the base form of the verb ('go') following the auxiliary verb 'will'.",
                },
                "next_prompt": "Who would you invite along if you went there again?",
            }
        elif any(f in lower for f in ["um", "uh", "basically like", "you know"]):
            return {
                "coach_message": (
                    "Your explanation was very clear! One technique to sound even more confident is replacing filler words "
                    "like 'um' with a brief, silent pause. A pause gives you time to think and sounds very executive."
                ),
                "correction": {
                    "original": "um / filler words",
                    "improved": "[brief pause]",
                    "reason": "Deliberate pauses project poise and reduce reliance on conversational fillers.",
                },
                "next_prompt": "Could you share one more goal you have for this week?",
            }
        else:
            # Clean English - No corrections needed
            return {
                "coach_message": "That's well expressed! You used clear sentence structure and natural vocabulary.",
                "correction": None,
                "next_prompt": "What is a project or skill you are currently working on developing?",
            }

    # Mode 2: Interview Answer Training (STAR Method, Impact, Conciseness)
    elif mode == "answer_training":
        has_star = any(k in lower for k in ["situation", "task", "action", "result", "metric", "%", "improved", "led", "delivered", "increased"])
        if not has_star and len(words) > 8:
            return {
                "coach_message": (
                    "Great start! You explained the context well. One small improvement: to make your answer stand out, "
                    "try applying the STAR method by highlighting the specific Action you personally took and the measurable Result."
                ),
                "correction": {
                    "original": clean[:60] + "..." if len(clean) > 60 else clean,
                    "improved": "Frame your answer with: Situation, Task, Action you took, and the measurable Result (STAR).",
                    "reason": "The STAR framework gives interviewers a concrete, structured picture of your individual impact.",
                },
                "next_prompt": "Can you describe the specific outcome or result of that initiative?",
            }
        else:
            return {
                "coach_message": "Excellent answer! You structured your points effectively and highlighted your direct impact.",
                "correction": None,
                "next_prompt": "Now, can you describe a time you had to overcome a technical obstacle or tight deadline?",
            }

    # Mode 3: Conversation Practice (Fluency, Cadence, Open-ended flow)
    else:
        if "was go" in lower:
            return {
                "coach_message": (
                    "That sounds like fun! One small tip: instead of 'was go', saying 'went' sounds very natural. "
                    "Did you go with friends or family?"
                ),
                "correction": {
                    "original": "was go",
                    "improved": "went",
                    "reason": "Use simple past tense 'went' for completed past actions.",
                },
                "next_prompt": "Did you go with friends or family, and what was the highlight of the day?",
            }
        return {
            "coach_message": "That sounds really interesting! It's great to hear your perspective on that.",
            "correction": None,
            "next_prompt": "What inspired you to get started with that, and what do you enjoy most about it?",
        }


# =============================================================================
# CoachSession Class Implementation
# =============================================================================

class CoachSession:
    """Stateful communication coach session model for Agent 2 (AI Communication Coach).

    Manages interactive pedagogical exchanges across three specialized modes:
    - "conversation": Everyday conversational cadence and confidence.
    - "answer_training": STAR method structure, conciseness, and metrics.
    - "english_improvement": Grammar, vocabulary, phrasing, and filler words.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        mode: str = "conversation",
        history: Optional[List[Dict[str, Any]]] = None,
        corrections: Optional[List[Dict[str, Any]]] = None,
        user_profile: Optional[Dict[str, Any]] = None,
        current_prompt: Optional[str] = None,
        is_complete: bool = False,
        summary: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        telemetry: Optional[Dict[str, Any]] = None,
    ):
        self.session_id: str = session_id or str(uuid.uuid4())
        self.user_id: Optional[str] = user_id
        self.mode: str = mode.lower().strip() if mode else "conversation"
        if self.mode not in VALID_COACH_MODES:
            self.mode = "conversation"

        self.history: List[Dict[str, Any]] = copy.deepcopy(history) if history is not None else []
        self.corrections: List[Dict[str, Any]] = copy.deepcopy(corrections) if corrections is not None else []

        # If corrections list was empty but history had corrections, extract them
        if not self.corrections and self.history:
            for ex in self.history:
                if isinstance(ex, dict) and ex.get("correction"):
                    corr = ex["correction"]
                    if isinstance(corr, dict) and corr.get("original") and corr.get("improved"):
                        self.corrections.append(corr)

        self.user_profile: Dict[str, Any] = copy.deepcopy(user_profile) if user_profile else {
            "user_name": "Alex Candidate",
            "skill_level": "intermediate",
            "weak_areas": [],
            "strong_areas": [],
            "sessions_count": 0,
        }
        self.current_prompt: str = current_prompt or OPENING_PROMPTS.get(self.mode, "")
        self.is_complete: bool = is_complete
        self.summary: Optional[Dict[str, Any]] = copy.deepcopy(summary) if summary else None
        self.created_at: str = created_at or datetime.now(timezone.utc).isoformat()
        self.completed_at: Optional[str] = completed_at
        self.telemetry: Dict[str, Any] = copy.deepcopy(telemetry) if telemetry else {
            "corrections_count": len(self.corrections),
            "turns_count": len(self.history),
            "fallback_used": False,
        }

    def get_system_prompt(self) -> str:
        """Constructs system prompt adhering strictly to docs/08_AGENT_PROMPTS.md."""
        user_name = self.user_profile.get("user_name") or self.user_profile.get("name") or "Alex Candidate"
        skill_level = self.user_profile.get("skill_level", "intermediate")
        weak_areas = ", ".join(self.user_profile.get("weak_areas", [])) or "None identified yet"
        strong_areas = ", ".join(self.user_profile.get("strong_areas", [])) or "Active participation"

        base = COACH_BASE_PROMPT_TEMPLATE.format(
            user_name=user_name,
            skill_level=skill_level,
            weak_areas=weak_areas,
            strong_areas=strong_areas,
            mode=self.mode,
        )
        mode_instruction = MODE_INSTRUCTIONS.get(self.mode, "").format(skill_level=skill_level)
        return f"{base}\n\n{mode_instruction}"

    async def load_user_profile(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Loads user communication profile from Supabase users table via coach_persistence."""
        uid = user_id or self.user_id
        if not uid:
            return self.user_profile

        try:
            profile_record = await get_user_profile(uid)
            if profile_record:
                name = profile_record.get("name") or "Alex Candidate"
                comm_prof = profile_record.get("communication_profile") or profile_record
                self.user_profile = {
                    "user_name": name,
                    "name": name,
                    "skill_level": comm_prof.get("skill_level", "intermediate"),
                    "weak_areas": list(comm_prof.get("weak_areas", [])),
                    "strong_areas": list(comm_prof.get("strong_areas", [])),
                    "sessions_count": int(comm_prof.get("sessions_count", 0)),
                }
                return self.user_profile
        except Exception as exc:
            logger.warning(f"Notice: Could not load user profile for {uid}: {exc}. Using default profile.")

        return self.user_profile

    async def start_session(
        self,
        user_id: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> str:
        """Initializes coach session, loads candidate profile, and returns warm opening greeting."""
        if user_id:
            self.user_id = user_id
        if mode:
            val = mode.lower().strip()
            if val in VALID_COACH_MODES:
                self.mode = val

        # Load user profile from Supabase
        await self.load_user_profile(self.user_id)

        user_name = self.user_profile.get("user_name") or self.user_profile.get("name") or "Alex Candidate"
        template = OPENING_MESSAGES.get(self.mode, OPENING_MESSAGES["conversation"])
        opening_message = template.format(name=user_name)
        self.current_prompt = OPENING_PROMPTS.get(self.mode, "")
        self.is_complete = False

        logger.info(f"CoachSession {self.session_id} started in mode '{self.mode}' for user {self.user_id}.")
        return opening_message

    async def process_response(
        self,
        *args: Any,
        user_text: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Evaluates candidate response, provides supportive feedback and at most 1-2 corrections.

        Signature supports flexible positional and keyword invocation:
        - session.process_response("user text")
        - session.process_response("session_id", "user text")
        - session.process_response(user_text="...", session_id="...")
        """
        if args:
            if len(args) == 1:
                user_text = str(args[0])
            elif len(args) >= 2:
                session_id = str(args[0])
                user_text = str(args[1])

        clean_text = (user_text or "").strip()
        if session_id and session_id != self.session_id:
            self.session_id = session_id

        # Guard: Session already completed
        if self.is_complete:
            return {
                "coach_message": "Our coaching session is currently complete. You did a wonderful job!",
                "correction": None,
                "next_prompt": "Feel free to start a new session whenever you're ready to practice again.",
                "user_response_text": clean_text,
            }

        coach_message: Optional[str] = None
        correction: Optional[Dict[str, str]] = None
        next_prompt: Optional[str] = None

        # Execute Live LLM or Fallback to Curated Heuristics
        if not is_mock_mode():
            system_prompt = self.get_system_prompt()
            messages: List[Dict[str, str]] = []
            for ex in self.history[-3:]:
                if ex.get("coach_message"):
                    messages.append({"role": "assistant", "content": ex["coach_message"]})
                if ex.get("user_text"):
                    messages.append({"role": "user", "content": ex["user_text"]})

            messages.append({
                "role": "user",
                "content": (
                    f"Previous Challenge / Prompt: {self.current_prompt}\n"
                    f"User Utterance: {clean_text}\n"
                    "Evaluate the utterance according to your mode and provide response in the required JSON format."
                ),
            })

            try:
                raw_llm = await chat(messages, system_prompt=system_prompt)
                parsed = _extract_json_from_llm_response(raw_llm)
                if parsed and isinstance(parsed, dict):
                    coach_message = parsed.get("coach_message")
                    raw_correction = parsed.get("correction")
                    next_prompt = parsed.get("next_prompt")

                    # Normalize correction boundary (max 1-2 corrections)
                    if isinstance(raw_correction, list):
                        if len(raw_correction) > 0 and isinstance(raw_correction[0], dict):
                            correction = raw_correction[0]
                        else:
                            correction = None
                    elif isinstance(raw_correction, dict) and "original" in raw_correction and "improved" in raw_correction:
                        correction = raw_correction
                    else:
                        correction = None
            except Exception as exc:
                logger.warning(f"Live LLM coach call failed: {exc}. Falling back to mock heuristics.")
                self.telemetry["fallback_used"] = True

        # Fallback to curated mock heuristics if live response wasn't parsed or in mock mode
        if not coach_message or not next_prompt:
            heuristic_res = _evaluate_mock_coach_heuristics(
                mode=self.mode,
                user_text=clean_text,
                current_prompt=self.current_prompt,
                user_profile=self.user_profile,
            )
            coach_message = heuristic_res["coach_message"]
            correction = heuristic_res["correction"]
            next_prompt = heuristic_res["next_prompt"]

        # Track telemetry & corrections
        if correction:
            self.telemetry["corrections_count"] += 1
            self.corrections.append(correction)
        self.telemetry["turns_count"] += 1

        # Record exchange in history
        exchange = {
            "exchange_index": len(self.history),
            "turn": len(self.history) + 1,
            "user_text": clean_text,
            "coach_message": coach_message,
            "correction": correction,
            "next_prompt": next_prompt,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.history.append(exchange)
        self.current_prompt = next_prompt

        return {
            "coach_message": coach_message,
            "correction": correction,
            "next_prompt": next_prompt,
            "user_response_text": clean_text,
        }

    async def end_session(self) -> Dict[str, Any]:
        """Finalizes coach session, compiles summary, updates communication profile, and persists state."""
        self.is_complete = True
        self.completed_at = datetime.now(timezone.utc).isoformat()

        # Compile learning summary
        exchanges_count = len(self.history)
        corrections_observed = [ex["correction"] for ex in self.history if ex.get("correction")]

        key_learnings: List[str] = []
        if self.mode == "english_improvement":
            if any("past tense" in str(c.get("reason", "")).lower() or "went" in str(c.get("improved", "")) or "read" in str(c.get("improved", "")) for c in corrections_observed):
                key_learnings.append("Practiced simple past tense irregular verbs (e.g. 'went', 'read', 'bought').")
            if any("pause" in str(c.get("improved", "")).lower() for c in corrections_observed):
                key_learnings.append("Practiced silent pausing to eliminate conversational filler words.")
            if not key_learnings:
                key_learnings.append("Practiced natural vocabulary and clear conversational cadence.")
        elif self.mode == "answer_training":
            key_learnings.append("Structured interview answers using the STAR method (Situation, Task, Action, Result).")
            key_learnings.append("Highlighted measurable outcomes and direct project contributions.")
        else:
            key_learnings.append("Expanded conversational answers with natural descriptive details.")
            key_learnings.append("Maintained fluent conversational momentum on everyday topics.")

        summary = {
            "exchanges_count": exchanges_count,
            "corrections_count": len(corrections_observed),
            "mode": self.mode,
            "key_learnings": key_learnings,
            "encouragement": "Wonderful job today! Your spoken fluency and communication confidence are noticeably growing.",
        }
        self.summary = summary

        # Profile Learning Progression Update
        if self.user_id:
            try:
                updated_profile_data = await update_user_communication_profile(
                    self.user_id, self.to_dict()
                )
                self.user_profile = updated_profile_data.get("communication_profile", updated_profile_data)
            except Exception as exc:
                logger.warning(f"Failed to update user communication profile: {exc}")

        # Finalize persistence in coach_sessions
        try:
            await save_coach_session(self.session_id, self.to_dict())
        except Exception as exc:
            logger.warning(f"Failed to save completed coach session: {exc}")

        return {
            "session_id": self.session_id,
            "status": "completed",
            "summary": self.summary,
            "updated_profile": self.user_profile,
            "profile_updated": self.user_profile,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serializes session state to a dictionary conforming to Supabase schema."""
        return {
            "id": self.session_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "mode": self.mode,
            "exchanges": self.history,
            "history": self.history,
            "corrections": self.corrections,
            "summary": self.summary,
            "is_complete": self.is_complete,
            "status": "completed" if self.is_complete else "in_progress",
            "current_prompt": self.current_prompt,
            "created_at": self.created_at,
            "started_at": self.created_at,
            "completed_at": self.completed_at,
            "user_profile": self.user_profile,
            "telemetry": self.telemetry,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoachSession":
        """Reconstructs a CoachSession instance from a dictionary or Supabase row."""
        session_id = data.get("id") or data.get("session_id") or str(uuid.uuid4())
        is_complete = data.get("is_complete")
        if is_complete is None and data.get("status") == "completed":
            is_complete = True

        exchanges = data.get("exchanges") or data.get("history") or []
        if not isinstance(exchanges, list):
            exchanges = []

        corrections = data.get("corrections") or []
        if not isinstance(corrections, list):
            corrections = []

        return cls(
            session_id=session_id,
            user_id=data.get("user_id"),
            mode=data.get("mode", "conversation"),
            history=exchanges,
            corrections=corrections,
            user_profile=data.get("user_profile"),
            current_prompt=data.get("current_prompt"),
            is_complete=bool(is_complete),
            summary=data.get("summary"),
            created_at=data.get("created_at") or data.get("started_at"),
            completed_at=data.get("completed_at"),
            telemetry=data.get("telemetry"),
        )
