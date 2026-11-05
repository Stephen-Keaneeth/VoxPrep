"""VOXPREP Backend API - Interviewer Agent Router
Milestone 2: Phase 2 AI Interviewer Agent and Session Management.

Exposes REST endpoints for the interview lifecycle:
- POST /interview/start: Initializes session and returns opening greeting
- POST /interview/respond: Processes candidate answer, rubric scoring, and progression
- POST /interview/end: Terminates session, triggers report generation, and persists to Supabase
- GET /interview/report/{session_id}: Retrieves generated performance report

Authoritative references:
- docs/03_PHASE_PLAN.md (Phase 2 Deliverables)
- docs/05_ACCEPTANCE_CRITERIA.md (Phase 2 Acceptance Criteria)
- docs/06_TASK_DIVISION.md (Member A router responsibilities)
- docs/07_GUARDRAILS.md (Interviewer Rules, Boundaries, and Fallbacks)
- docs/08_AGENT_PROMPTS.md (Agent 1 HR & Technical Prompts + Report Schema)
"""

import copy
import logging
import threading
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.agents.interviewer import InterviewSession, VALID_INTERVIEW_TYPES
from app.db.session_persistence import (
    create_interview_session,
    finalize_interview_session,
    get_interview_session,
    update_interview_session,
)
from app.services.report import generate_report

logger = logging.getLogger("voxprep.routers.interview")

router = APIRouter(tags=["Interviewer Agent"])


# =============================================================================
# Request and Response Models
# =============================================================================

class InterviewStartRequest(BaseModel):
    """Payload to start a new interview session."""
    candidate_name: str = Field(..., min_length=1, description="Candidate's full name")
    role: str = Field(..., min_length=1, description="Target job title or role")
    experience_level: str = Field(..., min_length=1, description="Candidate's seniority level")
    interview_type: str = Field(..., description="Track: 'hr' or 'technical'")
    user_id: Optional[str] = Field(None, description="Optional Supabase user UUID")

    @field_validator("interview_type")
    @classmethod
    def validate_interview_type(cls, v: str) -> str:
        val = v.lower().strip()
        if val not in VALID_INTERVIEW_TYPES:
            raise ValueError(f"Invalid interview_type '{v}'. Must be 'hr' or 'technical'.")
        return val


class InterviewStartResponse(BaseModel):
    """Response returned upon successful interview initialization."""
    session_id: str = Field(..., description="Unique UUID identifying the interview session")
    opening_message: str = Field(..., description="Spoken introduction and first interview question")


class InterviewRespondRequest(BaseModel):
    """Payload containing candidate's verbal or text answer."""
    session_id: str = Field(..., min_length=1, description="UUID of the active interview session")
    answer_text: str = Field(..., description="Candidate's answer text")


class InterviewRespondResponse(BaseModel):
    """Interviewer agent's evaluated response and next conversational prompt."""
    spoken_response: str = Field(..., description="Interviewer's spoken response or next question")
    is_complete: bool = Field(..., description="True if interview session has concluded (5 questions reached)")
    follow_up_or_next: str = Field(..., description="'follow_up' if probing further, 'next' if moving to next question")
    question_index: int = Field(..., description="0-indexed current question number")
    current_question_index: int = Field(..., description="Alias for question_index for backward compatibility")
    total_questions: int = Field(default=5, description="Total core questions in interview (5 for MVP)")


class InterviewEndRequest(BaseModel):
    """Payload to conclude an interview session."""
    session_id: str = Field(..., min_length=1, description="Session UUID to terminate")


class InterviewEndResponse(BaseModel):
    """Response returned upon terminating an interview and generating the report."""
    session_id: str
    status: str = "completed"
    message: str = "Interview session ended successfully and report generated."
    report: Dict[str, Any]


# =============================================================================
# In-Memory Session Cache & Persistence Bridge
# =============================================================================

class InterviewSessionManager:
    """Session coordinator managing active InterviewSession instances with persistence backing."""

    def __init__(self):
        self._active_sessions: Dict[str, InterviewSession] = {}
        self._lock = threading.Lock()

    async def get_or_load(self, session_id: str) -> Optional[InterviewSession]:
        """Retrieves session from memory cache or restores from persistence layer."""
        with self._lock:
            if session_id in self._active_sessions:
                return self._active_sessions[session_id]

        row = await get_interview_session(session_id)
        if not row:
            return None

        session = InterviewSession.from_dict(row)
        with self._lock:
            self._active_sessions[session_id] = session
        return session

    def register(self, session: InterviewSession) -> None:
        """Stores session in active memory cache."""
        with self._lock:
            self._active_sessions[session.session_id] = session

    def clear(self) -> None:
        """Clears memory cache for isolated test runs."""
        with self._lock:
            self._active_sessions.clear()


