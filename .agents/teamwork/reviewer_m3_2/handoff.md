# Milestone 3 Architecture & Persistence Review Report

**Agent**: `reviewer_m3_2`  
**Verdict**: **APPROVE**  
**Timestamp**: 2026-11-05T22:16:00Z  

---

## 1. Observation

1. **Target Source & Schema Files**:
   - `backend/app/db/coach_persistence.py` (577 lines):
     * Implements `save_coach_session` and `get_coach_session` with bidirectional field aliasing (`exchanges` <-> `history`, `is_complete` <-> `status`, `created_at` <-> `started_at`).
     * Implements `get_user_profile` with automatic baseline profile provisioning for unseeded user IDs.
     * Implements `update_user_communication_profile` with standard taxonomy classification (`classify_correction`), deduplication, capping weak areas to 5, graduation of clean areas to `strong_areas`, and adaptive skill updates (`compute_updated_skill_level`).
     * Features thread-safe caching (`_coach_lock`, `_in_memory_coach_sessions`, `_in_memory_user_profiles`) and dual-write Supabase updates with automatic fallback to baseline columns if extended columns fail.
   - `backend/app/agents/coach.py` (694 lines):
     * Implements `CoachSession` with state machine across modes `"conversation"`, `"answer_training"`, `"english_improvement"`.
     * Strict prompt adherence to `docs/08_AGENT_PROMPTS.md` and `docs/07_GUARDRAILS.md`.
     * Maximum 1–2 corrections per exchange guardrail enforced in `process_response`.
     * Full bidirectional serialization and deserialization via `to_dict()` (lines 643–662) and `from_dict()` (lines 664–693).
     * Deterministic offline mock heuristics catalog (`_evaluate_mock_coach_heuristics`) and live NVIDIA NIM fallback.
   - `backend/app/routers/coach.py` (318 lines):
     * Exposes endpoints `POST /coach/start`, `POST /coach/respond`, and `POST /coach/end`.
     * `CoachSessionManager` provides synchronized cache retrieval and persistence hydration (`get_or_load`).
     * `POST /coach/end` contains idempotent early-exit logic (lines 289–304) returning existing summary without double-incrementing `sessions_count`.
     * Proper HTTP error handling: HTTP 400 for invalid modes, empty user IDs, or empty/whitespace utterances; HTTP 404 for missing sessions; HTTP 422 for missing required fields.
   - `backend/schema.sql` (lines 96–130):
     * Idempotent table definition `coach_sessions` with primary key, foreign key cascade to `users(id)`, CHECK constraint on `mode`, and indexes on `user_id`, `created_at`, `mode`, `is_complete`, and `status`.
     * Extended columns: `history`, `corrections`, `status`, `started_at`, `updated_at`.
     * User table extensions: `skill_level`, `weak_areas`, `strong_areas`, and `chk_users_skill_level` CHECK constraint (`'beginner'`, `'intermediate'`, `'advanced'`).
   - `backend/app/main.py` (lines 107–108):
     * Router mounted with `app.include_router(coach.router, prefix="/coach", tags=["coach"])`.

2. **Integrity & Code Inspection**:
   - Actively inspected for integrity violations:
     * Zero hardcoded test outputs or dummy facade stubs found.
     * Real pedagogical prompt construction, real classification taxonomy, real adaptive level calculation, and genuine session persistence logic.
     * Zero bypasses or external shortcuts.

3. **Independent Test Execution Results**:
   - Command: `.\.venv\Scripts\pytest.exe backend/tests/test_coach.py -v`
     * Result: `31 passed in 0.31s` (Exit Code 0).
   - Command: `.\.venv\Scripts\pytest.exe backend/tests -q`
     * Result: `280 passed in 1.05s` (Exit Code 0). Zero failures, zero warnings across the entire repository.

