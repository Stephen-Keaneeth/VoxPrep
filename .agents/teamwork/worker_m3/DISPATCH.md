## 2026-11-05T18:44:35Z
You are `worker_m3`, the Milestone 3 Implementation Worker.
Working directory: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\worker_m3
Project root: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer
Original request: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\PROJECT.md

Read the 3 Explorer blueprints before beginning:
- Explorer 1 (Coach Agent & Prompts): `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m3_1\handoff.md`
- Explorer 2 (Persistence & Profile Learning): `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m3_2\handoff.md`
- Explorer 3 (Router & Test Suite): `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m3_3\handoff.md`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your exclusive write ownership covers:
- `backend/app/agents/coach.py`
- `backend/app/db/coach_persistence.py`
- `backend/app/routers/coach.py`
- `backend/app/main.py` (mounting coach router)
- `backend/schema.sql` (if idempotent column additions are needed)
- `backend/tests/test_coach.py`

Implementation requirements:
1. `backend/app/agents/coach.py`:
   - `CoachSession` class with `session_id`, `user_id`, `mode`, `history`, `corrections`, `user_profile`.
   - Supported modes: `"conversation"`, `"answer_training"`, `"english_improvement"`.
   - `async def start_session(...) -> str`: loads user profile from Supabase, seeds mode system prompt with candidate context, returns warm opening prompt.
   - `async def process_response(user_text: str) -> dict`: processes speech, returns `{"coach_message": str, "correction": {"original": str, "improved": str, "reason": str} | None, "next_prompt": str}`.
   - Strict rules: Max 1–2 corrections per exchange. Warm, supportive, encouraging tone. If speech is clear or has no material issues, `correction` must be `None`.
   - Mode specifics: "conversation" (fluency/cadence), "answer_training" (STAR structure/conciseness/metrics), "english_improvement" (grammar/vocab/filler words).
   - Offline test mode catalog for deterministic tests when NVIDIA API keys are absent.
2. `backend/app/db/coach_persistence.py`:
   - `save_coach_session(session_id: str, data: dict) -> None`
   - `get_coach_session(session_id: str) -> dict | None`
   - `get_user_profile(user_id: str) -> dict`
   - `update_user_communication_profile(user_id: str, session_data: dict) -> dict`
   - Implement profile learning engine with taxonomy classification (filler words, STAR structure, conciseness, grammar, vocabulary, clarity, examples), weak area tracking (capped at 5), graduation to strong areas, and skill level progression (`beginner`, `intermediate`, `advanced`).
   - Dual-write compatibility with `MockSupabaseClient` and production PostgreSQL.
3. `backend/app/routers/coach.py`:
   - `POST /coach/start`: `{user_id, mode}` -> `{session_id, opening_message, mode}`.
   - `POST /coach/respond`: `{session_id, user_text}` -> `{coach_message, correction, next_prompt}`.
   - `POST /coach/end`: `{session_id}` -> `{session_id, status: "completed", summary, profile_updated}`.
   - Return appropriate HTTP errors (400 for invalid mode/empty text, 404 for missing session/user, 422 for missing fields).
4. `backend/app/main.py`:
   - Mount router: `app.include_router(coach.router, prefix="/coach", tags=["coach"])`.
5. `backend/tests/test_coach.py`:
   - Comprehensive test suite covering all 3 modes, clear answers vs answers needing corrections, filler words, STAR coaching, profile learning updates, session persistence, boundary conditions (400, 404, 422), and idempotence.
   - Use `LocalClient` and `run_sync` (do NOT use Starlette TestClient directly to avoid Windows socket hangs).
6. Build and test verification:
   - Run `.\.venv\Scripts\pytest.exe backend/tests/test_coach.py -v`
   - Run `.\.venv\Scripts\pytest.exe backend/tests -v`
   - Verify that 100% of tests pass with 0 failures and 0 regressions.
7. Deliver a 5-component handoff report (Observation, Logic Chain, Caveats, Conclusion, Verification Method) to:
   `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\worker_m3\handoff.md`
8. When complete, send a message to the orchestrator.
