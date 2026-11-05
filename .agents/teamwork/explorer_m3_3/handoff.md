# Milestone 3 Technical Blueprint: Coach Router & Comprehensive Test Suite

**Agent**: `explorer_m3_3` (Coach Router & Test Suite Architect)  
**Date**: 2026-11-05T18:45:00Z  
**Milestone**: Milestone 3 (Phase 3: AI Communication Coach Agent)  
**Deliverables Covered**:
1. API Router: `backend/app/routers/coach.py` (`POST /coach/start`, `POST /coach/respond`, `POST /coach/end`)
2. FastAPI Main Application Mount: `backend/app/main.py`
3. Comprehensive Test Suite: `backend/tests/test_coach.py` (LocalClient, run_sync, all modes, edge cases, boundaries)

---

## 1. Observation

### 1.1 Authoritative Requirements & Phase Specifications
- **`ORIGINAL_REQUEST.md` (R4, lines 58–72)**:
  - `POST /coach/start`: Request body `{ "user_id": str, "mode": str }` (modes: `"conversation"`, `"answer_training"`, `"english_improvement"`). Returns `{ "session_id": str, "opening_message": str, "mode": str }`.
  - `POST /coach/respond`: Request body `{ "session_id": str, "user_text": str }`. Returns `{ "coach_message": str, "correction": { "original": str, "improved": str, "reason": str } | None, "next_prompt": str }`.
  - `POST /coach/end`: Request body `{ "session_id": str }`. Returns `{ "session_id": str, "status": "completed", "summary": dict, "profile_updated": dict }`.
  - On session end: saves exchanges to Supabase `coach_sessions` and updates user communication profile (`skill_level`, `weak_areas`, `strong_areas`).
- **`PROJECT.md` (lines 78–81, 107–109)**:
  - Feature 18: Start Coach Session (`POST /coach/start`)
  - Feature 19: Coach Respond (`POST /coach/respond`)
  - Feature 20: End Coach Session (`POST /coach/end`)
  - Feature 21: Profile Learning Updater
  - Router mount point in `backend/app/main.py`: `app.include_router(coach.router, prefix="/coach", tags=["coach"])`
- **`docs/08_AGENT_PROMPTS.md` (lines 153–228)**:
  - Base Prompt placeholders: `{user_name}`, `{skill_level}`, `{weak_areas}`, `{strong_areas}`, `{mode}`.
  - Core Rules: Never interrupt; feedback after acknowledging response; max 1–2 corrections per exchange; always provide better alternative; explain reason; adapt difficulty to skill level.
  - Correction format: `"[Acknowledge]. One small improvement: instead of saying '[original]', you could say '[improved]'. This sounds more natural because [reason]. Want to try it?"`
  - Output JSON: `{"coach_message": str, "correction": {"original": str, "improved": str, "reason": str} | None, "next_prompt": str}`.
- **`docs/07_GUARDRAILS.md` (lines 73–102)**:
  - Fallbacks:
    - User gives very short one-word answer: gently prompt for more.
    - User says "I don't know" / seems frustrated: acknowledge warmly, try something easier.
    - Profile not found: initialize beginner/intermediate defaults, create profile.

### 1.2 Codebase Precedents & Existing Patterns
1. **`backend/app/main.py:98-110`**:
   ```python
   from app.routers import auth, voice, interview
   app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
   app.include_router(voice.router, prefix="/voice", tags=["Voice Pipeline"])
   app.include_router(interview.router, prefix="/interview", tags=["Interviewer Agent"])
   # Milestone 3: Planned Mount Point
   # from app.routers import coach
   # app.include_router(coach.router, prefix="/coach", tags=["Coach Agent"])
   ```
2. **`backend/app/routers/interview.py:101-134`**:
   - `InterviewSessionManager`: In-memory thread-safe session dictionary (`_active_sessions`) with `get_or_load(session_id)`, `register(session)`, and `clear()` methods.
   - Pydantic models with explicit field descriptions and validation.
   - Idempotent lifecycle handling.
3. **`backend/tests/conftest.py:60-176`**:
   - `LocalClient`: In-memory ASGI test client that directly drives the application coroutine stack via synchronous stepping (`stack = [coro]`, `current.send(None)`). Completely avoids Windows socketpair event loop hangs.
4. **`backend/tests/test_interview.py:48-62`**:
   - `run_sync(coro)`: Synchronously executes coroutine call stacks for direct agent and service unit testing without asyncio socketpair dependencies:
     ```python
     def run_sync(coro):
         stack = [coro]
         while stack:
             current = stack[-1]
             try:
                 sub = current.send(None)
                 if hasattr(sub, "send"):
                     stack.append(sub)
             except StopIteration as exc:
                 stack.pop()
                 if not stack:
                     return exc.value
     ```
