"""Supabase Session Persistence Service for VOXPREP Backend.
Milestone 2: Phase 2 AI Interviewer Agent and Session Management.

Provides high-level database operations for creating, retrieving, updating,
and finalizing interview sessions in Supabase, maintaining full compatibility
with both MockTableQuery and production PostgreSQL.
"""

from datetime import datetime, timezone
import logging
import threading
from typing import Any, Dict, List, Optional
import uuid

from app.db.supabase import get_supabase_client

logger = logging.getLogger("voxprep.db.session")

# In-process backup cache ensuring session continuity across test runs
_in_memory_sessions: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()


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
    exp_level = session_data.get("experience_level", "mid-level")
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
        "session_id": session_id,
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

    # Store in memory cache
    with _cache_lock:
        _in_memory_sessions[session_id] = record

    try:
        client.table("interview_sessions").insert(record).execute()
        logger.info(f"Created interview session {session_id} in Supabase.")
    except Exception as exc:
        logger.warning(f"Notice: Supabase insert returned notice or failed: {exc}. Retaining in memory cache.")

    return _normalize_session_row(record)


async def get_interview_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Loads an interview session record by ID from Supabase or memory cache.

    Args:
        session_id: The UUID or string identifier of the session.

    Returns:
        The normalized session dictionary if found, else None.
    """
    sid = str(session_id)
    with _cache_lock:
        if sid in _in_memory_sessions:
            return _normalize_session_row(_in_memory_sessions[sid])

    client = get_supabase_client()
    try:
        res = client.table("interview_sessions").select("*").eq("id", sid).execute()
        if res and res.data:
            row = res.data[0] if isinstance(res.data, list) else res.data
            normalized = _normalize_session_row(row)
            with _cache_lock:
                _in_memory_sessions[sid] = normalized
            return normalized
    except Exception as exc:
        logger.warning(f"Failed to fetch interview session {sid} from Supabase: {exc}")

    return None


async def update_interview_session(session_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Updates an active interview session record in Supabase and memory cache.

    Args:
        session_id: The UUID or string identifier of the session.
        updates: Fields to update (e.g. history, question_count, scores).

    Returns:
        The updated session dictionary.
    """
    sid = str(session_id)
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

    # Update in memory cache first
    with _cache_lock:
        if sid in _in_memory_sessions:
            _in_memory_sessions[sid].update(clean_updates)
        else:
            _in_memory_sessions[sid] = dict(clean_updates)
            _in_memory_sessions[sid]["id"] = sid

    # Update Supabase
    client = get_supabase_client()
    try:
        client.table("interview_sessions").update(clean_updates).eq("id", sid).execute()
        logger.debug(f"Updated interview session {sid} in Supabase.")
    except Exception as exc:
        logger.warning(f"Failed to update interview session {sid} in Supabase: {exc}")

    return await get_interview_session(sid)


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
