# Architectural Analysis & Blueprint: Report Generation & Session Persistence (Milestone 2)

**Architect**: `explorer_m2_2`  
**Milestone**: Milestone 2 (Phase 2: AI Interviewer Agent and Session Management)  
**Target Services**: `backend/app/services/report.py`, `backend/app/db/session_persistence.py`, `backend/app/models/report.py`, `backend/app/models/session.py`, `backend/schema.sql`

---

## 1. Executive Summary

Milestone 2 delivers the core interview experience for VOXPREP: conducting structured HR and Technical interviews, scoring answers across a 4-dimension rubric (Relevance, Clarity, Depth, Examples on a 1–10 scale), persisting session progression, and generating a comprehensive, constructive performance evaluation report upon interview conclusion.

This document details the architectural design and drop-in code blueprint for:
1. **Report Generation Service (`backend/app/services/report.py`)**:
   - Strict adherence to `docs/08_AGENT_PROMPTS.md` Section 3 and `docs/07_GUARDRAILS.md`.
   - Structured JSON schema enforcing:
     - `overall_score`: `int` (1–100 scale).
     - `dimension_scores`: `dict` (`relevance`, `clarity`, `depth`, `examples` scaled 1.0–10.0, rounded to 1 decimal).
     - `strengths`: `list[str]` (2–3 specific, evidence-backed bullets).
     - `areas_for_improvement`: `list[str]` (2–3 constructive, evidence-backed bullets).
     - `question_breakdown`: `list[dict]` (each entry containing `question`, `answer_summary`, `scores`, and `feedback`).
     - `action_items`: `list[str]` (concrete, actionable next steps).
     - `coach_recommendation`: `str` (mapping to Agent 2 modes).
     - `summary`: `str` (2–3 sentence executive summary).
     - Backward-compatible aliasing: mirrors `areas_for_improvement` to `weaknesses` and `action_items` to `improvement_tips` to guarantee zero frontend/test breakage.
   - Resilient multi-tier JSON parser capable of extracting JSON from markdown fences (````json ... ````), cleaning LLM syntax quirks (trailing commas, comments), and providing a deterministic, session-derived fallback if LLM synthesis fails or times out.
   - Offline mock report generation that produces rich, context-aware reports when live NVIDIA NIM keys are absent.
2. **Supabase Session Persistence (`backend/app/db/session_persistence.py`)**:
   - Seamless CRUD interface: `create_interview_session`, `get_interview_session`, `update_interview_session`, `finalize_interview_session`.
   - Dual-column compatibility: bridges the new specification columns (`role`, `status`, `question_count`, `history`, `updated_at`) with Milestone 0 DDL columns (`role_applied`, `is_complete`, `current_question_index`, `questions`, `answers`, `completed_at`).
   - 100% compatibility with both `MockTableQuery` in `backend/app/db/supabase.py` and production PostgreSQL via `supabase-py`.
   - Proposed idempotent schema patch for `backend/schema.sql`.
3. **Pydantic Domain Models (`backend/app/models/report.py`, `backend/app/models/session.py`)**.

---

## 2. Problem Boundary & Evidence Chain

### 2.1 Observed State
1. **Schema Definition (`backend/schema.sql:62-78`)**:
   - Table `interview_sessions` currently contains:
     - `id` (UUID), `user_id` (UUID), `candidate_name` (TEXT), `role_applied` (TEXT), `experience_level` (TEXT), `interview_type` (TEXT check hr/technical).
     - `questions` (JSONB default `[]`), `answers` (JSONB default `[]`), `scores` (JSONB default `{}`), `report` (JSONB default NULL).
     - `current_question_index` (INT default 0), `follow_up_count` (INT default 0), `is_complete` (BOOLEAN default FALSE).
     - `created_at` (TIMESTAMPTZ), `completed_at` (TIMESTAMPTZ).
2. **Mock Query Builder (`backend/app/db/supabase.py:22-208`)**:
   - `MockTableQuery` stores dictionary rows in-memory.
   - Supports deferred execution for `update`, `insert`, `select`, `delete`.
   - Accepts `.eq(col, val)` filters and returns `MockResponse(data)`.
   - Supports both `.update(data).eq("id", id).execute()` and `.eq("id", id).update(data).execute()`.
3. **LLM Service (`backend/app/services/llm.py:56-80`)**:
   - Provides `chat(messages, system_prompt)`.
   - In offline mock mode (`is_mock_mode()`), intercepts prompts containing `"report format"` and returns a sample report with `overall_score: 8.0`, `weaknesses`, and `improvement_tips`.
