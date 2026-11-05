# VOXPREP Backend E2E Test Infrastructure Specification

## 1. Test Philosophy & Architecture

### 1.1 Opaque-Box & Requirement-Driven Testing
The VOXPREP End-to-End (E2E) testing suite operates strictly under an **opaque-box paradigm**:
- **Interface Decoupling**: Tests interact exclusively with the public HTTP REST interfaces defined in `PROJECT.md` and `ORIGINAL_REQUEST.md`. No test directly accesses internal state machines, private module functions, or internal storage dictionaries.
- **Contract Verification**: Every request payload, response status code, header, and JSON schema is validated against the formal API contracts established in `docs/05_ACCEPTANCE_CRITERIA.md` and `docs/08_AGENT_PROMPTS.md`.
- **Expected Output Derivation**: All expected outputs and rubric dimensions (`relevance`, `clarity`, `depth`, `examples` on 1–10 scale) are derived authoritatively from `PROJECT.md` and `ORIGINAL_REQUEST.md`.

### 1.2 Dual Execution Modes: Live Server vs In-Process TestClient
The test suite seamlessly supports two execution modes without code modifications:
1. **Live Server Mode (`BASE_URL` configured)**:
   When `BASE_URL` (e.g. `http://localhost:8000` or production Railway URL) is provided, `httpx.Client` or `httpx.AsyncClient` executes real network HTTP requests against the running instance.
2. **In-Process FastAPI `TestClient` Mode (Default / CI Mode)**:
   When running locally or in continuous integration without a booted server, the suite instantiates `fastapi.testclient.TestClient(app)` with mock fallbacks for external AI services (NVIDIA NIM) and Supabase when credentials (`NVIDIA_API_KEY`, `SUPABASE_URL`) are absent.

### 1.3 External Service Mock Fallbacks
To guarantee deterministic execution and high speed in environments without active NVIDIA API keys or Supabase projects:
- **NVIDIA Nemotron LLM**: Replaced with a deterministic mock adhering to the exact prompt instructions and response JSON schemas defined in `docs/08_AGENT_PROMPTS.md`.
- **NVIDIA Parakeet STT**: Replaced with an audio transcription mock recognizing standard test audio waveforms or metadata headers.
- **NVIDIA Magpie TTS**: Replaced with a mock returning valid Linear PCM / WAV byte headers.
- **Supabase Auth & DB**: Supported via in-memory mock repositories adhering to the `users`, `interview_sessions`, and `coach_sessions` schema.

---

## 2. Feature Inventory to Test Tier Mapping

The 24 backend features identified in `PROJECT.md` are comprehensively mapped across four progressive testing tiers:

| Feature # | Feature Description | Tier 1 (Isolated) | Tier 2 (Boundaries) | Tier 3 (Pairwise) | Tier 4 (Scenarios) |
|---|---|:---:|:---:|:---:|:---:|
| 1 | Dedicated Virtual Environment (`.venv`) | - | - | - | Environment |
| 2 | Health Check (`GET /health`) | `test_tier1_features.py` | - | - | Pre-flight |
| 3 | CORS Configuration | `test_tier1_features.py` | `test_tier2_boundaries.py` | - | - |
| 4 | Supabase DDL Schema | - | - | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 5 | LLM Client (`services/llm.py`) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 6 | STT Client (`services/stt.py`) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 7 | TTS Client (`services/tts.py`) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 8 | Voice Process (`POST /voice/process`) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 9 | User Registration (`POST /auth/register`) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 10 | User Login (`POST /auth/login`) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 11 | Supabase Client Singleton | `test_tier1_features.py` | - | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 12 | Start Interview (`POST /interview/start`) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 13 | Interview Respond (`POST /interview/respond`) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 14 | 4-Dimension Rubric Scoring (1–10) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 15 | End Interview (`POST /interview/end`) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 16 | Report Generation (`services/report.py`) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 17 | Fetch Report (`GET /interview/report/{id}`) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 18 | Start Coach Session (`POST /coach/start`) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 19 | Coach Respond (`POST /coach/respond`) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 20 | End Coach Session (`POST /coach/end`) | `test_tier1_features.py` | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 21 | Profile Learning Updater | - | `test_tier2_boundaries.py` | `test_tier3_pairwise.py` | `test_tier4_scenarios.py` |
| 22 | Global Exception Handlers | - | `test_tier2_boundaries.py` | - | - |
| 23 | Containerization (`Dockerfile`) | - | - | - | Production Spec |
| 24 | Railway Deployment Manifest | - | - | - | Production Spec |

---

## 3. Test Tier Descriptions

