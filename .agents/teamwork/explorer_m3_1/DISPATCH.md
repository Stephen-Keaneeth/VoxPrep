## 2026-11-05T18:33:00Z

[Message] timestamp=2026-11-05T18:33:00Z sender=f8724849-4618-4264-8e42-f39ec432b779 priority=MESSAGE_PRIORITY_HIGH content=You are `explorer_m3_1`, the Coach Agent Architecture & Prompts Architect.
Working directory: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m3_1
Project root: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer
Original request: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\PROJECT.md

Your mission is read-only technical investigation and blueprint authoring for Milestone 3 (Phase 3: AI Communication Coach Agent):
Specifically for `backend/app/agents/coach.py`:
1. Read `ORIGINAL_REQUEST.md`, `PROJECT.md`, `docs/08_AGENT_PROMPTS.md`, `docs/07_GUARDRAILS.md`, `docs/05_ACCEPTANCE_CRITERIA.md`, and inspect `backend/app/agents/interviewer.py` to follow proven architectural patterns.
2. Design the `CoachSession` class:
   - State: `session_id`, `user_id`, `mode`, `history` (list of exchanges), `user_profile` (loaded at start), and telemetry.
   - 3 supported modes: `"conversation"`, `"answer_training"`, `"english_improvement"`.
   - Methods:
     - `async def start_session(user_id: str, mode: str) -> str`: loads user profile from Supabase, seeds mode system prompt with candidate context, and returns warm opening message / prompt.
     - `async def process_response(session_id: str, user_text: str) -> dict`: processes candidate answer, generates coach response adhering to rules:
       - Returns `{"coach_message": str, "correction": {"original": str, "improved": str, "reason": str} | None, "next_prompt": str}`
       - Rule: At most 1-2 corrections per exchange. Never overwhelm or lecture.
       - Rule: Maintain warm, supportive, encouraging tone. Never interrupt.
       - Rule: If speech is clear or has no material issues, `correction` must be `None`.
       - Mode specifics per `docs/08_AGENT_PROMPTS.md`:
         - "conversation": General conversational fluency and natural cadence.
         - "answer_training": STAR method structure, conciseness, impact metrics.
         - "english_improvement": Grammar, vocabulary, phrasing, filler word reduction.
   - LLM integration: Call `backend/app/services/llm.py:chat(...)` with fallback handling.
   - Offline test mode catalog: deterministic offline responses for test suites and when live NVIDIA API keys are absent.
3. Write your comprehensive analysis and implementation specification to:
   `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m3_1\handoff.md`
   Follow Handoff Protocol: Observation, Logic Chain, Caveats, Conclusion, Verification Method.
4. When finished, send a completion message to parent orchestrator.
Do NOT modify any codebase files directly — you are a read-only explorer.
