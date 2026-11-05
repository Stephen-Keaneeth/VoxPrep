## 2026-11-05T18:33:00Z
You are `explorer_m3_3`, the Coach Router & Test Suite Architect.
Working directory: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m3_3
Project root: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer
Original request: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\ORIGINAL_REQUEST.md
Project plan: d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\PROJECT.md

Your mission is read-only technical investigation and blueprint authoring for Milestone 3 (Phase 3: AI Communication Coach Agent):
Specifically for the API Router and Comprehensive Test Suite:
1. Read `ORIGINAL_REQUEST.md`, `PROJECT.md`, `backend/app/routers/interview.py`, `backend/app/main.py`, and `backend/tests/test_interview.py`.
2. Design `backend/app/routers/coach.py`:
   - Endpoint: `POST /coach/start`:
     - Request body: `{ "user_id": str, "mode": str }` (modes: "conversation", "answer_training", "english_improvement").
     - Response: `{ "session_id": str, "opening_message": str, "mode": str }`.
   - Endpoint: `POST /coach/respond`:
     - Request body: `{ "session_id": str, "user_text": str }`.
     - Response: `{ "coach_message": str, "correction": { "original": str, "improved": str, "reason": str } | None, "next_prompt": str }`.
   - Endpoint: `POST /coach/end`:
     - Request body: `{ "session_id": str }`.
     - Response: `{ "session_id": str, "status": "completed", "summary": dict, "profile_updated": dict }`.
   - Mounting in `backend/app/main.py`: `app.include_router(coach.router, prefix="/coach", tags=["coach"])`.
   - Error handling: HTTP 400 for invalid mode/empty user_text, HTTP 404 for missing session/user.
3. Design test suite for `backend/tests/test_coach.py`:
   - Test start session across all 3 modes ("conversation", "answer_training", "english_improvement").
   - Test respond with clear answer (correction=None) and answer needing correction (structured dict with original, improved, reason).
   - Test end session persisting to `coach_sessions` and updating user profile (`skill_level`, `weak_areas`, `strong_areas`).
   - Test boundary & error conditions: invalid mode, missing session, empty text, idempotent end session.
   - Integration with existing test harness (use `LocalClient` and `run_sync` to prevent Windows socket hangs).
4. Write your comprehensive analysis and blueprint to:
   `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m3_3\handoff.md`
   Follow Handoff Protocol: Observation, Logic Chain, Caveats, Conclusion, Verification Method.
5. When finished, send a completion message to parent orchestrator.
Do NOT modify any codebase files directly — you are a read-only explorer.
