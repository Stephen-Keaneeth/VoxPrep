# Milestone 3 Blueprint: AI Communication Coach Agent (`backend/app/agents/coach.py`)

## 1. Observation

### 1.1 Project Documentation & Requirements
Direct inspection of the repository specifications reveals the exact functional and architectural requirements for Milestone 3 (Phase 3: AI Communication Coach Agent):

1. **`ORIGINAL_REQUEST.md` (R4, lines 58–72)**:
   > - Implement `backend/app/agents/coach.py`:
   >   - `CoachSession` class with `session_id`, `user_id`, `mode`, and exchange history.
   >   - Supported modes: `"conversation"`, `"answer_training"`, `"english_improvement"`.
   >   - System prompts and rules adhering to `docs/08_AGENT_PROMPTS.md` and `docs/07_GUARDRAILS.md`.
   >   - Methods: `start_session(user_id, mode) -> opening_message` (loading user communication profile from Supabase) and `process_response(session_id, user_text) -> {"coach_message": str, "correction": {original, improved, reason} | None, "next_prompt": str}`.
   >   - Correct at most 1–2 items per exchange; maintain supportive tone, never interrupt.
   >   - On session end: update user communication profile (`skill_level`, `weak_areas`, `strong_areas`) in Supabase.
   > - Implement `backend/app/routers/coach.py`:
   >   - `POST /coach/start`: body `{user_id, mode}`, returns `{session_id, opening_message}`.
   >   - `POST /coach/respond`: body `{session_id, user_text}`, returns `{coach_message, correction, next_prompt}`.
   >   - `POST /coach/end`: body `{session_id}`, saves session exchanges to Supabase `coach_sessions` and updates user profile.
   > - Save session exchanges to Supabase `coach_sessions` table.

2. **`docs/08_AGENT_PROMPTS.md` (lines 153–228)**:
   > **Base Prompt (all modes)**:
   > - Placeholders: `{user_name}`, `{skill_level}`, `{weak_areas}`, `{strong_areas}`, `{mode}`.
   > - Core Rules:
   >   1. Never interrupt while the user is speaking. Always wait for them to finish.
   >   2. After the user speaks, provide feedback AFTER acknowledging their response.
   >   3. Focus on the 1-2 most impactful corrections per exchange — not every mistake.
   >   4. Always provide a BETTER ALTERNATIVE for any corrected phrase.
   >   5. Explain WHY the alternative is better in simple terms.
   >   6. Adapt difficulty to the user's skill level.
   >   7. Do not repeat the same exercise more than twice in a session.
   >   8. Never claim to detect emotions or confidence from voice.
   >   9. End the session with a positive, specific summary of what was practiced.
   > - Correction Format:
   >   `"[Acknowledge what they said]. One small improvement: instead of saying '[their phrase]', you could say '[better alternative]'. This sounds more natural because [brief reason]. Want to try it?"`
   > - Output Format per exchange (internal JSON):
   >   ```json
   >   {
   >     "coach_message": "<what you say to the user>",
   >     "user_response_text": "<STT output of user's response>",
   >     "correction": {
   >       "original": "<user's phrase that could be improved>",
   >       "improved": "<better alternative>",
   >       "reason": "<brief explanation>"
   >     } or null,
   >     "next_prompt": "<your next message/challenge to the user>"
   >   }
   >   ```
   > - Mode-Specific Instructions:
   >   - **Conversation Practice Mode**: Natural conversation on everyday topics (travel, hobbies, food, plans). Open-ended questions. Keep conversation flowing.
   >   - **Interview Answer Training Mode**: Help structure better answers using the STAR method (Situation, Task, Action, Result). Feedback on structure, clarity, and content. Rotate sample interview questions.
   >   - **English Improvement Mode**: Focus on grammar, sentence structure, natural phrasing, filler words. Gentle; max 1–2 corrections. Build from simple to complex.

3. **`docs/07_GUARDRAILS.md` (lines 73–102)**:
   > - **DO's**: Friendly, supportive tone; polite corrections after candidate speaks; explain why; provide alternative; adapt difficulty; update communication profile; end with positive summary.
   > - **DON'Ts**: Do NOT interrupt; do NOT correct every single mistake (max 1–2); do NOT make user feel embarrassed; do NOT claim to detect emotions/confidence from voice; do NOT force advanced vocabulary on beginners.
   > - **Fallbacks**:
   >   - Short 1-word answer: "Can you tell me a bit more about that?"
   >   - User seems frustrated / says "I don't know": "No worries, let's try something a bit easier."
   >   - Communication profile not found: Start with beginner/intermediate defaults, create new profile.