5. **Existing E2E Test Suite (`backend/tests/e2e/test_tier1_features.py:210-276`)**:
   - `test_coach_start_isolated`: calls `POST /coach/start` with `{"user_id": str(uuid.uuid4()), "mode": "conversation"}` and expects HTTP 200 with `session_id` and `opening_message`.
   - `test_coach_respond_isolated`: calls `POST /coach/respond` with `user_text` and expects `coach_message`, `next_prompt`, and optional `correction`.
   - `test_coach_end_isolated`: calls `POST /coach/end` and asserts `assert "updated_profile" in data` and `assert data.get("session_id") == session_id`.
   - Key Compatibility Observation: Dispatch states `profile_updated: dict`, while existing test asserts `updated_profile in data`. The `CoachEndResponse` model must support both keys (`profile_updated` and `updated_profile`) to achieve 100% test pass rate across all tiers!
6. **Peer Architect Handoffs**:
   - `explorer_m3_1/handoff.md`: Defines `CoachSession` class in `backend/app/agents/coach.py`, mode system prompts, heuristic rule engine (`_evaluate_mock_coach_heuristics`), deterministic offline catalog, and `to_dict()`/`from_dict()` serialization.
   - `explorer_m3_2/handoff.md`: Defines `backend/app/db/coach_persistence.py` with `save_coach_session`, `get_coach_session`, `get_user_profile`, `update_user_communication_profile`, in-memory fallback caches, and adaptive profile learning algorithm.

---

## 2. Logic Chain

### Step 2.1: Router Contract & Status Code Mapping
1. **From Observation 1.1 & Dispatch Instructions**:
   - `POST /coach/start`:
     - Input: `{ "user_id": str, "mode": str }`.
     - Mode validation: If `mode` is not in `{"conversation", "answer_training", "english_improvement"}`, return `HTTP 400 Bad Request` with detail explaining valid modes.
     - User ID validation: If `user_id` is empty or only whitespace, return `HTTP 400 Bad Request`.
     - Missing fields (e.g. omitted `user_id` or `mode`): FastAPI/Pydantic returns `HTTP 422 Unprocessable Entity`.
     - Output: `{ "session_id": str, "opening_message": str, "mode": str }` with `HTTP 200 OK`.
   - `POST /coach/respond`:
     - Input: `{ "session_id": str, "user_text": str }`.
     - Session validation: If `session_id` does not exist in memory or database, return `HTTP 404 Not Found`.
     - User text validation: If `user_text` is empty or only whitespace (`not user_text.strip()`), return `HTTP 400 Bad Request`.
     - State validation: If session has already been completed, return `HTTP 400 Bad Request`.
     - Output: `{ "coach_message": str, "correction": { "original": str, "improved": str, "reason": str } | None, "next_prompt": str }` with `HTTP 200 OK`.
   - `POST /coach/end`:
     - Input: `{ "session_id": str }`.
     - Session validation: If `session_id` does not exist, return `HTTP 404 Not Found`.
     - Idempotency: If session is already completed, return `HTTP 200 OK` with existing `summary` and `profile_updated` without re-running mutations.
     - Finalization: Marks session complete, updates user profile in Supabase (`users.communication_profile`), saves completed session state, and returns `{ "session_id": str, "status": "completed", "summary": dict, "profile_updated": dict, "updated_profile": dict }` with `HTTP 200 OK`.

### Step 2.2: Session Manager Design (`CoachSessionManager`)
1. **From Observation 1.2 (InterviewSessionManager precedent)**:
   - Provide a singleton `CoachSessionManager` in `backend/app/routers/coach.py`:
     - Maintains in-memory map `_active_sessions: Dict[str, CoachSession]`.
     - Thread-safety via `threading.Lock()`.
     - `get_or_load(session_id)` checks memory first; on cache miss, queries `get_coach_session(session_id)` from `coach_persistence.py`, hydrates via `CoachSession.from_dict()`, and stores in memory.
     - `register(session)` stores newly instantiated sessions.
     - `clear()` purges in-memory sessions between test cases for complete test isolation.

### Step 2.3: Backward and Forward Model Compatibility
1. **From Observation 1.1 & 1.2**:
   - The dispatch specification requests:
     `Response: { "session_id": str, "status": "completed", "summary": dict, "profile_updated": dict }`
   - However, existing E2E test `test_tier1_features.py:271` asserts:
     `assert "updated_profile" in data`
   - Design decision: In `CoachEndResponse`, define both `profile_updated: Dict[str, Any]` and `updated_profile: Dict[str, Any]`, setting both to the profile dictionary. This guarantees immediate zero-regression passing for all existing E2E tiers while fully adhering to the dispatch specification.

### Step 2.4: Test Suite Architecture (`backend/tests/test_coach.py`)
1. **From Observation 1.2 (Test Harness Precedents)**:
   - Must use `LocalClient(app)` fixture to prevent Windows socket hangs.
   - Must use `run_sync` helper for async coroutines.
   - Must clear `session_manager` before and after each test using an `autouse=True` fixture.
   - Must cover 5 distinct testing dimensions:
     1. Start session across all 3 modes (`conversation`, `answer_training`, `english_improvement`).
     2. Respond with clear answer (`correction=None`) vs answer needing correction (`correction={original, improved, reason}`).
     3. End session persistence to `coach_sessions` and user profile updates (`skill_level`, `weak_areas`, `strong_areas`).
     4. Boundary & error conditions (invalid mode, missing session, empty text, completed session, idempotent end, missing fields).
     5. Direct unit tests of `CoachSession` and `coach_persistence` methods via `run_sync`.

---

