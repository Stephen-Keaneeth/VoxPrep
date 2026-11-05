"""Pydantic data models for interview evaluation reports.
Milestone 2: Phase 2 AI Interviewer Agent and Session Management.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DimensionScores(BaseModel):
    """Rubric evaluation scores scaled 1.0 to 10.0."""
    relevance: float = Field(..., ge=1.0, le=10.0, description="Answer addressed the prompt directly")
    clarity: float = Field(..., ge=1.0, le=10.0, description="Logical structure and clear articulation")
    depth: float = Field(..., ge=1.0, le=10.0, description="Technical depth and understanding")
    examples: float = Field(..., ge=1.0, le=10.0, description="Specific evidence and real-world scenarios")


class QuestionBreakdownItem(BaseModel):
    """Per-question evaluation entry."""
    question: str = Field(..., description="The interview question posed to candidate")
    answer_summary: str = Field(..., description="Concise synopsis of the candidate's response")
    scores: DimensionScores = Field(..., description="Rubric dimension scores for this answer")
    feedback: str = Field(..., description="Specific, constructive feedback on this response")


class InterviewReport(BaseModel):
    """Comprehensive performance evaluation report generated upon interview completion."""
    overall_score: float = Field(..., ge=1.0, le=10.0, description="Composite score scaled 1.0 to 10.0")
    dimension_scores: DimensionScores = Field(..., description="Average scores across the 4 dimensions (1-10)")
    strengths: List[str] = Field(..., min_length=1, max_length=5, description="Key candidate strengths observed")
    areas_for_improvement: List[str] = Field(..., min_length=1, max_length=5, description="Constructive improvement targets")
    question_breakdown: List[QuestionBreakdownItem] = Field(default_factory=list, description="Detailed per-question breakdown")
    action_items: List[str] = Field(default_factory=list, description="Concrete next steps for candidate improvement")
    coach_recommendation: Optional[str] = Field("Interview Answer Training", description="Recommended coach practice mode")
    summary: Optional[str] = Field("", description="Executive summary of the candidate's performance")

    # Backward compatibility fields for frontend / existing test contracts
    weaknesses: Optional[List[str]] = Field(None, description="Alias for areas_for_improvement")
    improvement_tips: Optional[List[str]] = Field(None, description="Alias for action_items")

    def model_post_init(self, __context: Any) -> None:
        """Ensure backward compatibility aliases mirror primary fields."""
        if self.weaknesses is None:
            self.weaknesses = list(self.areas_for_improvement)
        if self.improvement_tips is None:
            self.improvement_tips = list(self.action_items)