### Tier 1: Isolated Feature Verification (`test_tier1_features.py`)
- Purpose: Atomic validation of each endpoint under optimal "happy path" inputs.
- Coverage:
  - `GET /health` returns status `ok` and HTTP 200.
  - `POST /auth/register` creates a user and returns access token and user record.
  - `POST /auth/login` verifies user authentication and token issuance.
  - `POST /voice/process` executes audio transcription, LLM reasoning, and TTS synthesis.
  - `POST /interview/start` initializes an interview session and returns opening greeting.
  - `POST /interview/respond` processes single candidate answer and returns spoken response with dimension scoring.
  - `POST /interview/end` terminates session and triggers full performance report.
  - `GET /interview/report/{session_id}` retrieves the structured report JSON.
  - `POST /coach/start` initiates coach session with opening message.
  - `POST /coach/respond` evaluates utterance and returns coach response with constructive correction.
  - `POST /coach/end` closes coach session and returns summary with profile updates.

### Tier 2: Boundary & Corner Cases (`test_tier2_boundaries.py`)
- Purpose: Validate guardrails, system limits, and defensive error handling under adverse inputs.
- Coverage:
  - Audio inputs: 0-byte audio file, corrupted non-audio bytes, extremely large payload.
  - Session boundaries: strict enforcement of maximum 5 core questions per interview session.
  - Follow-up limits: maximum 1 follow-up question per core question before forced transition.
  - Coach corrections: strict limitation of at most 1–2 corrections per exchange.
  - Answer quality edges: 1-word responses ("Yes", "Python"), "I don't know", off-topic tangents.
  - Invalid modes & inputs: unsupported `interview_type` (e.g. `debate`), unsupported coach mode (`argument`).
  - Missing required fields: validation error interception (HTTP 422) for missing email, session_id, or answer text.
  - Non-existent session IDs: proper HTTP 404 handling.

### Tier 3: Pairwise Cross-Feature Combinations (`test_tier3_pairwise.py`)
- Purpose: Validate interaction between disparate backend subsystems across lifecycles.
- Coverage:
  - Sequence A: `Auth Register -> Login -> Start Technical Interview -> Respond -> End -> Fetch Report`.
  - Sequence B: `Auth Register -> Start Coach Session (English Improvement) -> Respond multiple times -> End -> Verify Profile Weak/Strong Areas Updated`.
  - Sequence C: `Auth Token -> Authenticated Voice Process Endpoint -> STT-to-Agent pipeline`.

### Tier 4: Real-World Application Scenarios (`test_tier4_scenarios.py`)
- Purpose: High-fidelity end-to-end simulations mirroring actual candidate usage.
- Coverage:
  - Scenario 1 (Full Technical Interview): Mid-level Backend Engineer candidate completes all 5 technical questions (including 1 follow-up), evaluates rubric trends across relevance, clarity, depth, and examples, and verifies comprehensive final report with coach recommendations.
  - Scenario 2 (Full HR Behavioral Interview): Junior Software Developer completes full behavioral session; tests STAR method alignment and behavioral assessment.
  - Scenario 3 (Multi-Turn Communication Drill): Non-native English speaker practices everyday conversation with coach across 4 distinct turns; validates supportive coaching tone, max 2 corrections, and profile learning progression from Beginner to Intermediate.

---

## 4. Test Architecture & Directory Layout

```
backend/tests/
├── conftest.py                   # Root pytest fixtures (shared helpers, client factory)
└── e2e/
    ├── __init__.py
    ├── conftest.py               # E2E test client, mock NVIDIA & Supabase harnesses
    ├── test_tier1_features.py    # Isolated happy-path feature tests
    ├── test_tier2_boundaries.py  # Guardrail & boundary tests
    ├── test_tier3_pairwise.py    # Cross-feature lifecycle tests
    └── test_tier4_scenarios.py   # Full real-world simulation scenarios
```

---

## 5. Test Execution Commands

From project root:
```bash
# Activate virtual environment
.venv\Scripts\activate   # Windows
# or: source .venv/bin/activate # Linux/macOS

# Run the entire E2E test suite
pytest backend/tests/e2e -v

# Run individual tiers
pytest backend/tests/e2e/test_tier1_features.py -v
pytest backend/tests/e2e/test_tier2_boundaries.py -v
pytest backend/tests/e2e/test_tier3_pairwise.py -v
pytest backend/tests/e2e/test_tier4_scenarios.py -v

# Run against a live running server
$env:BASE_URL="http://localhost:8000"  # PowerShell
pytest backend/tests/e2e -v
```