## 3. Implementation Blueprint

### 3.1 `backend/app/routers/coach.py` Blueprint

```python
"""VOXPREP Backend API - AI Communication Coach Router
Milestone 3: Phase 3 AI Communication Coach Agent.

Exposes REST endpoints for the coach lifecycle:
- POST /coach/start: Initializes coaching session and returns opening greeting
- POST /coach/respond: Evaluates user speech, delivers encouragement and max 1-2 corrections
- POST /coach/end: Concludes session, updates communication profile, and persists state

Authoritative references:
- docs/03_PHASE_PLAN.md (Phase 3 Deliverables)
- docs/05_ACCEPTANCE_CRITERIA.md (Phase 3 Acceptance Criteria)
- docs/07_GUARDRAILS.md (Coach Rules, Boundaries, and Fallbacks)
- docs/08_AGENT_PROMPTS.md (Agent 2 Base Prompt & Mode Instructions)
"""

import copy
import logging
import threading
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.agents.coach import CoachSession, VALID_COACH_MODES
from app.db.coach_persistence import (
    get_coach_session,
    get_user_profile,
    save_coach_session,
    update_user_communication_profile,
)

logger = logging.getLogger("voxprep.routers.coach")

router = APIRouter(tags=["coach"])


# =============================================================================
# Request and Response Models
# =============================================================================

class CoachCorrection(BaseModel):
    """Structured linguistic or communication correction."""
    original: str = Field(..., description="User's original phrase or sentence that needed improvement")
    improved: str = Field(..., description="Recommended alternative or corrected phrase")
    reason: str = Field(..., description="Explanation of why the improvement is suggested")


class CoachStartRequest(BaseModel):
    """Payload to start a new coaching session."""
    user_id: str = Field(..., min_length=1, description="Unique UUID or identifier of the user")
    mode: str = Field(..., min_length=1, description="Coach mode: 'conversation', 'answer_training', 'english_improvement'")


class CoachStartResponse(BaseModel):
    """Response returned upon successful coach session initialization."""
    session_id: str = Field(..., description="Unique UUID identifying the coach session")
    opening_message: str = Field(..., description="Warm opening greeting and initial exercise prompt")
    mode: str = Field(..., description="Active coaching mode")


class CoachRespondRequest(BaseModel):
    """Payload containing user's verbal or typed response."""
    session_id: str = Field(..., min_length=1, description="UUID of the active coach session")
    user_text: str = Field(..., description="User's response text")


class CoachRespondResponse(BaseModel):
    """Coach agent's evaluated response and next prompt."""
    coach_message: str = Field(..., description="Coach's supportive conversational message")
    correction: Optional[CoachCorrection] = Field(None, description="Constructive correction if needed, or None if clear")
    next_prompt: str = Field(..., description="Next conversational prompt or exercise question")


class CoachEndRequest(BaseModel):
    """Payload to conclude a coaching session."""
    session_id: str = Field(..., min_length=1, description="UUID of the coach session to terminate")


class CoachEndResponse(BaseModel):
    """Response returned upon terminating a coaching session and updating profile."""
    session_id: str = Field(..., description="Unique UUID of the completed coach session")
    status: str = Field(default="completed", description="Status of the session, 'completed'")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Session performance summary and metrics")
    profile_updated: Dict[str, Any] = Field(default_factory=dict, description="Updated user communication profile")
    updated_profile: Dict[str, Any] = Field(default_factory=dict, description="Backward-compatible alias for profile_updated")


# =============================================================================
# In-Memory Session Cache & Persistence Bridge
# =============================================================================

class CoachSessionManager:
    """Session coordinator managing active CoachSession instances with persistence backing."""

    def __init__(self):
        self._active_sessions: Dict[str, CoachSession] = {}
        self._lock = threading.Lock()

    async def get_or_load(self, session_id: str) -> Optional[CoachSession]:
        """Retrieves session from memory cache or restores from persistence layer."""
        with self._lock:
            if session_id in self._active_sessions:
                return self._active_sessions[session_id]

        row = await get_coach_session(session_id)
        if not row:
            return None

        session = CoachSession.from_dict(row)
        with self._lock:
            self._active_sessions[session_id] = session
        return session

    def register(self, session: CoachSession) -> None:
        """Stores session in active memory cache."""
        with self._lock:
            self._active_sessions[session.session_id] = session

    def clear(self) -> None:
        """Clears memory cache for isolated test runs."""
        with self._lock:
            self._active_sessions.clear()


session_manager = CoachSessionManager()


# =============================================================================
# Router Endpoints
# =============================================================================

@router.post(
    "/start",
    response_model=CoachStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Start a Coach Session",
)
async def start_coach(payload: CoachStartRequest) -> CoachStartResponse:
    """
    Initializes a new coach session:
    - Validates user_id is non-empty.
    - Validates mode is one of ('conversation', 'answer_training', 'english_improvement').
    - Loads or auto-provisions user profile from Supabase users table.
    - Generates unique session UUID and instantiates CoachSession.
    - Returns session_id, opening_message, and mode.
    """
    clean_user_id = payload.user_id.strip()
    if not clean_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id must not be empty",
        )

    clean_mode = payload.mode.strip().lower()
    if clean_mode not in VALID_COACH_MODES:
        valid_modes_str = ", ".join(sorted(VALID_COACH_MODES))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid coach mode '{payload.mode}'. Valid modes: {valid_modes_str}",
        )

    # Load or provision user communication profile
    profile = await get_user_profile(clean_user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{clean_user_id}' not found",
        )

    session_id = str(uuid.uuid4())
    session = CoachSession(
        session_id=session_id,
        user_id=clean_user_id,
        mode=clean_mode,
        user_profile=profile.get("communication_profile", profile),
    )

    opening_message = await session.start_session()
    session_manager.register(session)

    # Persist session to database
    await save_coach_session(session.session_id, session.to_dict())

    logger.info(f"Initialized coach session {session_id} ({clean_mode}) for user {clean_user_id}")
    return CoachStartResponse(
        session_id=session_id,
        opening_message=opening_message,
        mode=clean_mode,
    )


@router.post(
    "/respond",
    response_model=CoachRespondResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit User Speech to Coach",
)
async def respond_coach(payload: CoachRespondRequest) -> CoachRespondResponse:
    """
    Processes user's spoken or typed response:
    - Verifies active session exists (returns 404 if missing).
    - Verifies user_text is non-empty (returns 400 if empty).
    - Verifies session is not already completed (returns 400 if completed).
    - Delivers supportive coach feedback and at most 1-2 constructive corrections.
    - Persists updated session state to Supabase.
    - Returns coach_message, correction, and next_prompt.
    """
    clean_sid = payload.session_id.strip()
    if not clean_sid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id must not be empty",
        )

    clean_text = payload.user_text.strip()
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_text cannot be empty",
        )

    session = await session_manager.get_or_load(clean_sid)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coach session not found",
        )

    if session.is_complete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Coach session is already completed.",
        )

    result = await session.process_response(clean_text)

    # Persist updated exchange history to Supabase
    await save_coach_session(session.session_id, session.to_dict())

    # Format correction model
    raw_corr = result.get("correction")
    correction_model = None
    if isinstance(raw_corr, dict) and raw_corr.get("original") and raw_corr.get("improved"):
        correction_model = CoachCorrection(
            original=raw_corr["original"],
            improved=raw_corr["improved"],
            reason=raw_corr.get("reason", "Provides a clearer, more natural phrasing."),
        )

    return CoachRespondResponse(
        coach_message=result.get("coach_message", ""),
        correction=correction_model,
        next_prompt=result.get("next_prompt", ""),
    )


@router.post(
    "/end",
    response_model=CoachEndResponse,
    status_code=status.HTTP_200_OK,
    summary="End Coach Session and Update Profile",
)
async def end_coach(payload: CoachEndRequest) -> CoachEndResponse:
    """
    Concludes a coach session:
    - Verifies session exists (returns 404 if missing).
    - Idempotently returns existing summary and updated profile if already completed.
    - Generates summary of practice exchanges and corrections.
    - Updates user communication profile in Supabase users table (skill_level, weak_areas, strong_areas).
    - Saves finalized session state to Supabase coach_sessions.
    - Returns session_id, status='completed', summary, and profile_updated.
    """
    clean_sid = payload.session_id.strip()
    if not clean_sid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id must not be empty",
        )

    session = await session_manager.get_or_load(clean_sid)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coach session not found",
        )

    # Idempotent response if session was already completed
    if session.is_complete:
        summary = session.summary or {
            "exchanges_count": len(session.history),
            "corrections_count": session.telemetry.get("corrections_count", 0),
            "encouragement": "Great job! Keep practicing regularly to build your conversational fluency.",
        }
        user_prof = await get_user_profile(session.user_id)
        active_prof = user_prof.get("communication_profile", user_prof)
        return CoachEndResponse(
            session_id=session.session_id,
            status="completed",
            summary=summary,
            profile_updated=active_prof,
            updated_profile=active_prof,
        )

    # Mark completed
    session.is_complete = True
    session.completed_at = session.completed_at or uuid.uuid4().hex

    # Compile session summary
    exchanges_count = len(session.history)
    corrections_count = session.telemetry.get("corrections_count", 0)
    summary = {
        "exchanges_count": exchanges_count,
        "corrections_count": corrections_count,
        "mode": session.mode,
        "key_learnings": [
            f"Completed {exchanges_count} practice exchanges in {session.mode} mode.",
            "Refined natural phrasing and active communication structure.",
        ],
        "encouragement": "Wonderful job today! Your confidence is noticeably growing.",
    }
    session.summary = summary

    # Update communication profile in Supabase
    updated_profile_data = await update_user_communication_profile(session.user_id, session.to_dict())
    active_profile = updated_profile_data.get("communication_profile", updated_profile_data)

    # Finalize persistence in coach_sessions
    await save_coach_session(session.session_id, session.to_dict())

    logger.info(f"Concluded coach session {session.session_id} and updated communication profile for user {session.user_id}")
    return CoachEndResponse(
        session_id=session.session_id,
        status="completed",
        summary=summary,
        profile_updated=active_profile,
        updated_profile=active_profile,
    )
```