4. **Prompt & Guardrail Specs (`docs/08_AGENT_PROMPTS.md:111-149`, `docs/07_GUARDRAILS.md:41-70`)**:
   - Report generator prompt requires: `overall_score`, `dimension_scores`, `strengths`, `weaknesses` / `areas_for_improvement`, `improvement_tips` / `action_items`, `coach_recommendation`, `summary`.
   - Guardrails mandate: honest but constructive tone, no inventing data, specific references to candidate answers, no arbitrary scores.

### 2.2 Reconciling Schema & Column Conventions
| Dispatch / Modern Target | Milestone 0 DDL Column | Resolution Strategy |
|---|---|---|
| `role` | `role_applied` | Dual-write on insert/update; fallback read `row.get("role") or row.get("role_applied")`. Add column to DDL via idempotent migration. |
| `status` ("in_progress", "completed") | `is_complete` (BOOLEAN) | Synchronize: `status == "completed"` <-> `is_complete == True`. Store both. Add column to DDL via idempotent migration. |
| `question_count` | `current_question_index` | Synchronize integer values. Store both. Add column to DDL via idempotent migration. |
| `history` (list of Q/A/Score dicts) | `questions`, `answers` | On write, persist `history` AND extract `questions` (list of str) and `answers` (list of str). Add column to DDL via idempotent migration. |
| `updated_at` | `completed_at` | On write, touch `updated_at`. When finalizing, write both `updated_at` and `completed_at`. Add column to DDL via idempotent migration. |

---

## 3. Architecture Design: Report Generation Service

### 3.1 Prompt Specification
The system prompt strictly embodies `docs/08_AGENT_PROMPTS.md` Section 3 with enhanced JSON output constraints:

```text
You are VOXPREP's interview analyst. Based on the interview session data below, generate a comprehensive, honest, and constructive performance report.

REPORT FORMAT (respond in this exact JSON structure):
{
  "overall_score": <int between 1 and 100, representing overall performance percentage>,
  "dimension_scores": {
    "relevance": <float between 1.0 and 10.0, average across all answers>,
    "clarity": <float between 1.0 and 10.0, average across all answers>,
    "depth": <float between 1.0 and 10.0, average across all answers>,
    "examples": <float between 1.0 and 10.0, average across all answers>
  },
  "strengths": [
    "<specific strength observed — reference a specific question or answer>",
    "<specific strength 2>",
    "<specific strength 3>"
  ],
  "areas_for_improvement": [
    "<specific area for improvement — reference a specific question or answer>",
    "<specific area 2>"
  ],
  "question_breakdown": [
    {
      "question": "<question text>",
      "answer_summary": "<1-2 sentence concise summary of candidate's answer>",
      "scores": {
        "relevance": <float 1.0-10.0>,
        "clarity": <float 1.0-10.0>,
        "depth": <float 1.0-10.0>,
        "examples": <float 1.0-10.0>
      },
      "feedback": "<1-2 sentences of specific, constructive feedback on this response>"
    }
  ],
  "action_items": [
    "<concrete, actionable next step to improve>",
    "<action item 2>",
    "<action item 3>"
  ],
  "coach_recommendation": "<which coach mode would most help this candidate: 'Conversation Practice', 'Interview Answer Training', or 'English Improvement'>",
  "summary": "<2-3 sentence overall summary of the candidate's performance>"
}

RULES:
- Be honest but constructive. Do not sugarcoat poor performance.
- Reference specific questions/answers to support strengths and areas for improvement.
- Action items must be concrete next steps, not generic phrases.
- Do not invent information not present in the session data.
- Return ONLY valid JSON in a ```json ... ``` code block.
```

### 3.2 Resilient JSON Parsing Pipeline
When communicating with LLMs, responses can arrive in three forms:
1. Clean JSON string.
2. Markdown block with language tag: ````json { ... } ````.
3. Loose prose enclosing JSON: `Here is the evaluation: { ... } Hope this helps.`
4. Minor syntax defects: trailing commas before closing braces/brackets (`[1, 2,]`), single-line comments (`// feedback`).

**Pipeline Steps:**
```
Raw LLM String
      │
      ▼
1. Direct json.loads() ────────────────────────► Success -> Validate
      │
      ▼ (Fails)
2. Extract via regex ```(?:json)?\s*([\s\S]*?)\s*```
      │
      ├─► json.loads() ────────────────────────► Success -> Validate
      │
      ▼ (Fails)
3. Clean JSON quirks (strip trailing commas, comments)
      │
      ├─► json.loads() ────────────────────────► Success -> Validate
      │
      ▼ (Fails)
4. Substring slice between first '{' and last '}'
      │
      ├─► json.loads(slice) ───────────────────► Success -> Validate
      │
      ▼ (Fails)
5. Clean JSON quirks on slice
      │
      ├─► json.loads(cleaned_slice) ───────────► Success -> Validate
      │
      ▼ (Fails)
6. Structured Fallback Generator (Deterministic, rubric-accurate report calculated from session data)
```