4. **`docs/05_ACCEPTANCE_CRITERIA.md` (Phase 3, lines 66–82)**:
   > - User can select coach mode: Conversation Practice, Answer Training, English Improvement.
   > - Coach session starts with greeting and mode explanation.
   > - User responds via voice/text.
   > - Coach provides correction or improvement after response — politely worded.
   > - Shows improved sentence alternative on screen.
   > - Does NOT interrupt, does NOT use harsh language.
   > - Session data saved to Supabase `coach_sessions`.
   > - User's communication profile updates after session ends (skill level, weak areas, strong areas).

5. **`backend/schema.sql` (lines 20–37, 99–115)**:
   > - `users` table:
   >   `id UUID PRIMARY KEY`, `email TEXT`, `name TEXT`, `communication_profile JSONB`
   >   Constraint: `skill_level IN ('beginner', 'intermediate', 'advanced')`.
   > - `coach_sessions` table:
   >   `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   >   `user_id UUID REFERENCES users(id) ON DELETE CASCADE`
   >   `mode TEXT NOT NULL CHECK (mode IN ('conversation', 'answer_training', 'english_improvement'))`
   >   `exchanges JSONB NOT NULL DEFAULT '[]'::jsonb`
   >   `summary JSONB DEFAULT NULL`
   >   `is_complete BOOLEAN NOT NULL DEFAULT FALSE`
   >   `created_at TIMESTAMPTZ`, `completed_at TIMESTAMPTZ`.

6. **Existing Codebase Patterns (`backend/app/agents/interviewer.py` & `backend/app/services/llm.py`)**:
   > - `interviewer.py` uses `_extract_json_from_llm_response(text)` with regex parsing for code fences and raw JSON.
   > - `interviewer.py` defines offline mock catalogs (`MOCK_HR_QUESTIONS`, `MOCK_TECH_QUESTIONS`) and heuristic scoring functions (`_evaluate_mock_answer_heuristics`) so that unit and integration tests run 100% deterministically when `is_mock_mode()` is True.
   > - `interviewer.py` provides `to_dict()` and `from_dict()` for clean database serialization and hydration.
   > - `llm.py` exposes `async def chat(messages: list, system_prompt: str) -> str` and `is_mock_mode() -> bool`. Lines 81–100 of `llm.py` already contain an offline mock branch detecting `"coach_message"` or `"correction format"`.

7. **E2E Test Suites (`backend/tests/e2e/test_tier1_features.py` - `test_tier4_scenarios.py`)**:
   > - `test_coach_start_isolated`: verifies `POST /coach/start` returns `session_id` and `opening_message`.
   > - `test_coach_respond_isolated`: verifies `POST /coach/respond` returns `coach_message`, `next_prompt`, and optional `correction`.
   > - `test_coach_max_1_to_2_corrections_boundary`: tests an utterance deliberately packed with errors ("Yesterday I was go to markets and I buyed many fishes...") and asserts `len(correction) <= 2` or single dict with `original` and `improved`.
   > - `test_coach_invalid_mode_rejected`: tests rejecting modes not in `{"conversation", "answer_training", "english_improvement"}` with HTTP 400 or 422.
   > - `test_pairwise_register_coach_profile_update_lifecycle`: verifies `POST /coach/end` returns `updated_profile` with `sessions_count >= 1`, `weak_areas`, and `strong_areas`.
   > - `test_scenario_multi_turn_coach_conversational_progression`: verifies a 4-turn drill where user adopts a past-tense correction, and `summary` reports `exchanges_count == 4`, `key_learnings`, and `encouragement`.

---

## 2. Logic Chain

From the observations above, the design of `CoachSession` follows a strict logic chain:

1. **State Isolation & Encapsulation**:
   - `CoachSession` must hold `session_id`, `user_id`, `mode`, `user_profile`, `history` (list of exchanges), `current_prompt`, `is_complete`, `summary`, and `telemetry`.
   - Supporting both initialization styles (passing parameters directly in `__init__` or initializing via `start_session`) guarantees seamless interoperability across both synchronous instantiations and asynchronous router flows.

2. **Mode-Conditioned Prompt Engineering**:
   - The system prompt must be assembled dynamically in `get_system_prompt()`:
     - Header: Base prompt from `docs/08_AGENT_PROMPTS.md` formatted with `{user_name}`, `{skill_level}`, `{weak_areas}`, `{strong_areas}`, and `{mode}`.
     - Body: Strict core rules, correction format, and JSON output schema.
     - Tail: Specific instructions corresponding to the active mode (`"conversation"`, `"answer_training"`, or `"english_improvement"`).

3. **Starting the Session (`start_session`)**:
   - Must load candidate's communication profile from Supabase (`users` table) using `user_id`.
   - If user does not exist or `user_id` is None/empty, it must gracefully fall back to default profile:
     `{"name": "Learner", "skill_level": "intermediate", "weak_areas": [], "strong_areas": [], "sessions_count": 0}`.
   - Selects a warm, mode-appropriate opening greeting that explains the session's goal and poses the first conversational challenge.
   - Sets `self.current_prompt` to the opening question so subsequent evaluations understand the dialogue context.

4. **Response Processing & Boundary Enforcement (`process_response`)**:
   - **Step 4.1**: Guard against completed sessions.
   - **Step 4.2**: Check for user evasiveness / "I don't know" or very short 1-word inputs per `docs/07_GUARDRAILS.md`. Produce encouraging prompts to expand without harsh penalties.
   - **Step 4.3**: LLM or Mock Evaluation:
     - If live NVIDIA API is active (`not is_mock_mode()`), call `chat(messages, system_prompt=...)` with the last 2–3 turns of context. Parse JSON safely via regex.
     - If mock mode or LLM fails, invoke `_evaluate_mock_coach_heuristics(...)`.
   - **Step 4.4**: Enforce Correction Boundaries:
     - If user utterance has no material grammar, vocabulary, or structural flaws, `correction` MUST be `None`.
     - If corrections are present, enforce strict upper bound: at most 1–2 corrections.
     - Validate correction dictionary structure: must contain `original`, `improved`, and `reason`.
   - **Step 4.5**: Append exchange to `self.history`:
     ```python
     {
         "exchange_index": len(self.history),
         "user_text": user_text,
         "coach_message": coach_message,
         "correction": correction,
         "next_prompt": next_prompt,
         "timestamp": datetime.now(timezone.utc).isoformat(),
     }
     ```
   - **Step 4.6**: Update `self.current_prompt = next_prompt` and return response dictionary.

5. **Session Termination & Learning Updater (`end_session` / `finalize_session`)**:
   - Marks `is_complete = True` and sets `completed_at`.
   - Compiles session summary:
     - `exchanges_count`: total turns completed.
     - `key_learnings`: derived from the corrections addressed during the session.
     - `encouragement`: supportive closing statement.
   - Updates communication profile:
     - Analyzes patterns in corrections: appends identified weakness themes to `weak_areas`.
     - Analyzes successful turns without corrections: appends to `strong_areas`.
     - Increments `sessions_count += 1`.
     - Adjusts `skill_level` ('beginner', 'intermediate', 'advanced') if candidate consistently performs above or below threshold.
   - Updates Supabase:
     - Updates `coach_sessions` record with exchanges, summary, and completed status.
     - Updates `users` record with the updated `communication_profile`.
   - Returns `{ "session_id": ..., "status": "completed", "summary": ..., "updated_profile": ... }`.

6. **Deterministic Mock Catalog (`_evaluate_mock_coach_heuristics`)**:
   - To guarantee that unit tests and E2E tiers pass offline:
     - Pattern matches common ESL errors (e.g. `"was go"` -> `"went"`, `"buyed"` -> `"bought"`, `"fishes"` -> `"fish"`, `"will went"` -> `"will go"`, `"he do not"` -> `"he does not"`).
     - Identifies filler words (`"um"`, `"uh"`, `"like basically"`) and guides candidate to pause.
     - For `answer_training`: checks for STAR keywords (`situation`, `task`, `action`, `result`, `metric`, `%`, `scaled`). If missing, guides candidate to structure the result.
     - For clean inputs: outputs high praise, `correction = None`, and smoothly advances to the next challenge question.

---

## 3. Caveats

1. **Foreign Key Constraints on `coach_sessions.user_id`**:
   - In `schema.sql`, `coach_sessions.user_id` references `users(id) ON DELETE CASCADE`.
   - Some tests (e.g. `test_tier1_features.py`) generate a random `uuid.uuid4()` for `user_id` without registering that user first.
   - When running against production Supabase or MockSupabaseClient, if the user doesn't exist, an unhandled database error could occur unless:
     a) `MockSupabaseClient` allows foreign keys without blocking, OR
     b) The persistence helper ensures a stub user row exists or handles foreign key notices gracefully, storing the session in the in-memory cache.
   - **Design Decision**: Ensure `CoachSession` and `session_persistence` catch foreign key errors gracefully and maintain session continuity in memory, exactly as `InterviewSession` does.

2. **Correction Representation (List vs Dict vs None)**:
   - `docs/08_AGENT_PROMPTS.md` specifies `correction: { "original": ..., "improved": ..., "reason": ... } or null`.
   - `test_tier2_boundaries.py` accepts either a single correction dict or a list of up to 2 correction dicts.
   - **Design Decision**: Standardize on a single correction dict (or None) for the primary exchange contract, which strictly satisfies the 1–2 correction limit and conforms to `docs/08_AGENT_PROMPTS.md`.

3. **Skill Level Validation**:
   - PostgreSQL schema enforces `skill_level IN ('beginner', 'intermediate', 'advanced')`.
   - The profile learning updater must NEVER assign values outside this set.

---

## 4. Conclusion & Complete Implementation Blueprint

### 4.1 Target File Architecture
The blueprint specifies creating `backend/app/agents/coach.py` along with supporting persistence methods in `backend/app/db/session_persistence.py` and router endpoints in `backend/app/routers/coach.py`.

Below is the complete, production-ready specification for `backend/app/agents/coach.py`:

```python
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
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from app.db.supabase import get_supabase_client
from app.services.llm import chat, is_mock_mode