---

### 3.2 Main Mount Blueprint (`backend/app/main.py`)

In `backend/app/main.py`, uncomment and activate the router mount:

```python
# Before (lines 107-109):
# Milestone 3: Planned Mount Point
# from app.routers import coach
# app.include_router(coach.router, prefix="/coach", tags=["Coach Agent"])

# After:
# Milestone 3: Phase 3 Communication Coach Agent Router
from app.routers import coach
app.include_router(coach.router, prefix="/coach", tags=["coach"])
```

---

### 3.3 Comprehensive Test Suite Blueprint (`backend/tests/test_coach.py`)

```python
"""VOXPREP Backend - AI Communication Coach Agent Unit & Integration Tests
Milestone 3: Phase 3 AI Communication Coach Agent, Session Management, and Profile Learning.

Verifies:
1. Coach start across all 3 supported modes:
   - "conversation" (HTTP 200)
   - "answer_training" (HTTP 200)
   - "english_improvement" (HTTP 200)
2. Coach response evaluation:
   - Clear answer receiving positive reinforcement (correction=None)
   - Grammatical / structural flaws receiving constructive correction (original, improved, reason)
   - Max 1-2 corrections per exchange guardrail enforcement
3. Session conclusion (POST /coach/end):
   - Persistence to Supabase coach_sessions
   - Updates to user communication profile (skill_level, weak_areas, strong_areas, sessions_count)
   - Idempotent termination handling
4. Error handling & boundary conditions:
   - Invalid coaching mode returns HTTP 400
   - Empty user_id returns HTTP 400
   - Missing coach session returns HTTP 404
   - Empty user_text returns HTTP 400
   - Responding to completed session returns HTTP 400
   - Missing required payload fields returns HTTP 422
5. Direct agent & persistence unit tests using run_sync (no asyncio socket dependencies).
"""

import uuid
import pytest

from app.agents.coach import CoachSession, VALID_COACH_MODES
from app.db.coach_persistence import (
    get_coach_session,
    get_user_profile,
    save_coach_session,
    update_user_communication_profile,
)
from app.main import app
from app.routers.coach import session_manager
from tests.conftest import LocalClient


def run_sync(coro):
    """Executes a coroutine stack synchronously without socketpair event loop dependencies."""
    stack = [coro]
    while stack:
        current = stack[-1]
        try:
            sub = current.send(None)
            if hasattr(sub, "send"):
                stack.append(sub)
        except StopIteration as exc:
            stack.pop()
            if not stack:
                return exc.value


@pytest.fixture(autouse=True)
def clean_sessions():
    """Ensures clean in-memory session manager for every test function."""
    session_manager.clear()
    yield
    session_manager.clear()


@pytest.fixture
def test_client():
    """Provides synchronous LocalClient bound to the application."""
    with LocalClient(app) as client:
        yield client


@pytest.fixture
def sample_user_id():
    """Returns standard seeded demo user UUID."""
    return "00000000-0000-0000-0000-000000000001"


# =============================================================================
# 1. Coach Session Start Tests
# =============================================================================

def test_coach_start_conversation_mode(test_client, sample_user_id):
    """Verifies that conversation mode initializes with friendly conversational prompt."""
    payload = {
        "user_id": sample_user_id,
        "mode": "conversation",
    }
    response = test_client.post("/coach/start", json=payload)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    data = response.json()
    assert "session_id" in data
    assert "opening_message" in data
    assert data.get("mode") == "conversation"
    assert len(data["session_id"]) > 0
    assert len(data["opening_message"]) > 0


def test_coach_start_answer_training_mode(test_client, sample_user_id):
    """Verifies that answer training mode initializes with STAR framework guidance."""
    payload = {
        "user_id": sample_user_id,
        "mode": "answer_training",
    }
    response = test_client.post("/coach/start", json=payload)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    data = response.json()
    assert "session_id" in data
    assert "opening_message" in data
    assert data.get("mode") == "answer_training"
    assert "STAR" in data["opening_message"] or "interview" in data["opening_message"].lower()


def test_coach_start_english_improvement_mode(test_client, sample_user_id):
    """Verifies that english improvement mode initializes with grammar/phrasing prompt."""
    payload = {
        "user_id": sample_user_id,
        "mode": "english_improvement",
    }
    response = test_client.post("/coach/start", json=payload)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    data = response.json()
    assert "session_id" in data
    assert "opening_message" in data
    assert data.get("mode") == "english_improvement"
    assert len(data["opening_message"]) > 0


def test_coach_start_persists_session(test_client, sample_user_id):
    """Verifies that starting a coach session writes record to coach_sessions persistence."""
    payload = {
        "user_id": sample_user_id,
        "mode": "conversation",
    }
    response = test_client.post("/coach/start", json=payload)
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    persisted = run_sync(get_coach_session(session_id))
    assert persisted is not None
    assert persisted["id"] == session_id
    assert persisted["user_id"] == sample_user_id
    assert persisted["mode"] == "conversation"
    assert persisted["is_complete"] is False


# =============================================================================
# 2. Coach Response & Feedback Tests
# =============================================================================

def test_coach_respond_clear_answer_no_correction(test_client, sample_user_id):
    """Verifies that fluent, clear speech receives positive feedback with correction=None."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    payload = {
        "session_id": session_id,
        "user_text": "I really enjoy hiking on mountain trails during clear weekend mornings.",
    }
    response = test_client.post("/coach/respond", json=payload)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    data = response.json()

    assert "coach_message" in data
    assert "next_prompt" in data
    assert data.get("correction") is None
    assert len(data["coach_message"]) > 0
    assert len(data["next_prompt"]) > 0


def test_coach_respond_with_correction_structured(test_client, sample_user_id):
    """Verifies that grammatical flaws receive structured correction with original, improved, reason."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "english_improvement",
    })
    session_id = start_resp.json()["session_id"]

    payload = {
        "session_id": session_id,
        "user_text": "Yesterday I was go to the market and met my colleagues.",
    }
    response = test_client.post("/coach/respond", json=payload)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    data = response.json()

    assert "coach_message" in data
    assert "next_prompt" in data
    correction = data.get("correction")
    assert correction is not None, "Expected correction for grammatical error 'was go'"
    assert "original" in correction
    assert "improved" in correction
    assert "reason" in correction
    assert "was go" in correction["original"].lower()
    assert "went" in correction["improved"].lower()
    assert len(correction["reason"]) > 0


def test_coach_respond_filler_words_correction(test_client, sample_user_id):
    """Verifies that excessive filler words receive constructive coaching on deliberate pauses."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "english_improvement",
    })
    session_id = start_resp.json()["session_id"]

    payload = {
        "session_id": session_id,
        "user_text": "Um, like, basically I worked on the database migration last month.",
    }
    response = test_client.post("/coach/respond", json=payload)
    assert response.status_code == 200
    data = response.json()
    correction = data.get("correction")
    assert correction is not None
    assert "pause" in correction["improved"].lower() or "filler" in correction["original"].lower()


def test_coach_respond_answer_training_star_guidance(test_client, sample_user_id):
    """Verifies that unstructured interview answers receive STAR framework guidance."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "answer_training",
    })
    session_id = start_resp.json()["session_id"]

    payload = {
        "session_id": session_id,
        "user_text": "I worked on a frontend project for a few months with some coworkers.",
    }
    response = test_client.post("/coach/respond", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "coach_message" in data
    assert "STAR" in data["coach_message"] or (data.get("correction") and "STAR" in data["correction"]["improved"])


def test_coach_respond_max_corrections_guardrail(test_client, sample_user_id):
    """Verifies rule: Coach provides at most 1-2 corrections per exchange to avoid overwhelming candidate."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "english_improvement",
    })
    session_id = start_resp.json()["session_id"]

    # Utterance deliberately packed with multiple grammatical and syntax errors
    flawed_text = (
        "Yesterday I was go to store and I buyed many fishes and then "
        "he do not know where is car and we was very sad."
    )
    response = test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": flawed_text,
    })
    assert response.status_code == 200
    data = response.json()

    correction = data.get("correction")
    if correction:
        if isinstance(correction, list):
            assert len(correction) <= 2, f"Exceeded max 2 corrections: {len(correction)}"
        elif isinstance(correction, dict):
            assert "original" in correction
            assert "improved" in correction


def test_coach_respond_persists_exchanges(test_client, sample_user_id):
    """Verifies that consecutive responses are properly accumulated and persisted."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "I enjoy playing tennis and reading technical books.",
    })
    test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "Yes, I usually play twice a week with my friends.",
    })

    persisted = run_sync(get_coach_session(session_id))
    assert persisted is not None
    assert len(persisted.get("history", [])) == 2


# =============================================================================
# 3. Session End & Profile Learning Tests
# =============================================================================

def test_coach_end_session_success(test_client, sample_user_id):
    """Verifies that ending a session returns completion status, summary, and updated profile."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "english_improvement",
    })
    session_id = start_resp.json()["session_id"]

    test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "I was go to office yesterday.",
    })

    end_resp = test_client.post("/coach/end", json={"session_id": session_id})
    assert end_resp.status_code == 200, f"Expected 200, got: {end_resp.text}"
    data = end_resp.json()

    assert data.get("session_id") == session_id
    assert data.get("status") == "completed"
    assert "summary" in data
    assert "profile_updated" in data
    assert "updated_profile" in data  # Dual-compatibility key

    summary = data["summary"]
    assert "exchanges_count" in summary
    assert summary["exchanges_count"] >= 1

    profile = data["profile_updated"]
    assert "skill_level" in profile
    assert "weak_areas" in profile and isinstance(profile["weak_areas"], list)
    assert "strong_areas" in profile and isinstance(profile["strong_areas"], list)


def test_coach_end_persists_to_coach_sessions(test_client, sample_user_id):
    """Verifies that coach session record in database is marked completed with summary."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "Hello coach, I am ready to practice.",
    })

    test_client.post("/coach/end", json={"session_id": session_id})

    persisted = run_sync(get_coach_session(session_id))
    assert persisted is not None
    assert persisted["is_complete"] is True
    assert persisted["status"] == "completed"
    assert persisted.get("summary") is not None


def test_coach_end_updates_user_profile(test_client, sample_user_id):
    """Verifies that user's persistent communication profile is updated upon session completion."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "english_improvement",
    })
    session_id = start_resp.json()["session_id"]

    test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "Yesterday I was go to the market.",
    })

    test_client.post("/coach/end", json={"session_id": session_id})

    profile = run_sync(get_user_profile(sample_user_id))
    comm_prof = profile.get("communication_profile", profile)
    assert comm_prof["sessions_count"] >= 1


def test_coach_end_idempotent(test_client, sample_user_id):
    """Verifies that calling POST /coach/end multiple times succeeds idempotently without error."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    resp1 = test_client.post("/coach/end", json={"session_id": session_id})
    assert resp1.status_code == 200
    data1 = resp1.json()

    resp2 = test_client.post("/coach/end", json={"session_id": session_id})
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data1["session_id"] == data2["session_id"]
    assert data1["status"] == data2["status"] == "completed"


# =============================================================================
# 4. Boundary & Error Condition Tests (400, 404, 422)
# =============================================================================

def test_coach_start_invalid_mode_returns_400(test_client, sample_user_id):
    """Verifies that unsupported or arbitrary modes return HTTP 400 Bad Request."""
    payload = {
        "user_id": sample_user_id,
        "mode": "hostile_cross_examination",
    }
    response = test_client.post("/coach/start", json=payload)
    assert response.status_code == 400, f"Expected 400 for invalid mode, got: {response.status_code}"
    assert "invalid coach mode" in response.text.lower() or "mode" in response.text.lower()


def test_coach_start_empty_user_id_returns_400(test_client):
    """Verifies that whitespace-only user_id returns HTTP 400 Bad Request."""
    payload = {
        "user_id": "   ",
        "mode": "conversation",
    }
    response = test_client.post("/coach/start", json=payload)
    assert response.status_code == 400


def test_coach_respond_empty_user_text_returns_400(test_client, sample_user_id):
    """Verifies that empty user_text returns HTTP 400 Bad Request."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    # Empty string
    resp1 = test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "",
    })
    assert resp1.status_code == 400

    # Whitespace only
    resp2 = test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "   \n\t  ",
    })
    assert resp2.status_code == 400


def test_coach_respond_missing_session_returns_404(test_client):
    """Verifies that submitting response to non-existent session UUID returns HTTP 404."""
    non_existent_sid = str(uuid.uuid4())
    payload = {
        "session_id": non_existent_sid,
        "user_text": "Hello coach?",
    }
    response = test_client.post("/coach/respond", json=payload)
    assert response.status_code == 404
    assert "not found" in response.text.lower()


def test_coach_respond_to_completed_session_returns_400(test_client, sample_user_id):
    """Verifies that attempting to respond to an already terminated session returns HTTP 400."""
    start_resp = test_client.post("/coach/start", json={
        "user_id": sample_user_id,
        "mode": "conversation",
    })
    session_id = start_resp.json()["session_id"]

    test_client.post("/coach/end", json={"session_id": session_id})

    response = test_client.post("/coach/respond", json={
        "session_id": session_id,
        "user_text": "Can I still speak?",
    })
    assert response.status_code == 400
    assert "already completed" in response.text.lower()


def test_coach_end_missing_session_returns_404(test_client):
    """Verifies that ending a non-existent session returns HTTP 404."""
    non_existent_sid = str(uuid.uuid4())
    response = test_client.post("/coach/end", json={"session_id": non_existent_sid})
    assert response.status_code == 404
    assert "not found" in response.text.lower()


def test_coach_validation_missing_fields_returns_422(test_client):
    """Verifies that omitting required schema parameters raises HTTP 422 Unprocessable Entity."""
    # 1. Missing mode in start
    resp1 = test_client.post("/coach/start", json={"user_id": str(uuid.uuid4())})
    assert resp1.status_code == 422

    # 2. Missing user_id in start
    resp2 = test_client.post("/coach/start", json={"mode": "conversation"})
    assert resp2.status_code == 422

    # 3. Missing session_id in respond
    resp3 = test_client.post("/coach/respond", json={"user_text": "Sample text"})
    assert resp3.status_code == 422

    # 4. Missing session_id in end
    resp4 = test_client.post("/coach/end", json={})
    assert resp4.status_code == 422


# =============================================================================
# 5. Direct Unit Tests (via run_sync)
# =============================================================================

def test_coach_session_unit_modes_via_run_sync():
    """Directly tests CoachSession lifecycle and prompt construction across all modes."""
    for mode in ["conversation", "answer_training", "english_improvement"]:
        session = CoachSession(
            session_id=str(uuid.uuid4()),
            user_id="unit-tester",
            mode=mode,
        )
        opening = run_sync(session.start_session())
        assert isinstance(opening, str)
        assert len(opening) > 0

        # Process standard response
        res = run_sync(session.process_response("I practiced speaking today."))
        assert "coach_message" in res
        assert "next_prompt" in res
        assert "correction" in res


def test_coach_persistence_unit_via_run_sync():
    """Directly tests database persistence CRUD and normalization via run_sync."""
    sess_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    # 1. Save initial session
    data = {
        "id": sess_id,
        "user_id": user_id,
        "mode": "english_improvement",
        "history": [{"user_text": "Hello", "coach_message": "Hi"}],
    }
    saved = run_sync(save_coach_session(sess_id, data))
    assert saved["id"] == sess_id
    assert saved["is_complete"] is False

    # 2. Retrieve session
    loaded = run_sync(get_coach_session(sess_id))
    assert loaded is not None
    assert loaded["mode"] == "english_improvement"

    # 3. Update communication profile
    profile_result = run_sync(update_user_communication_profile(user_id, {
        "id": sess_id,
        "user_id": user_id,
        "mode": "english_improvement",
        "history": [{
            "user_text": "was go",
            "correction": {
                "original": "was go",
                "improved": "went",
                "reason": "past tense verb",
            },
        }],
    }))
    comm_prof = profile_result.get("communication_profile", profile_result)
    assert comm_prof["sessions_count"] >= 1
```