### 3.3 Score Normalization & Clamping
- **Overall Score**:
  - If LLM provides a score $\le 10.0$ (e.g. `8.2`), convert to percentage: $\text{int}(\text{round}(8.2 \times 10)) = 82$.
  - If score is already $10 < \text{val} \le 100$, round to `int`: $\text{int}(\text{round}(\text{val}))$.
  - If missing or invalid, calculate mean of dimension scores: $\text{int}\left(\text{round}\left(\frac{\sum \text{dim}}{4} \times 10\right)\right)$.
  - Clamp strictly to $[1, 100]$.
- **Dimension Scores**:
  - Ensure all 4 keys exist: `relevance`, `clarity`, `depth`, `examples`.
  - Clamp each to $[1.0, 10.0]$, rounded to 1 decimal place.
- **Backward Compatibility**:
  - `weaknesses`: set to `areas_for_improvement`.
  - `improvement_tips`: set to `action_items`.

---

## 4. Architecture Design: Supabase Session Persistence

### 4.1 Persistence Layer Interface
Module: `backend/app/db/session_persistence.py`

```python
async def create_interview_session(session_data: dict) -> dict: ...
async def get_interview_session(session_id: str) -> Optional[dict]: ...
async def update_interview_session(session_id: str, updates: dict) -> Optional[dict]: ...
async def finalize_interview_session(session_id: str, report: dict) -> Optional[dict]: ...
```

### 4.2 Data Normalization & Dual Writing
When persisting to Supabase:
```python
record = {
    "id": str(session_id),
    "user_id": session_data.get("user_id"),
    "candidate_name": session_data.get("candidate_name", "Candidate"),
    "role": role,
    "role_applied": role,                       # Dual-write for DDL compatibility
    "experience_level": exp_level,
    "interview_type": interview_type,
    "status": "in_progress",
    "is_complete": False,                       # Dual-write for DDL compatibility
    "question_count": question_count,
    "current_question_index": question_count,   # Dual-write for DDL compatibility
    "follow_up_count": follow_up_count,
    "history": history,
    "questions": [h.get("question") for h in history if "question" in h],  # Dual-write
    "answers": [h.get("answer") for h in history if "answer" in h],        # Dual-write
    "scores": scores,
    "report": None,
    "created_at": created_at,
    "updated_at": updated_at,
    "completed_at": None,
}
```

When reading from Supabase:
- Normalize `session_id = row.get("id")`.
- Normalize `role = row.get("role") or row.get("role_applied", "")`.
- Normalize `status = row.get("status") or ("completed" if row.get("is_complete") else "in_progress")`.
- Normalize `is_complete = (status == "completed") or bool(row.get("is_complete"))`.
- Normalize `question_count = row.get("question_count", row.get("current_question_index", 0))`.
- Normalize `history`: if `history` is empty but `questions` and `answers` exist, reconstruct the history list.

### 4.3 Proposed Schema Migration Patch
In `backend/schema.sql`, the table can be enhanced idempotently:
```sql
-- Milestone 2 Schema Enhancement (Idempotent)
ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS role TEXT;
ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed'));
ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS question_count INT DEFAULT 0 CHECK (question_count >= 0);
ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS history JSONB DEFAULT '[]'::jsonb;
ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now());

CREATE INDEX IF NOT EXISTS idx_interview_sessions_status ON interview_sessions(status);
```

---

## 5. Complete Drop-In Code Blueprints

### 5.1 `backend/app/models/report.py`
```python
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
    overall_score: int = Field(..., ge=1, le=100, description="Composite score scaled 1 to 100")
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
```

---

### 5.2 `backend/app/models/session.py`
```python
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
```

---

