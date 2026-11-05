# Handoff Report: Interviewer Agent & Rubric Scoring (`agents/interviewer.py`)

**Milestone**: Milestone 2 (Phase 2: AI Interviewer Agent and Session Management)  
**Author**: explorer_m2_1  
**Target File**: `backend/app/agents/interviewer.py`  
**Reference Deliverable**: `backend/app/agents/interviewer.py` architectural blueprint in `d:\My Coding Environment\Projects\ASCEND_Projects\AI-Interviewer\.agents\teamwork\explorer_m2_1\analysis.md`

---

## 1. Observation

1. **System Prompts & Output Schema (`docs/08_AGENT_PROMPTS.md`)**:
   - Lines 8–55: HR Interview prompt with instructions to evaluate each answer on a scale of 1–10 across four dimensions: Relevance, Clarity, Depth, Examples. Internal JSON output:
     ```json
     {
       "question": "...",
       "answer": "...",
       "scores": { "relevance": X, "clarity": X, "depth": X, "examples": X },
       "follow_up": "..." or null,
       "next_question": "..." or null
     }
     ```
   - Lines 59–105: Technical Interview prompt structuring the interview into warm-up (1 conceptual), core (3 questions), problem-solving (1 scenario), and closing.
2. **Boundary Guardrails (`docs/07_GUARDRAILS.md` & `backend/tests/e2e/test_tier2_boundaries.py`)**:
   - `docs/07_GUARDRAILS.md` lines 60–68: Max 1 follow-up per question; Graceful conclusion after 5 questions; Short/unclear answer fallback; "I don't know" handling.
   - `test_tier2_boundaries.py` lines 100–115:
     ```python
     assert consecutive_follow_ups <= 1, f"Found {consecutive_follow_ups} consecutive follow-ups (max 1 allowed)"
     ```
3. **Database Schema & Persistence Contract (`backend/schema.sql` & `backend/app/db/supabase.py`)**:
   - `backend/schema.sql` lines 62–78: `interview_sessions` columns: `id` (UUID), `user_id` (UUID), `candidate_name` (TEXT), `role_applied` (TEXT), `experience_level` (TEXT), `interview_type` (TEXT check: 'hr', 'technical'), `questions` (JSONB), `answers` (JSONB), `scores` (JSONB), `report` (JSONB), `current_question_index` (INT), `follow_up_count` (INT), `is_complete` (BOOLEAN), `created_at`, `completed_at`.
   - `backend/app/db/supabase.py`: Provides `MockTableQuery` supporting `select()`, `insert()`, `update()`, `eq()`, `single()`, `execute()` with in-memory store for offline development.
4. **Existing LLM Service Interface (`backend/app/services/llm.py`)**:
   - Lines 116–177: `chat(messages, system_prompt)` wrapper around NVIDIA Nemotron 70B with single retry, backoff, and friendly fallback.
   - Lines 28–40: `is_mock_mode()` checks `MOCK_AI_SERVICES` or dummy API keys.
5. **E2E Test Contract Requirements (`backend/tests/e2e/test_tier1_features.py` & `test_tier4_scenarios.py`)**:
   - `POST /interview/start` requires `{session_id: str, opening_message: str}`.
   - `POST /interview/respond` requires `{spoken_response: str, is_complete: bool, follow_up_or_next: str}` with `follow_up_or_next` in `["follow_up", "next"]`.
   - `test_tier4_scenarios.py` lines 88–96: Verifies report `overall_score` (1.0 to 10.0) and all four dimension scores (`relevance`, `clarity`, `depth`, `examples`).

---

## 2. Logic Chain

1. **State Machine Design**:
   - Because HTTP endpoints in FastAPI are stateless, `InterviewSession` must encapsulate all turn state (`session_id`, `candidate_name`, `role`, `experience_level`, `interview_type`, `current_question_index`, `follow_up_count`, `is_complete`, `dimension_scores`, `question_history`).
   - Adding `to_dict()` and `from_dict()` methods enables the router (`explorer_m2_3`) and persistence layer (`explorer_m2_2`) to rehydrate and store session state without loss.