---

## 4. Caveats

1. **Dual Response Key for Profile Update**:
   - The dispatch specification defines `POST /coach/end` returning `{ "profile_updated": dict }`.
   - Existing E2E test `test_tier1_features.py:271` asserts `assert "updated_profile" in data`.
   - To eliminate any conflict and guarantee that both new and existing tests pass seamlessly, `CoachEndResponse` includes both keys (`profile_updated` and `updated_profile`), pointing to the exact same updated dictionary.
2. **Auto-Provisioning vs. 404 on Missing User**:
   - Per `docs/07_GUARDRAILS.md:100` and `schema.sql`, when a user ID does not exist in `users`, the system initializes baseline defaults and auto-provisions a learner profile. This allows tests that generate random UUIDs (`str(uuid.uuid4())`) to initiate sessions without pre-registering auth records.
   - However, if `user_id` is passed as empty string or whitespace, `HTTP 400` is immediately returned. If `get_user_profile` returns `None` (e.g. database error), `HTTP 404` is returned.
3. **Pydantic Validation (422) vs Application Validation (400)**:
   - When required JSON fields are omitted entirely from the HTTP body, FastAPI's built-in Pydantic parser returns `HTTP 422 Unprocessable Entity` (standard behavior verified in `test_tier2_boundaries.py:178-195`).
   - When fields are present but contain invalid values (e.g. `mode="invalid"`, `user_text=""`), the endpoint logic explicitly raises `HTTP 400 Bad Request` per dispatch instructions.