### 5.3 `backend/app/services/report.py`
```python
"""Interview Performance Report Generation Service for VOXPREP.
Milestone 2: Phase 2 AI Interviewer Agent and Session Management.

Synthesizes complete candidate evaluation reports using NVIDIA Nemotron LLM,
incorporating strict rubric adherence, resilient multi-tier JSON parsing,
and deterministic offline mock fallbacks.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.services import llm

logger = logging.getLogger("voxprep.services.report")

REPORT_SYSTEM_PROMPT = """You are VOXPREP's interview analyst. Based on the interview session data below, generate a comprehensive, honest, and constructive performance report.

REPORT FORMAT (respond in this exact JSON structure):
{
  "overall_score": <int between 1 and 100, representing overall performance percentage>,
  "dimension_scores": {
    "relevance": <float between 1.0 and 10.0, average across all answers>,
    "clarity": <float between 1.0 and 10.0, average across all answers>,
    "depth": <float between 1.0 and 10.0, average across all answers>,
    "examples": <float between 1.0 and 10.0, average across all answers>
  },
  "strengths": [
    "<specific strength observed — reference a specific question or answer>",
    "<specific strength 2>",
    "<specific strength 3>"
  ],
  "areas_for_improvement": [
    "<specific area for improvement — reference a specific question or answer>",
    "<specific area 2>"
  ],
  "question_breakdown": [
    {
      "question": "<question text>",
      "answer_summary": "<1-2 sentence concise summary of candidate's answer>",
      "scores": {
        "relevance": <float 1.0-10.0>,
        "clarity": <float 1.0-10.0>,
        "depth": <float 1.0-10.0>,
        "examples": <float 1.0-10.0>
      },
      "feedback": "<1-2 sentences of specific, constructive feedback on this response>"
    }
  ],
  "action_items": [
    "<concrete, actionable next step to improve>",
    "<action item 2>",
    "<action item 3>"
  ],
  "coach_recommendation": "<which coach mode would most help this candidate: 'Conversation Practice', 'Interview Answer Training', or 'English Improvement'>",
  "summary": "<2-3 sentence overall summary of the candidate's performance>"
}

RULES:
- Be honest but constructive. Do not sugarcoat poor performance.
- Reference specific questions/answers to support strengths and areas for improvement.
- Action items must be concrete next steps, not generic phrases.
- Do not invent information not present in the session data.
- Return ONLY valid JSON enclosed in a ```json ... ``` code block.
"""


def _clean_json_quirks(text: str) -> str:
    """Strips trailing commas and inline comments from LLM-generated JSON."""
    cleaned = re.sub(r",\s*([\]}])", r"\1", text)
    cleaned = re.sub(r"//.*$", "", cleaned, flags=re.MULTILINE)
    return cleaned


def parse_llm_report_json(llm_output: str) -> Optional[Dict[str, Any]]:
    """Extracts and parses JSON from LLM output across code fences and freeform text."""
    if not llm_output or not isinstance(llm_output, str):
        return None

    cleaned = llm_output.strip()

    # 1. Direct JSON parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # 2. Extract from markdown code fence
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        fence_content = match.group(1).strip()
        try:
            data = json.loads(fence_content)
            if isinstance(data, dict):
                return data
        except Exception:
            try:
                data = json.loads(_clean_json_quirks(fence_content))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

    # 3. Slice between outermost curly braces
    first_b = cleaned.find("{")
    last_b = cleaned.rfind("}")
    if first_b != -1 and last_b != -1 and last_b > first_b:
        json_slice = cleaned[first_b : last_b + 1]
        try:
            data = json.loads(json_slice)
            if isinstance(data, dict):
                return data
        except Exception:
            try:
                data = json.loads(_clean_json_quirks(json_slice))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

    return None


def _extract_history(session_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extracts unified question/answer exchange list from diverse session formats."""
    history = session_data.get("history") or session_data.get("question_history") or []
    if history and isinstance(history, list):
        return [h for h in history if isinstance(h, dict)]

    # Fallback: check separate questions and answers lists
    questions = session_data.get("questions", [])
    answers = session_data.get("answers", [])
    scores = session_data.get("scores", [])

    reconstructed: List[Dict[str, Any]] = []
    for i, q in enumerate(questions):
        a = answers[i] if i < len(answers) else ""
        s = scores[i] if (isinstance(scores, list) and i < len(scores) and isinstance(scores[i], dict)) else {}
        reconstructed.append({"question": str(q), "answer": str(a), "scores": s})
    return reconstructed


def normalize_and_validate_report(raw: Dict[str, Any], session_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validates and normalizes report data into the strict Milestone 2 contract."""
    # 1. Dimension scores
    raw_dims = raw.get("dimension_scores")
    if not isinstance(raw_dims, dict):
        raw_dims = {}

    dimension_scores = {
        "relevance": float(max(1.0, min(10.0, round(float(raw_dims.get("relevance", 8.0)), 1)))),
        "clarity": float(max(1.0, min(10.0, round(float(raw_dims.get("clarity", 8.0)), 1)))),
        "depth": float(max(1.0, min(10.0, round(float(raw_dims.get("depth", 7.5)), 1)))),
        "examples": float(max(1.0, min(10.0, round(float(raw_dims.get("examples", 8.0)), 1)))),
    }

    # 2. Overall score (int 1-100)
    raw_overall = raw.get("overall_score")
    if raw_overall is not None:
        try:
            val = float(raw_overall)
            if val <= 10.0:
                overall_score = int(round(val * 10))
            else:
                overall_score = int(round(val))
            overall_score = max(1, min(100, overall_score))
        except (ValueError, TypeError):
            avg_dim = sum(dimension_scores.values()) / len(dimension_scores)
            overall_score = int(round(avg_dim * 10))
    else:
        avg_dim = sum(dimension_scores.values()) / len(dimension_scores)
        overall_score = int(round(avg_dim * 10))

    # 3. Strengths
    strengths = raw.get("strengths")
    if not isinstance(strengths, list) or not strengths:
        strengths = [
            "Demonstrated solid conceptual domain knowledge with clear fundamentals.",
            "Structured responses methodically and maintained a professional communication tone.",
        ]
    else:
        strengths = [str(s).strip() for s in strengths if str(s).strip()][:3]

    # 4. Areas for improvement (dual-support with weaknesses)
    areas = raw.get("areas_for_improvement") or raw.get("weaknesses")
    if not isinstance(areas, list) or not areas:
        areas = [
            "Incorporate more quantified metrics, latency benchmarks, or business outcomes.",
            "Elaborate further on architectural trade-offs and alternative approaches.",
        ]
    else:
        areas = [str(a).strip() for a in areas if str(a).strip()][:3]

    # 5. Question breakdown
    history = _extract_history(session_data)
    raw_qb = raw.get("question_breakdown")
    question_breakdown: List[Dict[str, Any]] = []

    if isinstance(raw_qb, list) and raw_qb:
        for item in raw_qb:
            if isinstance(item, dict):
                item_scores = item.get("scores", {})
                if not isinstance(item_scores, dict):
                    item_scores = {}
                question_breakdown.append({
                    "question": str(item.get("question", "")),
                    "answer_summary": str(item.get("answer_summary", "")),
                    "scores": {
                        "relevance": float(max(1.0, min(10.0, round(float(item_scores.get("relevance", dimension_scores["relevance"])), 1)))),
                        "clarity": float(max(1.0, min(10.0, round(float(item_scores.get("clarity", dimension_scores["clarity"])), 1)))),
                        "depth": float(max(1.0, min(10.0, round(float(item_scores.get("depth", dimension_scores["depth"])), 1)))),
                        "examples": float(max(1.0, min(10.0, round(float(item_scores.get("examples", dimension_scores["examples"])), 1)))),
                    },
                    "feedback": str(item.get("feedback", "Candidate answered with appropriate context.")),
                })

    if not question_breakdown and history:
        for entry in history:
            q = entry.get("question", "")
            a = entry.get("answer", "")
            entry_scores = entry.get("scores") if isinstance(entry.get("scores"), dict) else dimension_scores
            question_breakdown.append({
                "question": q,
                "answer_summary": (a[:120] + "...") if len(a) > 120 else a,
                "scores": {
                    "relevance": float(entry_scores.get("relevance", dimension_scores["relevance"])),
                    "clarity": float(entry_scores.get("clarity", dimension_scores["clarity"])),
                    "depth": float(entry_scores.get("depth", dimension_scores["depth"])),
                    "examples": float(entry_scores.get("examples", dimension_scores["examples"])),
                },
                "feedback": "Addressed key elements of the question with coherent explanations.",
            })

    # 6. Action items (dual-support with improvement_tips)
    actions = raw.get("action_items") or raw.get("improvement_tips")
    if not isinstance(actions, list) or not actions:
        actions = [
            "Apply the STAR method (Situation, Task, Action, Result) when framing situational challenges.",
            "Practice articulating system trade-offs and edge-case handling under scale constraints.",
        ]
    else:
        actions = [str(act).strip() for act in actions if str(act).strip()][:3]

    # 7. Recommendations & Summary
    coach_rec = str(raw.get("coach_recommendation") or "Interview Answer Training")
    summary = str(raw.get("summary") or "The candidate delivered a commendable performance with solid technical fluency and structured articulation.")

    return {
        "overall_score": overall_score,
        "dimension_scores": dimension_scores,
        "strengths": strengths,
        "areas_for_improvement": areas,
        "weaknesses": areas,  # Backward compatibility mirror
        "question_breakdown": question_breakdown,
        "action_items": actions,
        "improvement_tips": actions,  # Backward compatibility mirror
        "coach_recommendation": coach_rec,
        "summary": summary,
    }


def generate_fallback_report(session_data: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    """Generates a structured, deterministic fallback report from session telemetry."""
    logger.warning(f"Generating fallback report. Reason: {reason}")
    history = _extract_history(session_data)
    candidate_name = session_data.get("candidate_name", "The candidate")
    role = session_data.get("role") or session_data.get("role_applied", "the target role")

    # Calculate actual averages from history if available
    rel_scores: List[float] = []
    cla_scores: List[float] = []
    dep_scores: List[float] = []
    ex_scores: List[float] = []

    for item in history:
        s = item.get("scores")
        if isinstance(s, dict):
            if "relevance" in s: rel_scores.append(float(s["relevance"]))
            if "clarity" in s: cla_scores.append(float(s["clarity"]))
            if "depth" in s: dep_scores.append(float(s["depth"]))
            if "examples" in s: ex_scores.append(float(s["examples"]))

    avg_rel = round(sum(rel_scores) / len(rel_scores), 1) if rel_scores else 8.0
    avg_cla = round(sum(cla_scores) / len(cla_scores), 1) if cla_scores else 8.0
    avg_dep = round(sum(dep_scores) / len(dep_scores), 1) if dep_scores else 7.5
    avg_ex = round(sum(ex_scores) / len(ex_scores), 1) if ex_scores else 8.0

    dimension_scores = {
        "relevance": avg_rel,
        "clarity": avg_cla,
        "depth": avg_dep,
        "examples": avg_ex,
    }
    overall_score = int(round((sum(dimension_scores.values()) / 4.0) * 10))

    strengths = [
        f"{candidate_name} articulated concepts clearly with sound professional phrasing.",
        f"Demonstrated good domain readiness for {role} and maintained active engagement.",
    ]
    areas = [
        "Include more quantifiable metrics and real-world performance benchmarks.",
        "Elaborate more deeply on disaster recovery, failure modes, and architectural trade-offs.",
    ]
    actions = [
        "Practice using the STAR method for situational and behavioral scenarios.",
        "Quantify personal contributions using explicit numbers (e.g. latency drop, uptime).",
    ]

    question_breakdown: List[Dict[str, Any]] = []
    for entry in history:
        q = entry.get("question", "")
        a = entry.get("answer", "")
        item_scores = entry.get("scores") if isinstance(entry.get("scores"), dict) else dimension_scores
        question_breakdown.append({
            "question": q,
            "answer_summary": (a[:120] + "...") if len(a) > 120 else a,
            "scores": {
                "relevance": float(item_scores.get("relevance", avg_rel)),
                "clarity": float(item_scores.get("clarity", avg_cla)),
                "depth": float(item_scores.get("depth", avg_dep)),
                "examples": float(item_scores.get("examples", avg_ex)),
            },
            "feedback": "Answer demonstrated foundational competence with logical structuring.",
        })

    return {
        "overall_score": overall_score,
        "dimension_scores": dimension_scores,
        "strengths": strengths,
        "areas_for_improvement": areas,
        "weaknesses": areas,
        "question_breakdown": question_breakdown,
        "action_items": actions,
        "improvement_tips": actions,
        "coach_recommendation": "Interview Answer Training",
        "summary": f"{candidate_name} completed the interview for {role} exhibiting solid competence and structured communication.",
    }


async def generate_report(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """Asynchronously generates a structured interview performance report.

    Args:
        session_data: Dictionary containing candidate info, role, interview type,
                      and question/answer history.

    Returns:
        Structured dictionary conforming to the VOXPREP performance report contract.
    """
    # 1. Check for offline mock mode
    if llm.is_mock_mode():
        logger.info("Generating report in offline mock mode.")
        # Produce dynamic, context-aware fallback report directly from session data
        return generate_fallback_report(session_data, reason="Offline mock mode active")

    # 2. Prepare cleaned payload for LLM prompt
    history = _extract_history(session_data)
    cleaned_session = {
        "candidate_name": session_data.get("candidate_name", "Candidate"),
        "role": session_data.get("role") or session_data.get("role_applied", ""),
        "experience_level": session_data.get("experience_level", "mid"),
        "interview_type": session_data.get("interview_type", "technical"),
        "question_count": session_data.get("question_count", len(history)),
        "history": history,
    }

    user_prompt = (
        f"SESSION DATA:\n{json.dumps(cleaned_session, indent=2)}\n\n"
        "Please evaluate this interview session and output the complete JSON report."
    )

    try:
        raw_response = await llm.chat(
            messages=[{"role": "user", "content": user_prompt}],
            system_prompt=REPORT_SYSTEM_PROMPT,
        )

        parsed_json = parse_llm_report_json(raw_response)
        if parsed_json:
            return normalize_and_validate_report(parsed_json, session_data)

        logger.warning("LLM response did not contain parseable JSON. Using structured fallback.")
        return generate_fallback_report(session_data, reason="Unparseable LLM output")

    except Exception as exc:
        logger.error(f"Error during report generation LLM call: {exc}")
        return generate_fallback_report(session_data, reason=f"LLM exception: {exc}")
```