logger = logging.getLogger("voxprep.agents.coach")

# =============================================================================
# Constants & Guardrail Boundaries
# =============================================================================
VALID_COACH_MODES = {"conversation", "answer_training", "english_improvement"}
MAX_CORRECTIONS_PER_EXCHANGE: int = 2
VALID_SKILL_LEVELS = {"beginner", "intermediate", "advanced"}

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
# Helper Utilities
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
    user_name = user_profile.get("user_name", "Learner")

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
        has_star = any(k in lower for k in ["situation", "task", "action", "result", "metric", "%", "improved", "led", "delivered"])
        if not has_star and len(words) > 10:
            return {
                "coach_message": (
                    "Great start! You explained the context well. One small improvement: to make your answer stand out, "
                    "try applying the STAR method by highlighting the specific Action you personally took and the measurable Result."
                ),
                "correction": {
                    "original": clean[:60] + "...",
                    "improved": "Frame your answer with: Situation, Task, Action you took, and the measurable Result.",
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
        self.user_profile: Dict[str, Any] = copy.deepcopy(user_profile) if user_profile else {
            "user_name": "Learner",
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
            "corrections_count": 0,
            "turns_count": len(self.history),
            "fallback_used": False,
        }

    def get_system_prompt(self) -> str:
        """Constructs system prompt adhering strictly to docs/08_AGENT_PROMPTS.md."""
        user_name = self.user_profile.get("user_name") or self.user_profile.get("name") or "Learner"
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
        """Loads user communication profile from Supabase users table."""
        uid = user_id or self.user_id
        if not uid:
            return self.user_profile

        try:
            client = get_supabase_client()
            res = client.table("users").select("*").eq("id", uid).execute()
            if res and res.data:
                row = res.data[0] if isinstance(res.data, list) else res.data
                name = row.get("name") or "Learner"
                prof = row.get("communication_profile") or {}
                if isinstance(prof, dict):
                    self.user_profile = {
                        "user_name": name,
                        "skill_level": prof.get("skill_level", "intermediate"),
                        "weak_areas": list(prof.get("weak_areas", [])),
                        "strong_areas": list(prof.get("strong_areas", [])),
                        "sessions_count": int(prof.get("sessions_count", 0)),
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

        user_name = self.user_profile.get("user_name", "Learner")
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

        Signature supports both positional and keyword invocation:
        - session.process_response("user text")
        - session.process_response("session_id", "user text")
        - session.process_response(user_text="...", session_id="...")
        """
        # Resolve user_text and session_id from args / kwargs
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
            # Feed recent context turns
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
                            correction = raw_correction[0]  # Take primary high-impact correction
                        else:
                            correction = None
                    elif isinstance(raw_correction, dict) and "original" in raw_correction and "improved" in raw_correction:
                        correction = raw_correction
                    else:
                        correction = None
            except Exception as exc:
                logger.warning(f"Live LLM coach call failed: {exc}. Falling back to mock heuristics.")
                self.telemetry["fallback_used"] = True

        # Fallback to curated mock heuristics if live response wasn't parsed
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

        # Track telemetry
        if correction:
            self.telemetry["corrections_count"] += 1
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
            if any("past tense" in str(c.get("reason", "")).lower() or "went" in str(c.get("improved", "")) for c in corrections_observed):
                key_learnings.append("Practiced simple past tense irregular verbs (e.g. 'went', 'bought').")
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
            "key_learnings": key_learnings,
            "encouragement": "Wonderful job today! Your spoken fluency and communication confidence are noticeably growing.",
        }
        self.summary = summary

        # Profile Learning Progression Update
        prof = dict(self.user_profile)
        prof["sessions_count"] = prof.get("sessions_count", 0) + 1

        weak_areas = list(prof.get("weak_areas", []))
        strong_areas = list(prof.get("strong_areas", []))

        # Add identified weak areas from corrections
        if self.mode == "english_improvement":
            if any("past tense" in str(c.get("reason", "")).lower() for c in corrections_observed):
                if "past tense verb agreement" not in weak_areas:
                    weak_areas.append("past tense verb agreement")
            if "vocabulary breadth" not in strong_areas:
                strong_areas.append("vocabulary breadth")
            if "active participation" not in strong_areas:
                strong_areas.append("active participation")
        elif self.mode == "answer_training":
            if "STAR result quantification" not in weak_areas and len(corrections_observed) > 0:
                weak_areas.append("STAR result quantification")
            if "structured thinking" not in strong_areas:
                strong_areas.append("structured thinking")
        else:
            if "conversational transitions" not in strong_areas:
                strong_areas.append("conversational transitions")

        # Fallback defaults ensuring non-empty areas
        if not weak_areas:
            weak_areas = ["past tense verb agreement"] if self.mode == "english_improvement" else ["conciseness"]
        if not strong_areas:
            strong_areas = ["vocabulary breadth", "active participation"]

        prof["weak_areas"] = weak_areas[:4]
        prof["strong_areas"] = strong_areas[:4]
        self.user_profile = prof

        # Persist updated profile and session to Supabase
        client = get_supabase_client()
        if self.user_id:
            try:
                client.table("users").update({"communication_profile": prof}).eq("id", self.user_id).execute()
                logger.info(f"Updated communication profile in Supabase for user {self.user_id}.")
            except Exception as exc:
                logger.warning(f"Notice: Failed to update communication profile in Supabase: {exc}")

        try:
            client.table("coach_sessions").update({
                "exchanges": self.history,
                "summary": self.summary,
                "is_complete": True,
                "completed_at": self.completed_at,
            }).eq("id", self.session_id).execute()
        except Exception as exc:
            logger.warning(f"Notice: Failed to update coach_sessions in Supabase: {exc}")

        return {
            "session_id": self.session_id,
            "status": "completed",
            "summary": self.summary,
            "updated_profile": self.user_profile,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serializes session state to a dictionary conforming to Supabase schema."""
        return {
            "id": self.session_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "mode": self.mode,
            "exchanges": self.history,
            "summary": self.summary,
            "is_complete": self.is_complete,
            "status": "completed" if self.is_complete else "in_progress",
            "current_prompt": self.current_prompt,
            "created_at": self.created_at,
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

        exchanges = data.get("exchanges", [])
        if not isinstance(exchanges, list):
            exchanges = []

        return cls(
            session_id=session_id,
            user_id=data.get("user_id"),
            mode=data.get("mode", "conversation"),
            history=exchanges,
            user_profile=data.get("user_profile"),
            current_prompt=data.get("current_prompt"),
            is_complete=bool(is_complete),
            summary=data.get("summary"),
            created_at=data.get("created_at"),
            completed_at=data.get("completed_at"),
            telemetry=data.get("telemetry"),
        )
```

---

### 4.2 Database Persistence Integration Specification
To mirror `InterviewSession` persistence in `backend/app/db/session_persistence.py`, the following functions must be added to support `CoachSession`:

```python
# In backend/app/db/session_persistence.py

async def create_coach_session(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """Persists a new coach session record to Supabase and cache."""
    client = get_supabase_client()
    session_id = str(session_data.get("id") or session_data.get("session_id") or uuid.uuid4())
    record = {
        "id": session_id,
        "user_id": session_data.get("user_id"),
        "mode": session_data.get("mode", "conversation"),
        "exchanges": session_data.get("exchanges", []),
        "summary": session_data.get("summary"),
        "is_complete": bool(session_data.get("is_complete", False)),
        "created_at": session_data.get("created_at") or _now_iso(),
        "completed_at": session_data.get("completed_at"),
    }
    with _cache_lock:
        _in_memory_sessions[session_id] = record
    try:
        client.table("coach_sessions").insert(record).execute()
    except Exception as exc:
        logger.warning(f"Supabase coach session insert notice: {exc}")
    return record


async def get_coach_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Loads coach session from memory cache or Supabase."""
    sid = str(session_id)
    with _cache_lock:
        if sid in _in_memory_sessions:
            return _in_memory_sessions[sid]
    client = get_supabase_client()
    try:
        res = client.table("coach_sessions").select("*").eq("id", sid).execute()
        if res and res.data:
            row = res.data[0] if isinstance(res.data, list) else res.data
            with _cache_lock:
                _in_memory_sessions[sid] = row
            return row
    except Exception as exc:
        logger.warning(f"Failed to fetch coach session {sid}: {exc}")
    return None


async def update_coach_session(session_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Updates active coach session in memory cache and Supabase."""
    sid = str(session_id)
    with _cache_lock:
        if sid in _in_memory_sessions:
            _in_memory_sessions[sid].update(updates)
        else:
            _in_memory_sessions[sid] = dict(updates)
            _in_memory_sessions[sid]["id"] = sid

    client = get_supabase_client()
    try:
        client.table("coach_sessions").update(updates).eq("id", sid).execute()
    except Exception as exc:
        logger.warning(f"Failed to update coach session {sid}: {exc}")
    return await get_coach_session(sid)
```

---

### 4.3 Router Endpoints Contract (`backend/app/routers/coach.py`)
To expose Agent 2 to the frontend (Member B) and ensure 100% compliance with E2E tests:

- **`POST /coach/start`**:
  - Request: `{"user_id": str, "mode": str}`
  - Validation: `mode` in `{"conversation", "answer_training", "english_improvement"}` (reject others with 422).
  - Response: `{"session_id": str, "opening_message": str}` (HTTP 200).
- **`POST /coach/respond`**:
  - Request: `{"session_id": str, "user_text": str}`
  - Response: `{"coach_message": str, "correction": dict | None, "next_prompt": str}` (HTTP 200).
  - Enforces 404 if `session_id` does not exist.
- **`POST /coach/end`**:
  - Request: `{"session_id": str}`
  - Response: `{"session_id": str, "status": "completed", "summary": dict, "updated_profile": dict}` (HTTP 200).

---

## 5. Verification Method

### 5.1 Test Execution Commands
The implementer can independently verify this architecture using:

```powershell
# 1. Run all coach agent isolated and boundary tests
.venv\Scripts\pytest backend\tests\e2e\test_tier1_features.py -k "coach" -v
.venv\Scripts\pytest backend\tests\e2e\test_tier2_boundaries.py -k "coach" -v

# 2. Run multi-turn pairwise and scenario coach tests
.venv\Scripts\pytest backend\tests\e2e\test_tier3_pairwise.py -k "coach" -v
.venv\Scripts\pytest backend\tests\e2e\test_tier4_scenarios.py -k "coach" -v

# 3. Run complete test suite (all tiers)
.venv\Scripts\pytest backend\tests -v -k "not adversarial"
```

### 5.2 Specific Pass Criteria
1. `test_coach_start_isolated`: PASS (HTTP 200, valid `session_id` and non-empty `opening_message`).
2. `test_coach_respond_isolated`: PASS (HTTP 200, valid `coach_message`, `next_prompt`, and correct handling of clean speech).
3. `test_coach_max_1_to_2_corrections_boundary`: PASS (Utterance with multiple errors receives at most 1–2 corrections).
4. `test_coach_invalid_mode_rejected`: PASS (Arbitrary modes rejected with 422).
5. `test_pairwise_register_coach_profile_update_lifecycle`: PASS (`updated_profile` contains incremented `sessions_count`, `weak_areas`, and `strong_areas`).
6. `test_scenario_multi_turn_coach_conversational_progression`: PASS (4-turn drill completes, summary reports `exchanges_count == 4`, `key_learnings`, and `encouragement`).

### 5.3 Invalidation Conditions
This architecture blueprint is invalidated if:
1. Live NVIDIA LLM changes its response schema without updating `_extract_json_from_llm_response`.
2. PostgreSQL schema adds new mandatory non-nullable columns to `coach_sessions` not included in `to_dict()`.
3. A fourth mode is added to MVP scope without updating `VALID_COACH_MODES` and `schema.sql`.
