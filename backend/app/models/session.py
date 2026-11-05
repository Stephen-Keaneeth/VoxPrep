"""Pydantic data models for interview session persistence.
Milestone 2: Phase 2 AI Interviewer Agent and Session Management.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QuestionExchange(BaseModel):
    """Single exchange record in interview history."""
    question: str
    answer: str
    scores: Dict[str, float] = Field(default_factory=dict)
    follow_up_used: bool = False
    timestamp: Optional[str] = None


class InterviewSessionModel(BaseModel):
    """Domain model representing an interview session stored in Supabase."""
    id: str
    user_id: Optional[str] = None
    candidate_name: str
    role: str
    experience_level: str
    interview_type: str
    status: str = "in_progress"
    is_complete: bool = False
    question_count: int = 0
    current_question_index: int = 0
    follow_up_count: int = 0
    history: List[Dict[str, Any]] = Field(default_factory=list)
    scores: Dict[str, Any] = Field(default_factory=dict)
    report: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