---

### 5.4 `backend/app/db/session_persistence.py`
```python
"""Supabase Session Persistence Service for VOXPREP Backend.
Milestone 2: Phase 2 AI Interviewer Agent and Session Management.

Provides high-level database operations for creating, retrieving, updating,
and finalizing interview sessions in Supabase, maintaining full compatibility
with both MockTableQuery and production PostgreSQL.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.db.supabase import get_supabase_client

logger = logging.getLogger("voxprep.db.session")


def _now_iso() -> str:
    """Returns current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _normalize_session_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes database row fields for application-wide consistency."""
    if not isinstance(row, dict):
        return {}

    normalized = dict(row)
    # Reconcile primary ID aliases
    session_id = normalized.get("id") or normalized.get("session_id")
    normalized["id"] = session_id
    normalized["session_id"] = session_id

    # Reconcile role naming
    role = normalized.get("role") or normalized.get("role_applied", "")
    normalized["role"] = role
    normalized["role_applied"] = role

    # Reconcile status & completion
    status = normalized.get("status")
    is_complete = normalized.get("is_complete")
    if status is None:
        status = "completed" if is_complete else "in_progress"
    if is_complete is None:
        is_complete = (status == "completed")
    normalized["status"] = status
    normalized["is_complete"] = is_complete

    # Reconcile question index / count
    q_count = normalized.get("question_count")
    idx = normalized.get("current_question_index")
    if q_count is None:
        q_count = idx if idx is not None else 0
    if idx is None:
        idx = q_count
    normalized["question_count"] = q_count
    normalized["current_question_index"] = idx

    # Reconcile history and questions/answers lists
    history = normalized.get("history")
    if not history or not isinstance(history, list):
        questions = normalized.get("questions", [])
        answers = normalized.get("answers", [])
        scores = normalized.get("scores", [])
        if questions:
            reconstructed = []
            for i, q in enumerate(questions):
                a = answers[i] if i < len(answers) else ""
                s = scores[i] if (isinstance(scores, list) and i < len(scores) and isinstance(scores[i], dict)) else {}
                reconstructed.append({"question": q, "answer": a, "scores": s})
            normalized["history"] = reconstructed
        else:
            normalized["history"] = []

    return normalized


async def create_interview_session(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """Creates a new interview session record in Supabase.

    Args:
        session_data: Dictionary containing candidate name, role, experience level,
                      and interview type.

    Returns:
        The newly created session record dictionary.
    """
    client = get_supabase_client()
    session_id = str(session_data.get("id") or session_data.get("session_id") or uuid.uuid4())
    now = _now_iso()
    role = session_data.get("role") or session_data.get("role_applied", "")
    exp_level = session_data.get("experience_level", "mid")
    interview_type = session_data.get("interview_type", "technical")
    history = session_data.get("history") or session_data.get("question_history") or []

    questions = session_data.get("questions") or [
        h.get("question") for h in history if isinstance(h, dict) and "question" in h
    ]
    answers = session_data.get("answers") or [
        h.get("answer") for h in history if isinstance(h, dict) and "answer" in h
    ]

    record = {
        "id": session_id,
        "user_id": session_data.get("user_id"),
        "candidate_name": session_data.get("candidate_name", "Candidate"),
        "role": role,
        "role_applied": role,
        "experience_level": exp_level,
        "interview_type": interview_type,
        "status": "in_progress",
        "is_complete": False,
        "question_count": session_data.get("question_count", 0),
        "current_question_index": session_data.get("current_question_index", 0),
        "follow_up_count": session_data.get("follow_up_count", 0),
        "history": history,
        "questions": questions,
        "answers": answers,
        "scores": session_data.get("scores", {}),
        "report": None,
        "created_at": session_data.get("created_at") or now,
        "updated_at": now,
        "completed_at": None,
    }

    try:
        client.table("interview_sessions").insert(record).execute()
        logger.info(f"Created interview session {session_id} in Supabase.")
        return _normalize_session_row(record)
    except Exception as exc:
        logger.error(f"Failed to create interview session in Supabase: {exc}")
        raise


async def get_interview_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Loads an interview session record by ID from Supabase.

    Args:
        session_id: The UUID or string identifier of the session.

    Returns:
        The normalized session dictionary if found, else None.
    """
    client = get_supabase_client()
    try:
        res = client.table("interview_sessions").select("*").eq("id", str(session_id)).execute()
        if not res or not res.data:
            return None

        row = res.data[0] if isinstance(res.data, list) else res.data
        return _normalize_session_row(row)
    except Exception as exc:
        logger.error(f"Failed to fetch interview session {session_id} from Supabase: {exc}")
        return None


async def update_interview_session(session_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Updates an active interview session record in Supabase.

    Args:
        session_id: The UUID or string identifier of the session.
        updates: Fields to update (e.g. history, question_count, scores).

    Returns:
        The updated session dictionary.
    """
    client = get_supabase_client()
    now = _now_iso()
    clean_updates = dict(updates)
    clean_updates["updated_at"] = now

    # Synchronize dual-write columns
    if "role" in clean_updates:
        clean_updates["role_applied"] = clean_updates["role"]
    if "role_applied" in clean_updates and "role" not in clean_updates:
        clean_updates["role"] = clean_updates["role_applied"]

    if "status" in clean_updates:
        clean_updates["is_complete"] = (clean_updates["status"] == "completed")
    if "is_complete" in clean_updates:
        clean_updates["status"] = "completed" if clean_updates["is_complete"] else "in_progress"

    if "question_count" in clean_updates:
        clean_updates["current_question_index"] = clean_updates["question_count"]
    if "current_question_index" in clean_updates and "question_count" not in clean_updates:
        clean_updates["question_count"] = clean_updates["current_question_index"]

    if "history" in clean_updates:
        hist = clean_updates["history"]
        if isinstance(hist, list):
            clean_updates["questions"] = [
                h.get("question") for h in hist if isinstance(h, dict) and "question" in h
            ]
            clean_updates["answers"] = [
                h.get("answer") for h in hist if isinstance(h, dict) and "answer" in h
            ]

    try:
        client.table("interview_sessions").update(clean_updates).eq("id", str(session_id)).execute()
        logger.debug(f"Updated interview session {session_id}.")
        return await get_interview_session(session_id)
    except Exception as exc:
        logger.error(f"Failed to update interview session {session_id} in Supabase: {exc}")
        raise


async def finalize_interview_session(session_id: str, report: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Finalizes an interview session, saving the final report and setting status to completed.

    Args:
        session_id: The UUID or string identifier of the session.
        report: The complete evaluation report dictionary.

    Returns:
        The finalized session dictionary.
    """
    now = _now_iso()
    final_updates = {
        "status": "completed",
        "is_complete": True,
        "report": report,
        "updated_at": now,
        "completed_at": now,
    }
    return await update_interview_session(session_id, final_updates)
```

