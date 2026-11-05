# TEST_READY: VOXPREP Backend E2E Test Suite

## 1. Test Suite Status & Certification
The End-to-End (E2E) Opaque-Box Test Suite for VOXPREP Backend MVP is **complete, syntactically verified, and ready for continuous execution** across all milestone deliverables and final acceptance.

- **Integrity Mode:** Opaque-Box (HTTP REST interfaces only; zero internal coupling)
- **Total Test Cases:** 28 test cases across 4 progressive tiers
- **Execution Engine:** `pytest` + FastAPI `TestClient` / `httpx.Client`
- **Dual Track Mode:** Supports both in-process `TestClient` (with external mock fallbacks when API keys are absent) and live network execution against a running server (`BASE_URL`).

---

## 2. Test Artifacts Inventory

| Test File | Tier | Focus | Test Count |
|---|---|---|:---:|
| `backend/tests/e2e/conftest.py` | Fixtures | App resolution, `TestClient`, live `BASE_URL` adapter, WAV byte generators | N/A |
| `backend/tests/conftest.py` | Root Fixtures | Root-level pytest discoverability | N/A |
| `backend/tests/e2e/test_tier1_features.py` | Tier 1 | Isolated feature happy paths (Health, Auth, Voice, Interview, Coach) | 11 |
| `backend/tests/e2e/test_tier2_boundaries.py` | Tier 2 | Boundaries, guardrails, corrupt inputs, 404/422 validation, limit enforcement | 11 |
| `backend/tests/e2e/test_tier3_pairwise.py` | Tier 3 | Cross-feature lifecycles (Auth + Interview + Report, Auth + Coach + Profile, Auth + Voice) | 3 |
| `backend/tests/e2e/test_tier4_scenarios.py` | Tier 4 | Real-world multi-turn simulations (Full Tech, Full HR, Multi-turn Coach) | 3 |
| **Total** | | | **28** |

---

## 3. Test Tier Breakdown

### Tier 1: Feature Coverage (Isolated Happy Path)
1. `test_health_check_returns_ok`: Validates `GET /health` returns HTTP 200 with `{"status": "ok"}`.
2. `test_auth_register_isolated`: Validates `POST /auth/register` creates user and returns JWT token.
3. `test_auth_login_isolated`: Validates `POST /auth/login` verifies credentials and issues token.
4. `test_voice_process_isolated`: Validates `POST /voice/process` handles audio upload and returns transcript / spoken response.
5. `test_interview_start_isolated`: Validates `POST /interview/start` initializes session and returns opening greeting.
6. `test_interview_respond_isolated`: Validates `POST /interview/respond` records answer and returns spoken response with next question or follow-up.
7. `test_interview_end_isolated`: Validates `POST /interview/end` concludes session and triggers report generation.
8. `test_interview_report_retrieval_isolated`: Validates `GET /interview/report/{session_id}` returns full JSON report matching 4-dimension rubric.
9. `test_coach_start_isolated`: Validates `POST /coach/start` initiates coach session.
10. `test_coach_respond_isolated`: Validates `POST /coach/respond` processes conversational utterance.
11. `test_coach_end_isolated`: Validates `POST /coach/end` returns summary and profile updates.

### Tier 2: Boundary & Corner Cases
1. `test_voice_process_empty_audio_boundary`: Handles 0-byte audio payload gracefully without crashing.
2. `test_voice_process_corrupt_audio_boundary`: Handles non-audio corrupt byte stream gracefully.
3. `test_interview_max_5_questions_boundary`: Enforces maximum 5 core questions limit before mandatory completion.
4. `test_interview_max_1_follow_up_boundary`: Enforces maximum 1 follow-up question per core question.
5. `test_coach_max_1_to_2_corrections_boundary`: Verifies coach never overwhelms user with > 2 corrections per exchange.
6. `test_interview_invalid_mode_rejected`: Enforces validation rejection (HTTP 400/422) for unsupported modes (e.g. debate).
7. `test_coach_invalid_mode_rejected`: Enforces validation rejection for unsupported coach modes.
8. `test_missing_required_fields_raises_422`: Validates FastAPI Pydantic schema rejection for missing required payload fields.
9. `test_interview_1_word_answer_handling`: Verifies graceful response to terse single-word answers ("Yes", "React").
10. `test_interview_i_dont_know_answer_handling`: Verifies polite handling and advancement when candidate states "I don't know".
11. `test_nonexistent_session_id_returns_404`: Verifies HTTP 404 for invalid/unknown session UUIDs.

### Tier 3: Pairwise Cross-Feature Combinations
1. `test_pairwise_register_login_interview_report_lifecycle`: Complete lifecycle from registration -> login -> interview session -> report retrieval.
2. `test_pairwise_register_coach_profile_update_lifecycle`: Complete lifecycle from registration -> coach drill -> session completion -> communication profile learning update.
3. `test_pairwise_authenticated_voice_processing`: Bearer token authentication integrated with multipart audio processing pipeline.

### Tier 4: Real-World Application Scenarios
1. `test_scenario_full_technical_interview_simulation`: 5-turn Senior Backend Engineer interview covering distributed systems, caching, ACID transactions, fault tolerance, and memory leak triage, followed by rubric verification.
2. `test_scenario_full_hr_behavioral_interview_simulation`: Junior Developer behavioral interview evaluating STAR method responses on collaboration, conflict resolution, and career vision.
3. `test_scenario_multi_turn_coach_conversational_progression`: 4-turn ESL conversation drill practicing weekend activities, past tense verbs, gentle corrections, and profile progression.

---

## 4. Runner Execution Commands

### In-Process Test Execution (Default CI / Local Mode)
Execute inside the project root:

```bash
# Windows (PowerShell)
.venv\Scripts\pytest backend/tests/e2e -v

# Linux / macOS
.venv/bin/pytest backend/tests/e2e -v
```

### Running Individual Tiers
```bash
# Tier 1: Happy path feature coverage
pytest backend/tests/e2e/test_tier1_features.py -v

# Tier 2: Boundary & corner cases
pytest backend/tests/e2e/test_tier2_boundaries.py -v

# Tier 3: Cross-feature combinations
pytest backend/tests/e2e/test_tier3_pairwise.py -v

# Tier 4: Real-world scenarios
pytest backend/tests/e2e/test_tier4_scenarios.py -v
```

### Live Server Network Execution
To run the full suite against a live running backend (e.g. local uvicorn on port 8000 or Railway deployment):

```bash
# PowerShell
$env:BASE_URL="http://localhost:8000"
pytest backend/tests/e2e -v

# Bash
export BASE_URL="http://localhost:8000"
pytest backend/tests/e2e -v
```
