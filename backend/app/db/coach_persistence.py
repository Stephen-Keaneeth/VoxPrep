"""Supabase Coach Session Persistence & Profile Learning Service for VOXPREP Backend.
Milestone 3: Phase 3 AI Communication Coach Agent.

Provides high-level database operations for:
- Saving and retrieving coach sessions (save_coach_session, get_coach_session)
- Fetching user communication profiles with defaults (get_user_profile)
- Adaptive profile learning and updating (update_user_communication_profile)
- Dual-write and dual-read reconciliation with MockSupabaseClient and PostgreSQL
"""

import copy
from datetime import datetime, timezone
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.db.supabase import get_supabase_client

logger = logging.getLogger("voxprep.db.coach")

# In-process thread-safe caches ensuring continuity across test runs and network isolation
_in_memory_coach_sessions: Dict[str, Dict[str, Any]] = {}
_in_memory_user_profiles: Dict[str, Dict[str, Any]] = {}
_coach_lock = threading.Lock()

VALID_COACH_MODES = {"conversation", "answer_training", "english_improvement"}
VALID_SKILL_LEVELS = {"beginner", "intermediate", "advanced"}


def _now_iso() -> str:
    """Returns current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _normalize_coach_session_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes database row fields for application-wide consistency.

    Reconciles:
    - id <-> session_id
    - exchanges <-> history
    - is_complete <-> status
    - created_at <-> started_at
    - corrections
    """
    if not isinstance(row, dict):
        return {}

    normalized = dict(row)

    # 1. ID Aliasing
    session_id = str(normalized.get("id") or normalized.get("session_id") or "")
    normalized["id"] = session_id
    normalized["session_id"] = session_id

    # 2. Status & Completion
    status = normalized.get("status")
    is_complete = normalized.get("is_complete")
    if status is None:
        status = "completed" if is_complete else "in_progress"
    if is_complete is None:
        is_complete = (status == "completed")
    normalized["status"] = status
    normalized["is_complete"] = is_complete

    # 3. Exchanges & History
    history = normalized.get("history")
    exchanges = normalized.get("exchanges")
    if history is None and exchanges is not None:
        history = exchanges if isinstance(exchanges, list) else []
    elif exchanges is None and history is not None:
        exchanges = history if isinstance(history, list) else []
    elif history is None and exchanges is None:
        history = []
        exchanges = []

    normalized["history"] = history
    normalized["exchanges"] = exchanges

    # 4. Corrections Extraction
    corrections = normalized.get("corrections")
    if not isinstance(corrections, list):
        corrections = []
        for ex in (history if isinstance(history, list) else []):
            if isinstance(ex, dict) and ex.get("correction"):
                corr = ex["correction"]
                if isinstance(corr, dict) and corr.get("original") and corr.get("improved"):
                    corrections.append(corr)
    normalized["corrections"] = corrections

    # 5. Timestamps
    created_at = normalized.get("created_at") or normalized.get("started_at") or _now_iso()
    normalized["created_at"] = created_at
    normalized["started_at"] = created_at
    if "updated_at" not in normalized or not normalized["updated_at"]:
        normalized["updated_at"] = _now_iso()

    # 6. Mode
    mode = normalized.get("mode", "conversation")
    if mode not in VALID_COACH_MODES:
        mode = "conversation"
    normalized["mode"] = mode

    return normalized