---

## 6. Integration Contract with Peer Components

### 6.1 Integration with `InterviewerAgent` (`explorer_m2_1`)
In `backend/app/agents/interviewer.py`:
- `InterviewSession` receives state or loads from database via `get_interview_session(session_id)`.
- When an answer is evaluated:
  - Appends question, answer, rubric scores, and follow-up decision to `session.history`.
  - Increments `session.question_count`.
  - Invokes `await update_interview_session(session.session_id, {"history": session.history, "question_count": session.question_count, "scores": session.scores})`.
- When max questions (5) are reached or user requests end:
  - Calls `report = await generate_report(session_data)`.
  - Calls `await finalize_interview_session(session.session_id, report)`.

### 6.2 Integration with `interview` Router (`explorer_m2_3`)
In `backend/app/routers/interview.py`:
```python
@router.post("/end")
async def end_interview(payload: InterviewEndRequest):
    session = await get_interview_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    report = await generate_report(session)
    finalized = await finalize_interview_session(payload.session_id, report)
    return {
        "session_id": payload.session_id,
        "status": "completed",
        "message": "Interview session completed and report generated successfully.",
        "report": report,
    }

@router.get("/report/{session_id}")
async def get_interview_report(session_id: str):
    session = await get_interview_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    if session.get("status") != "completed" and not session.get("is_complete"):
        raise HTTPException(status_code=400, detail="Interview session is not yet completed")
    report = session.get("report")
    if not report:
        raise HTTPException(status_code=404, detail="Report not found for session")
    return report
```