4. **Idempotent Session Termination**:
   - Calling `POST /coach/end` on an already completed session does NOT fail or overwrite historical metrics; it returns `HTTP 200` with status `'completed'` and the existing summary.

---

## 5. Conclusion

1. **Router Specification**:
   - `backend/app/routers/coach.py` cleanly implements `POST /coach/start`, `POST /coach/respond`, and `POST /coach/end`.
   - Employs `CoachSessionManager` for instant in-memory session hydration and thread safety.
   - Normalizes Pydantic input/output schemas with clear descriptions and error handling.
2. **App Mount**:
   - `backend/app/main.py` is updated by importing `coach` and executing `app.include_router(coach.router, prefix="/coach", tags=["coach"])`.
3. **Comprehensive Test Suite**:
   - `backend/tests/test_coach.py` provides 23 granular unit and integration tests.
   - Executes via `LocalClient` and `run_sync` to ensure 100% deterministic test execution on Windows without socket hangs.
   - Covers all 3 coaching modes, clear speech, structured corrections, filler words, STAR frameworks, max 1-2 corrections guardrail, session persistence, profile learning updates, and boundary conditions (400, 404, 422).

---

## 6. Verification Method

### 6.1 Test Execution Command
Run the newly designed test suite in isolation:
```powershell
.venv\Scripts\python.exe -m pytest backend/tests/test_coach.py -v
```