session_manager = InterviewSessionManager()


# =============================================================================
# Router Endpoints
# =============================================================================

@router.post(
    "/start",
    response_model=InterviewStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Start an Interview Session",
)
async def start_interview(payload: InterviewStartRequest) -> InterviewStartResponse:
    """
    Initializes a new interview session:
    - Validates candidate name, role, experience level, and interview type ('hr' or 'technical').
    - Generates a unique UUID session ID.
    - Instantiates the interviewer agent persona.
    - Persists the initial session state to Supabase `interview_sessions`.
    - Returns session_id and verbal opening message.
    """
    session_id = str(uuid.uuid4())
    session = InterviewSession(
        session_id=session_id,
        candidate_name=payload.candidate_name.strip(),
        role=payload.role.strip(),
        experience_level=payload.experience_level.strip(),
        interview_type=payload.interview_type.strip().lower(),
        user_id=payload.user_id,
    )

    opening_message = await session.start_session()
    session_manager.register(session)

    # Persist initial session record to Supabase
    await create_interview_session(session.to_dict())

    logger.info(
        f"Initialized interview session {session_id} ({payload.interview_type}) for {payload.candidate_name}"
    )
    return InterviewStartResponse(session_id=session_id, opening_message=opening_message)


@router.post(
    "/respond",
    response_model=InterviewRespondResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Candidate Answer",
)
async def respond_interview(payload: InterviewRespondRequest) -> InterviewRespondResponse:
    """
    Processes candidate's verbal/text answer:
    - Verifies valid session existence (returns 404 if not found).
    - Checks completion state.
    - Evaluates answer against 4-dimension rubric (Relevance, Clarity, Depth, Examples).
    - Decides whether to ask 1 follow-up or move to next question (max 5 questions total).
    - Updates and persists session state to Supabase.
    - Returns interviewer's spoken response and progression state.
    """
    session = await session_manager.get_or_load(payload.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found",
        )

    result = await session.process_answer(payload.answer_text)

    # Persist updated session state to Supabase
    await update_interview_session(session.session_id, session.to_dict())

    return InterviewRespondResponse(
        spoken_response=result["spoken_response"],
        is_complete=result["is_complete"],
        follow_up_or_next=result["follow_up_or_next"],
        question_index=session.current_question_index,
        current_question_index=session.current_question_index,
        total_questions=5,
    )


@router.post(
    "/end",
    response_model=InterviewEndResponse,
    status_code=status.HTTP_200_OK,
    summary="End Interview Session and Generate Report",
)
async def end_interview(payload: InterviewEndRequest) -> InterviewEndResponse:
    """
    Terminates an interview session:
    - Verifies valid session existence (returns 404 if not found).
    - Marks `is_complete = True`.
    - Generates the comprehensive evaluation report via Nemotron LLM (or mock fallback).
    - Saves final report, scores, and completion timestamp to Supabase `interview_sessions`.
    - Returns completion confirmation and report.
    """
    session = await session_manager.get_or_load(payload.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found",
        )

    session.is_complete = True
    if not session.report:
        report = await generate_report(session.to_dict())
        session.report = report

    # Finalize in Supabase
    await finalize_interview_session(session.session_id, session.report)

    logger.info(f"Concluded interview session {payload.session_id} and generated report.")
    return InterviewEndResponse(
        session_id=session.session_id,
        status="completed",
        message="Interview session ended successfully and report generated.",
        report=session.report,
    )


@router.get(
    "/report/{session_id}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Retrieve Interview Performance Report",
)
async def get_interview_report(session_id: str) -> Dict[str, Any]:
    """
    Retrieves the generated interview report:
    - Returns 404 if session does not exist.
    - Returns 400 if session is still in progress / not yet completed.
    - Returns full JSON report when session is completed.
    """
    session = await session_manager.get_or_load(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found",
        )

    if not session.is_complete or not session.report:
        # Check if session is completed in database but report needs generation
        if session.is_complete and not session.report:
            report = await generate_report(session.to_dict())
            session.report = report
            await finalize_interview_session(session.session_id, report)
            return report

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview session is not yet completed. Complete the interview before retrieving the report.",
        )

    return session.report