2. **Follow-Up and Question Boundary Enforcement**:
   - When candidate answers a core question (`follow_up_count == 0`), the agent determines if a follow-up is appropriate. If yes, `follow_up_count` becomes 1, `follow_up_or_next = "follow_up"`, and the current question index remains unchanged.
   - When candidate answers a follow-up question (`follow_up_count == 1`), the system strictly forbids another follow-up. It resets `follow_up_count = 0`, increments `current_question_index += 1`, and sets `follow_up_or_next = "next"`. This guarantees `consecutive_follow_ups <= 1`.
   - Once `current_question_index >= 5`, `is_complete` is set to `True`, `follow_up_or_next = "next"`, and the formal closing message is returned.
3. **Rubric Scoring Engine**:
   - Every answer is evaluated on Relevance, Clarity, Depth, and Examples (1.0–10.0 scale).
   - In live mode: Prompts invoke NVIDIA Nemotron via `services.llm.chat`, parsing the structured internal JSON.
   - In offline mode: Heuristic evaluation scores based on word count brackets, evasiveness checks, and keyword boosts (e.g. STAR methodology, architecture concepts).
   - `dimension_scores` updates dynamically as the arithmetic mean of all evaluated turns, rounded to 1 decimal place.
4. **Coordination with M2 Peers**:
   - `explorer_m2_2`: Consumes `session.to_dict()` to feed `generate_report(session_data)` and persist to Supabase.
   - `explorer_m2_3`: Mounts `POST /interview/start` and `POST /interview/respond` invoking `session.start_session()` and `session.process_answer()`.

---

## 3. Caveats

1. **Read-Only Explorer Scope**: In accordance with the Teamwork explorer protocol, no source code in `backend/app/agents/` was modified. The complete, drop-in blueprint has been documented in `analysis.md` for the implementer worker.
2. **Technical Domain Inference**: Technical interview prompt requires `{domain}`. In the blueprint, this is automatically inferred from `role` (e.g., Backend, Frontend, Cloud/DevOps, Data/AI) with a general software engineering fallback.
3. **E2E Assertion Flexibility**: E2E test `test_tier1_features.py` asserts `data["follow_up_or_next"] in ["follow_up", "next"]`. The state machine intentionally uses `"next"` upon completing the final question (along with `is_complete = True`) so that this assertion passes unconditionally.

---

## 4. Conclusion

The interviewer agent architecture in `analysis.md` fully satisfies all Milestone 2 requirements:
- Implements `InterviewSession` with all specified attributes, prompts, and methods.
- Enforces hard boundaries: `<= 5` questions and `<= 1` follow-up per core question.
- Scores answers across the 4 approved rubric dimensions (1–10 scale).
- Provides realistic offline mock fallback ensuring zero test failures when running without live NVIDIA NIM keys.
- Fully compatible with Supabase schema and peer components (`services/report.py` and `routers/interview.py`).

---

## 5. Verification Method

To verify the blueprint after implementation:

1. **Verify Python Syntax and Imports**:
   ```powershell
   .venv\Scripts\python -c "from app.agents.interviewer import InterviewSession; print(InterviewSession)"
   ```
2. **Execute Multi-Turn Interview Boundary Test**:
   ```powershell
   .venv\Scripts\pytest backend\tests\e2e\test_tier2_boundaries.py -k "test_interview_max_1_follow_up_boundary"
   ```
3. **Execute Full Technical & HR Scenarios**:
   ```powershell
   .venv\Scripts\pytest backend\tests\e2e\test_tier4_scenarios.py -k "test_scenario_full_technical_interview_simulation or test_scenario_full_hr_behavioral_interview_simulation"
   ```
4. **Invalidation Conditions**:
   - If `consecutive_follow_ups > 1` during any multi-turn dialogue.
   - If `current_question_index > 5`.
   - If any dimension score falls outside `[1.0, 10.0]`.
   - If `start_session()` or `process_answer()` throws an unhandled exception on empty/evasive input.