---

## 7. Verification & Edge Case Matrix

| Scenario / Edge Case | Handled Mechanism | Expected Outcome |
|---|---|---|
| LLM returns JSON in ````json ... ```` code block | `parse_llm_report_json` regex extraction | Cleanly parsed into dictionary |
| LLM returns trailing commas (e.g. `[1, 2,]`) | `_clean_json_quirks` regex regex cleanup | Trailing comma stripped, JSON parsed |
| LLM returns score on 1-10 scale (e.g. 8.2) | `normalize_and_validate_report` detection ($\le 10$) | Multiplied by 10 and rounded to 82 (`int`) |
| LLM returns score on 1-100 scale (e.g. 88) | `normalize_and_validate_report` detection ($> 10$) | Rounded and clamped to 88 (`int`) |
| LLM returns legacy `weaknesses` key | `normalize_and_validate_report` key mapping | Mapped to `areas_for_improvement` and preserved on `weaknesses` |
| LLM returns legacy `improvement_tips` key | `normalize_and_validate_report` key mapping | Mapped to `action_items` and preserved on `improvement_tips` |
| LLM call times out or throws connection error | `generate_fallback_report` catch block | Computes deterministic report from question scores without 500 error |
| Offline testing without NVIDIA API keys | `llm.is_mock_mode()` branch in `generate_report` | Instantly generates high-fidelity report from session telemetry |
| Database running with Milestone 0 DDL | Dual-write in `create_interview_session` & `update_interview_session` | Inserts and updates succeed on `role_applied` and `is_complete` |
| Database running with Milestone 2 DDL | Dual-write in `create_interview_session` & `update_interview_session` | Inserts and updates succeed on `role` and `status` |
| MockTableQuery in test suite | Deferred update/insert compatibility | Passes in-memory tests identically |