4. **Adversarial Stress Test Results**:
   - Roundtrip serialization `CoachSession -> to_dict() -> from_dict()`: Verified 100% losslessness of state, history, and telemetry.
   - Taxonomy classification (`classify_correction`): Verified on all 7 canonical categories (`filler words`, `STAR structure`, `conciseness`, `grammar & syntax`, `professional vocabulary`, `clarity`, `concrete examples`) plus fallback (`natural phrasing`). Handled `None` and empty dictionaries without throwing exceptions.
   - Weak area cap: When 7 distinct weak categories were injected, `weak_areas` was strictly deduplicated and capped at 5 (`len(comm['weak_areas']) <= 5`).
   - Weak area graduation: When user had existing weak areas (`STAR structure`, `conciseness`) and completed a clean session in `answer_training`, both graduated to `strong_areas` and were removed from `weak_areas`.
   - Idempotent termination: Calling `POST /coach/end` consecutively on the same session returned `sessions_count=1` on both calls without duplicate profile updates.

---

## 2. Logic Chain

1. *From Observation 1 & 2*: The implementation of Milestone 3 thoroughly adheres to the architecture specified in `ORIGINAL_REQUEST.md` (R4), `docs/03_PHASE_PLAN.md`, `docs/05_ACCEPTANCE_CRITERIA.md`, `docs/07_GUARDRAILS.md`, and `docs/08_AGENT_PROMPTS.md`.
2. *From Observation 1 & 4*: The database layer in `coach_persistence.py` correctly handles Supabase persistence with dual-write resilience and thread-safe memory caching. Column compatibility between `schema.sql`, PostgreSQL constraints, and `MockSupabaseClient` is completely aligned.
3. *From Observation 4*: The profile learning engine accurately classifies errors, deduplicates and bounds weak areas to 5, properly graduates mastered areas upon clean sessions, and preserves idempotency on repeated session completion requests.
4. *From Observation 3*: All 31 coach-specific tests pass cleanly, and all 280 tests across all modules (Milestones 0, 1, 2, and 3) pass with zero errors, confirming zero regressions.
5. *From Observation 2*: No integrity violations, shortcuts, facade implementations, or hardcoded test falsifications are present in the work product.

---

## 3. Caveats

- Tests run against the in-memory `MockSupabaseClient` and the deterministic heuristics catalog when offline without cloud API keys (`NVIDIA_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`). In production deployment, live service credentials will be passed via environment variables.
- Dual-write retry logic in `save_coach_session` and `update_user_communication_profile` logs warnings if extended schema columns are absent; this is an intentional safety fallback for un-migrated schemas.

---

## 4. Conclusion

**Verdict: APPROVE**

Milestone 3 (Phase 3 AI Communication Coach Agent & Profile Learning Engine) meets all architectural, persistence, safety, and testing requirements. Session persistence to `coach_sessions`, profile adaptation in `users`, guardrails, taxonomy classification, and REST endpoints are fully functional and verified with zero regressions across the 280-test repository suite. Milestone 3 is approved for progression to Milestone 4.

---

## 5. Verification Method

To independently reproduce this verification:
1. Run coach-specific test suite:
   ```powershell
   .\.venv\Scripts\pytest.exe backend/tests/test_coach.py -v
   ```
   *Expected output*: `31 passed`.
2. Run full repository test suite:
   ```powershell
   .\.venv\Scripts\pytest.exe backend/tests -q
   ```
   *Expected output*: `280 passed`.
3. Verify idempotence and capping:
   ```powershell
   $env:PYTHONPATH='backend'; .\.venv\Scripts\python.exe -c "
   from tests.conftest import LocalClient
   from app.main import app
   import uuid

   with LocalClient(app) as client:
       uid = str(uuid.uuid4())
       s = client.post('/coach/start', json={'user_id': uid, 'mode': 'conversation'}).json()['session_id']
       client.post('/coach/respond', json={'session_id': s, 'user_text': 'I spoke clearly today.'})
       e1 = client.post('/coach/end', json={'session_id': s}).json()
       e2 = client.post('/coach/end', json={'session_id': s}).json()
       assert e1['profile_updated']['sessions_count'] == 1
       assert e2['profile_updated']['sessions_count'] == 1
       print('VERIFIED IDEMPOTENT COUNT: 1')
   "
   ```
   *Expected output*: `VERIFIED IDEMPOTENT COUNT: 1`.