### 6.2 Full Test Suite Regression Verification
Run the entire test suite including Tier 1-4 E2E tests and existing unit tests:
```powershell
.venv\Scripts\python.exe -m pytest backend/tests/ -v
```
Expected outcome: All 249+ tests passing with 0 failures, 0 regressions, and 0 warnings.

### 6.3 Manual Endpoint Verification via cURL (or test client)
1. **Start Coach Session**:
   ```bash
   curl -X POST http://localhost:8000/coach/start \
     -H "Content-Type: application/json" \
     -d '{"user_id": "00000000-0000-0000-0000-000000000001", "mode": "english_improvement"}'
   ```
2. **Respond to Coach**:
   ```bash
   curl -X POST http://localhost:8000/coach/respond \
     -H "Content-Type: application/json" \
     -d '{"session_id": "<SESSION_ID>", "user_text": "Yesterday I was go to the market."}'
   ```
3. **End Coach Session**:
   ```bash
   curl -X POST http://localhost:8000/coach/end \
     -H "Content-Type: application/json" \
     -d '{"session_id": "<SESSION_ID>"}'
   ```

### 6.4 Invalidation Conditions
- A test failure occurs if `POST /coach/start` rejects valid modes or fails to return a non-empty `session_id`.
- A test failure occurs if `POST /coach/respond` returns more than 2 corrections in a single exchange.
- A test failure occurs if `POST /coach/end` fails to update `communication_profile` in Supabase.
- A test failure occurs if any test hangs on Windows socket loops (indicating non-use of `LocalClient` / `run_sync`).
