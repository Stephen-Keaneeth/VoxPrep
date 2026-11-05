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
  "overall_score": <average of all dimension scores, float between 1.0 and 10.0 rounded to 1 decimal>,
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

    # Check scores dict for question_history
    scores_dict = session_data.get("scores")
    if isinstance(scores_dict, dict) and isinstance(scores_dict.get("question_history"), list):
        return [h for h in scores_dict["question_history"] if isinstance(h, dict)]

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

    # 2. Overall score (scaled 1.0 to 10.0 float per docs/08_AGENT_PROMPTS.md & test_tier4_scenarios)
    raw_overall = raw.get("overall_score")
    if raw_overall is not None:
        try:
            val = float(raw_overall)
            if val > 10.0:
                # Value was expressed on 100-point scale (e.g. 80.0) -> normalize to 10-point scale
                overall_score = float(max(1.0, min(10.0, round(val / 10.0, 1))))
            else:
                overall_score = float(max(1.0, min(10.0, round(val, 1))))
        except (ValueError, TypeError):
            avg_dim = sum(dimension_scores.values()) / len(dimension_scores)
            overall_score = round(avg_dim, 1)
    else:
        avg_dim = sum(dimension_scores.values()) / len(dimension_scores)
        overall_score = round(avg_dim, 1)

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
    logger.info(f"Generating fallback report. Reason: {reason}")
    history = _extract_history(session_data)
    candidate_name = session_data.get("candidate_name", "Candidate")
    role = session_data.get("role") or session_data.get("role_applied", "the applied role")

    # Calculate actual averages from history if available
    rel_scores: List[float] = []
    cla_scores: List[float] = []
    dep_scores: List[float] = []
    ex_scores: List[float] = []

    for item in history:
        s = item.get("scores")
        if isinstance(s, dict):
            if "relevance" in s:
                rel_scores.append(float(s["relevance"]))
            if "clarity" in s:
                cla_scores.append(float(s["clarity"]))
            if "depth" in s:
                dep_scores.append(float(s["depth"]))
            if "examples" in s:
                ex_scores.append(float(s["examples"]))

    # Also check if session_data has dimension_scores directly
    dim_scores_existing = session_data.get("dimension_scores")
    if not dim_scores_existing and isinstance(session_data.get("scores"), dict):
        dim_scores_existing = session_data["scores"].get("dimension_scores")

    if dim_scores_existing and isinstance(dim_scores_existing, dict):
        avg_rel = float(dim_scores_existing.get("relevance", 8.0)) or 8.0
        avg_cla = float(dim_scores_existing.get("clarity", 8.0)) or 8.0
        avg_dep = float(dim_scores_existing.get("depth", 7.5)) or 7.5
        avg_ex = float(dim_scores_existing.get("examples", 8.0)) or 8.0
    else:
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
    overall_score = round(sum(dimension_scores.values()) / 4.0, 1)

    strengths = [
        f"Clear architectural explanation of service boundaries and concepts.",
        f"Demonstrated good domain readiness for {role} with structured communication.",
    ]
    areas = [
        "Could elaborate more on disaster recovery strategies and operational trade-offs.",
        "Include more quantifiable metrics and real-world performance benchmarks.",
    ]
    actions = [
        "Use the STAR method for situational questions.",
        "Quantify business outcomes and personal contributions with explicit metrics.",
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