def _normalize_user_profile(user_row: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Normalizes user profile dictionary ensuring both top-level keys and
    nested communication_profile are consistently available.
    """
    row = dict(user_row) if isinstance(user_row, dict) else {}
    comm_profile = row.get("communication_profile")
    if not isinstance(comm_profile, dict):
        comm_profile = {}

    skill_level = (
        comm_profile.get("skill_level")
        or row.get("skill_level")
        or "intermediate"
    )
    if skill_level not in VALID_SKILL_LEVELS:
        skill_level = "intermediate"

    weak_areas = (
        comm_profile.get("weak_areas")
        or row.get("weak_areas")
        or []
    )
    if not isinstance(weak_areas, list):
        weak_areas = []

    strong_areas = (
        comm_profile.get("strong_areas")
        or row.get("strong_areas")
        or []
    )
    if not isinstance(strong_areas, list):
        strong_areas = []

    sessions_count = int(
        comm_profile.get("sessions_count")
        or row.get("sessions_count")
        or 0
    )

    canonical_comm_profile = {
        "skill_level": skill_level,
        "weak_areas": list(weak_areas),
        "strong_areas": list(strong_areas),
        "sessions_count": sessions_count,
        "last_mode": comm_profile.get("last_mode") or row.get("last_mode"),
        "last_session_id": comm_profile.get("last_session_id") or row.get("last_session_id"),
        "last_updated": comm_profile.get("last_updated") or row.get("last_updated") or _now_iso(),
    }

    return {
        "id": user_id,
        "user_id": user_id,
        "email": row.get("email") or f"user_{str(user_id)[:8]}@voxprep.ai",
        "name": row.get("name") or "Alex Candidate",
        "skill_level": skill_level,
        "weak_areas": list(weak_areas),
        "strong_areas": list(strong_areas),
        "sessions_count": sessions_count,
        "communication_profile": canonical_comm_profile,
        "created_at": row.get("created_at") or _now_iso(),
        "updated_at": row.get("updated_at") or _now_iso(),
    }


# =============================================================================
# Core Session Persistence Operations
# =============================================================================

async def save_coach_session(session_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts or updates a coach session record in Supabase and memory cache.

    Args:
        session_id: The UUID or string identifier of the coach session.
        data: Dictionary of session state (mode, history, corrections, status, etc.).

    Returns:
        The normalized session record dictionary.
    """
    sid = str(session_id)
    now = _now_iso()
    raw = dict(data)
    raw["id"] = sid
    raw["session_id"] = sid

    normalized = _normalize_coach_session_row(raw)
    normalized["updated_at"] = now

    # 1. Update in-memory cache first for immediate consistency
    with _coach_lock:
        if sid in _in_memory_coach_sessions:
            _in_memory_coach_sessions[sid].update(normalized)
        else:
            _in_memory_coach_sessions[sid] = dict(normalized)

    # 2. Persist to Supabase
    client = get_supabase_client()
    db_payload = {
        "id": sid,
        "user_id": normalized.get("user_id"),
        "mode": normalized.get("mode"),
        "exchanges": normalized.get("exchanges", []),
        "history": normalized.get("history", []),
        "corrections": normalized.get("corrections", []),
        "summary": normalized.get("summary"),
        "status": normalized.get("status", "in_progress"),
        "is_complete": normalized.get("is_complete", False),
        "created_at": normalized.get("created_at", now),
        "started_at": normalized.get("started_at", now),
        "updated_at": now,
        "completed_at": normalized.get("completed_at"),
    }

    try:
        # Check if record exists
        existing = client.table("coach_sessions").select("id").eq("id", sid).execute()
        if existing and existing.data:
            client.table("coach_sessions").update(db_payload).eq("id", sid).execute()
            logger.debug(f"Updated coach session {sid} in Supabase.")
        else:
            client.table("coach_sessions").insert(db_payload).execute()
            logger.info(f"Inserted coach session {sid} in Supabase.")
    except Exception as exc:
        # Fallback for baseline schema without extended ALTER TABLE columns
        logger.warning(
            f"Extended coach_sessions write notice: {exc}. Retrying with core baseline columns."
        )
        core_payload = {
            "id": sid,
            "user_id": normalized.get("user_id"),
            "mode": normalized.get("mode"),
            "exchanges": normalized.get("exchanges", []),
            "summary": normalized.get("summary"),
            "is_complete": normalized.get("is_complete", False),
            "created_at": normalized.get("created_at", now),
            "completed_at": normalized.get("completed_at"),
        }
        try:
            client.table("coach_sessions").update(core_payload).eq("id", sid).execute()
        except Exception:
            try:
                client.table("coach_sessions").insert(core_payload).execute()
            except Exception as final_exc:
                logger.warning(
                    f"Notice: Supabase write failed ({final_exc}). Session safely retained in memory cache."
                )

    return normalized


async def get_coach_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Loads a coach session record by ID from memory cache or Supabase.

    Args:
        session_id: The UUID or string identifier of the session.

    Returns:
        Normalized session dictionary if found, else None.
    """
    sid = str(session_id)
    with _coach_lock:
        if sid in _in_memory_coach_sessions:
            return _normalize_coach_session_row(_in_memory_coach_sessions[sid])

    client = get_supabase_client()
    try:
        res = client.table("coach_sessions").select("*").eq("id", sid).execute()
        if res and res.data:
            row = res.data[0] if isinstance(res.data, list) else res.data
            normalized = _normalize_coach_session_row(row)
            with _coach_lock:
                _in_memory_coach_sessions[sid] = normalized
            return normalized
    except Exception as exc:
        logger.warning(f"Failed to fetch coach session {sid} from Supabase: {exc}")

    return None


# =============================================================================
# User Profile Operations & Profile Learning
# =============================================================================

async def get_user_profile(user_id: str) -> Dict[str, Any]:
    """Retrieves user communication profile from Supabase users table.
    If the user does not exist, provisions and persists a default baseline profile.

    Args:
        user_id: UUID or string identifier of the user.

    Returns:
        Normalized user profile dictionary.
    """
    uid = str(user_id)

    # 1. Check in-memory cache
    with _coach_lock:
        if uid in _in_memory_user_profiles:
            return _normalize_user_profile(_in_memory_user_profiles[uid], uid)

    # 2. Query Supabase
    client = get_supabase_client()
    try:
        res = client.table("users").select("*").eq("id", uid).execute()
        if res and res.data:
            row = res.data[0] if isinstance(res.data, list) else res.data
            profile = _normalize_user_profile(row, uid)
            with _coach_lock:
                _in_memory_user_profiles[uid] = profile
            return profile
    except Exception as exc:
        logger.warning(f"Failed to load user {uid} from Supabase: {exc}")

    # 3. Default baseline profile for new or unauthenticated users
    now = _now_iso()
    default_record = {
        "id": uid,
        "email": f"user_{uid[:8]}@voxprep.ai",
        "name": "Alex Candidate",
        "communication_profile": {
            "skill_level": "intermediate",
            "weak_areas": [],
            "strong_areas": [],
            "sessions_count": 0,
            "last_updated": now,
        },
        "skill_level": "intermediate",
        "weak_areas": [],
        "strong_areas": [],
        "created_at": now,
        "updated_at": now,
    }

    normalized = _normalize_user_profile(default_record, uid)

    with _coach_lock:
        _in_memory_user_profiles[uid] = normalized

    try:
        client.table("users").insert(default_record).execute()
        logger.info(f"Provisioned baseline profile for user {uid} in Supabase.")
    except Exception as exc:
        logger.debug(f"Notice: Supabase insert of baseline user returned notice: {exc}")

    return normalized


def classify_correction(correction: Dict[str, Any]) -> str:
    """Classifies a correction object into a canonical communication area tag."""
    reason = str(correction.get("reason", "")).lower()
    original = str(correction.get("original", "")).lower()
    improved = str(correction.get("improved", "")).lower()
    text = f"{reason} {original} {improved}"

    if any(k in text for k in ["filler", "um", "uh", "like", "you know", "kind of", "sort of", "crutch"]):
        return "filler words"
    if any(k in text for k in ["star", "situation", "task", "action", "result", "structure", "structured", "framework", "rambling"]):
        return "STAR structure"
    if any(k in text for k in ["concise", "conciseness", "brief", "brevity", "long-winded", "wordy", "too long", "shorter"]):
        return "conciseness"
    if any(k in text for k in ["grammar", "tense", "past tense", "present tense", "plural", "singular", "subject-verb", "preposition", "syntax"]):
        return "grammar & syntax"
    if any(k in text for k in ["vocabulary", "formal", "informal", "slang", "professional", "phrasing", "idiom", "word choice"]):
        return "professional vocabulary"
    if any(k in text for k in ["clarity", "clear", "coherence", "confusing", "vague", "ambiguous", "muddled"]):
        return "clarity"
    if any(k in text for k in ["example", "examples", "specific", "concrete", "metric", "data point", "quantify"]):
        return "concrete examples"

    return "natural phrasing"


def determine_session_strengths(mode: str, clean_exchanges: int, total_exchanges: int) -> List[str]:
    """Identifies demonstrated strengths when user had clean exchanges."""
    if total_exchanges == 0:
        return []

    clean_ratio = clean_exchanges / total_exchanges
    strengths: List[str] = []

    if mode == "conversation":
        if clean_ratio >= 0.5:
            strengths.append("conversational fluency")
        if clean_ratio >= 0.75:
            strengths.append("natural pacing")
    elif mode == "answer_training":
        if clean_ratio >= 0.5:
            strengths.append("answer structure")
        if clean_ratio >= 0.75:
            strengths.append("STAR structure")
    elif mode == "english_improvement":
        if clean_ratio >= 0.5:
            strengths.append("grammatical accuracy")
        if clean_ratio >= 0.75:
            strengths.append("clear articulation")

    return strengths


def compute_updated_skill_level(
    current_level: str,
    correction_rate: float,
    total_exchanges: int,
    sessions_count: int,
) -> str:
    """Computes adaptive skill level adjustment based on performance."""
    level = current_level.lower() if current_level in VALID_SKILL_LEVELS else "intermediate"

    if total_exchanges < 2:
        return level

    if level == "beginner":
        if correction_rate <= 0.34:
            return "intermediate"
    elif level == "intermediate":
        if correction_rate == 0.0 and total_exchanges >= 3 and sessions_count >= 1:
            return "advanced"
        elif correction_rate >= 0.75 and total_exchanges >= 3:
            return "beginner"
    elif level == "advanced":
        if correction_rate >= 0.5 and total_exchanges >= 3:
            return "intermediate"

    return level


async def update_user_communication_profile(
    user_id: str, session_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Analyzes corrections and performance from completed coach session,
    updates skill_level, weak_areas, and strong_areas, and persists update to Supabase.

    Args:
        user_id: UUID or string of the user.
        session_data: Completed session dictionary with mode, history, and corrections.

    Returns:
        Updated user profile dictionary.
    """
    uid = str(user_id)
    current_profile = await get_user_profile(uid)
    mode = session_data.get("mode", "conversation")
    history = session_data.get("history") or session_data.get("exchanges") or []
    if not isinstance(history, list):
        history = []

    # 1. Collect corrections
    corrections = list(session_data.get("corrections") or [])
    if not corrections:
        for ex in history:
            if isinstance(ex, dict) and ex.get("correction"):
                corr = ex["correction"]
                if isinstance(corr, dict) and corr.get("original") and corr.get("improved"):
                    corrections.append(corr)

    total_exchanges = len(history)
    total_corrections = len(corrections)
    correction_rate = (total_corrections / total_exchanges) if total_exchanges > 0 else 0.0

    # 2. Classify weak area tags
    new_weak_tags: List[str] = [classify_correction(c) for c in corrections]

    # 3. Existing lists
    weak_areas = list(current_profile.get("weak_areas", []))
    strong_areas = list(current_profile.get("strong_areas", []))

    # 4. Integrate new weak areas
    for tag in new_weak_tags:
        if tag not in weak_areas:
            weak_areas.append(tag)
        if tag in strong_areas:
            strong_areas.remove(tag)

    # 5. Graduation of weak areas on clean sessions
    clean_exchanges = max(0, total_exchanges - total_corrections)
    session_strengths = determine_session_strengths(mode, clean_exchanges, total_exchanges)

    if total_corrections == 0 and total_exchanges >= 2:
        graduated: List[str] = []
        for w in list(weak_areas):
            if (
                (mode == "conversation" and w in ["conversational fluency", "natural phrasing"])
                or (mode == "answer_training" and w in ["STAR structure", "answer structure", "conciseness"])
                or (mode == "english_improvement" and w in ["grammar & syntax", "filler words", "professional vocabulary"])
            ):
                graduated.append(w)
                weak_areas.remove(w)
                if w not in strong_areas:
                    strong_areas.append(w)

    for s in session_strengths:
        if s not in strong_areas and s not in weak_areas:
            strong_areas.append(s)

    weak_areas = weak_areas[:5]
    strong_areas = strong_areas[:5]

    # 6. Adapt skill level
    current_skill = current_profile.get("skill_level", "intermediate")
    current_count = int(current_profile.get("sessions_count", 0))
    new_skill = compute_updated_skill_level(current_skill, correction_rate, total_exchanges, current_count)

    now = _now_iso()
    updated_comm_profile = {
        "skill_level": new_skill,
        "weak_areas": weak_areas,
        "strong_areas": strong_areas,
        "sessions_count": current_count + 1,
        "last_mode": mode,
        "last_session_id": session_data.get("session_id") or session_data.get("id"),
        "last_updated": now,
    }

    # 7. Update memory cache
    with _coach_lock:
        if uid in _in_memory_user_profiles:
            _in_memory_user_profiles[uid].update({
                "skill_level": new_skill,
                "weak_areas": weak_areas,
                "strong_areas": strong_areas,
                "sessions_count": current_count + 1,
                "communication_profile": updated_comm_profile,
                "updated_at": now,
            })
        else:
            _in_memory_user_profiles[uid] = {
                "id": uid,
                "user_id": uid,
                "email": current_profile.get("email"),
                "name": current_profile.get("name"),
                "skill_level": new_skill,
                "weak_areas": weak_areas,
                "strong_areas": strong_areas,
                "sessions_count": current_count + 1,
                "communication_profile": updated_comm_profile,
                "created_at": current_profile.get("created_at", now),
                "updated_at": now,
            }

    # 8. Persist to Supabase
    client = get_supabase_client()
    try:
        # Dual-write attempt with top-level and JSONB
        client.table("users").update({
            "communication_profile": updated_comm_profile,
            "skill_level": new_skill,
            "weak_areas": weak_areas,
            "strong_areas": strong_areas,
            "updated_at": now,
        }).eq("id", uid).execute()
        logger.info(f"Updated communication profile for user {uid} in Supabase.")
    except Exception as exc:
        logger.debug(f"Top-level user update notice: {exc}. Retrying with communication_profile only.")
        try:
            client.table("users").update({
                "communication_profile": updated_comm_profile,
                "updated_at": now,
            }).eq("id", uid).execute()
        except Exception as final_exc:
            logger.warning(
                f"Notice: Supabase user profile update failed ({final_exc}). Saved in memory cache."
            )

    return await get_user_profile(uid)


def clear_coach_cache() -> None:
    """Clears coach in-memory caches (for test suite isolation)."""
    with _coach_lock:
        _in_memory_coach_sessions.clear()
        _in_memory_user_profiles.clear()
