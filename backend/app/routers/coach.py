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
from typing import Any, Dict, List, Optional
import uuid

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
        user_prof = await get_user_profile(session.user_id) if session.user_id else {}
        active_prof = user_prof.get("communication_profile", user_prof) if user_prof else session.user_profile
        return CoachEndResponse(
            session_id=session.session_id,
            status="completed",
            summary=summary,
            profile_updated=active_prof,
            updated_profile=active_prof,
        )

    # Conclude session via agent method
    end_result = await session.end_session()

    logger.info(
        f"Concluded coach session {session.session_id} and updated communication profile for user {session.user_id}"
    )
    return CoachEndResponse(
        session_id=session.session_id,
        status="completed",
        summary=end_result.get("summary", {}),
        profile_updated=end_result.get("updated_profile", {}),
        updated_profile=end_result.get("updated_profile", {}),
    )
