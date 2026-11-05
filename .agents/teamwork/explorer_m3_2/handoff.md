# Handoff Report: Milestone 3 Coach Persistence & Profile Learning Architecture

**Agent**: `explorer_m3_2` (Coach Persistence & Profile Learning Architect)  
**Date**: 2026-11-05T18:42:00Z  
**Target Milestone**: Milestone 3 (Phase 3: AI Communication Coach Agent)  
**Target Component**: Database Persistence & User Profile Learning (`backend/app/db/coach_persistence.py`, `backend/schema.sql`, `backend/app/db/supabase.py`)

---

## 1. Observation

Direct codebase observations, line numbers, and empirical command executions:

### 1.1 Existing Database Schema (`backend/schema.sql`)
1. **Users Table** (`backend/schema.sql:20-37`):
   ```sql
   CREATE TABLE IF NOT EXISTS users (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       email TEXT UNIQUE NOT NULL,
       name TEXT,
       created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
       updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
       communication_profile JSONB NOT NULL DEFAULT '{
           "skill_level": "intermediate",
           "weak_areas": [],
           "strong_areas": [],
           "sessions_count": 0
       }'::jsonb,
       CONSTRAINT chk_users_skill_level CHECK (
           communication_profile IS NULL OR
           communication_profile->>'skill_level' IS NULL OR
           communication_profile->>'skill_level' IN ('beginner', 'intermediate', 'advanced')
       )
   );
   ```
   - Seed data at `backend/schema.sql:148-159` populates demo user `00000000-0000-0000-0000-000000000001` (`demo@voxprep.ai`) with:
     - `skill_level`: `"intermediate"`
     - `weak_areas`: `["filler words", "conciseness"]`
     - `strong_areas`: `["technical depth", "clarity"]`
     - `sessions_count`: `1`

2. **Coach Sessions Table** (`backend/schema.sql:99-108`):
   ```sql
   CREATE TABLE IF NOT EXISTS coach_sessions (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       user_id UUID REFERENCES users(id) ON DELETE CASCADE,
       mode TEXT NOT NULL CHECK (mode IN ('conversation', 'answer_training', 'english_improvement')),
       exchanges JSONB NOT NULL DEFAULT '[]'::jsonb,
       summary JSONB DEFAULT NULL,
       is_complete BOOLEAN NOT NULL DEFAULT FALSE,
       created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
       completed_at TIMESTAMPTZ DEFAULT NULL
   );
   ```
   - Notice columns present: `id`, `user_id`, `mode`, `exchanges`, `summary`, `is_complete`, `created_at`, `completed_at`.
   - Columns referenced by dispatch, agent state, and router contracts: `history` (synonym for `exchanges`), `corrections` (JSONB list of identified corrections), `status` (TEXT: `'in_progress'` vs `'completed'`), `started_at` (synonym for `created_at`), and `updated_at`.
   - Milestone 2 precedent at `backend/schema.sql:87-93`: Idempotent schema enhancements were added for `interview_sessions`:
     ```sql
     -- Milestone 2 Idempotent Schema Enhancements
     ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS role TEXT;
     ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'in_progress';
     ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS question_count INT DEFAULT 0;
     ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS history JSONB DEFAULT '[]'::jsonb;
     ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now());
     ```

### 1.2 Mock Client State (`backend/app/db/supabase.py:273-290`)
- `MockSupabaseClient` initializes with:
  ```python
  self._store: Dict[str, List[Dict[str, Any]]] = {
      "users": [
          {
              "id": "00000000-0000-0000-0000-000000000001",
              "email": "demo@voxprep.ai",
              "name": "Alex Candidate",
              "communication_profile": {
                  "skill_level": "intermediate",
                  "weak_areas": ["filler words"],
                  "strong_areas": ["clarity"],
                  "sessions_count": 1,
              },
          }
      ],
      "interview_sessions": [],
      "coach_sessions": [],
  }
  ```
- `MockTableQuery` executes queries (`select`, `insert`, `update`, `delete`, `eq`, `single`) against in-memory dictionary lists (`store[table_name]`).
- In `MockTableQuery.update`, updates mutate matching dictionary records.
- In `MockTableQuery.insert`, dictionary records are appended to the table store.

### 1.3 Precedent Architectural Pattern (`backend/app/db/session_persistence.py`)
- Milestone 2 established a robust dual-layer persistence pattern in `backend/app/db/session_persistence.py`:
  1. **Thread-Safe In-Memory Cache**: `_in_memory_sessions` guarded by `_cache_lock` guarantees instant read-your-writes consistency and seamless fallback during network errors or test runs.
  2. **Field Normalization (`_normalize_session_row`)**: Reconciles dual-column representations (`role` vs `role_applied`, `status` vs `is_complete`, `question_count` vs `current_question_index`, `history` vs `questions`/`answers`).
  3. **Dual-Write Operations**: Ensures records written to Supabase contain all alternate column names so queries succeed regardless of which field names client code accesses.
  4. **Exception Containment**: Catches and logs database insert/update exceptions, falling back to the memory cache without crashing the API process.

### 1.4 Test Suite Baseline
- Command: `.venv\Scripts\pytest`
- Result: **249 passed, 1 warning in 1.97s** (clean 100% pass across all unit, boundary, and adversarial tests).

---

## 2. Logic Chain

Step-by-step reasoning from observations to the architectural design:

### Step 2.1: Schema Reconciliation & Dual-Write Necessity
- **From Observation 1.1 & 1.2**: `backend/schema.sql` initially defines `coach_sessions` with columns `(id, user_id, mode, exchanges, summary, is_complete, created_at, completed_at)`.
- However, the Coach agent (`agents/coach.py`) and router (`routers/coach.py`) interact with `history` (list of exchanges), `corrections` (list of corrections extracted or provided), `status` (`"in_progress"` / `"completed"`), `started_at`, and `updated_at`.
- If an application attempts to insert a record with columns `history` or `status` into a live PostgreSQL Supabase instance that only has the baseline `schema.sql`, PostgreSQL will reject the write with a PostgREST error: `column "history" of relation "coach_sessions" does not exist`.
- **Reasoning**:
  1. We must add idempotent `ALTER TABLE coach_sessions ADD COLUMN IF NOT EXISTS ...` migrations to `backend/schema.sql` (exactly matching the pattern established in Milestone 2 for `interview_sessions`).
  2. `coach_persistence.py` must implement dual-write and bidirectional normalization (`_normalize_coach_session_row`):
     - `exchanges` <-> `history` (both point to the exchange list)
     - `is_complete` <-> `status` (`status == "completed"` <-> `is_complete == True`)
     - `created_at` <-> `started_at`
     - `corrections` (extracted list of `{"original", "improved", "reason"}`)
     - `updated_at` (current UTC timestamp)
     - `id` <-> `session_id`

### Step 2.2: User Profile Structure & Reconciliation
- **From Observation 1.1**: In `schema.sql`, `users` defines `communication_profile JSONB` with default `{"skill_level": "intermediate", "weak_areas": [], "strong_areas": [], "sessions_count": 0}` and check constraint `chk_users_skill_level`.
- In `MockSupabaseClient`, `demo@voxprep.ai` has `communication_profile` dict, but no top-level `skill_level`, `weak_areas`, or `strong_areas` keys.
- **Reasoning**:
  1. `get_user_profile(user_id: str)` must normalize the user record. It extracts from `communication_profile` and sets top-level keys (`skill_level`, `weak_areas`, `strong_areas`, `sessions_count`) in the returned dict, while also preserving `communication_profile`.
  2. If `user_id` does not exist in `users` (e.g. guest or new user), `get_user_profile` provisions a safe default baseline:
     ```python
     {
         "id": user_id,
         "user_id": user_id,
         "email": f"user_{user_id[:8]}@voxprep.ai",
         "name": "Learner",
         "skill_level": "intermediate",
         "weak_areas": [],
         "strong_areas": [],
         "sessions_count": 0,
         "communication_profile": {
             "skill_level": "intermediate",
             "weak_areas": [],
             "strong_areas": [],
             "sessions_count": 0,
         }
     }
     ```
     It attempts an insert into `users` and saves to `_in_memory_user_profiles`.
  3. When persisting profile updates in `update_user_communication_profile`:
     Update `users.communication_profile` with the new JSON structure, and update top-level columns if present, ensuring 100% compatibility with both `MockSupabaseClient` and production Supabase PostgreSQL.

### Step 2.3: Profile Learning Algorithm Design
- **From Observation 1.1 & docs/08_AGENT_PROMPTS.md**:
  Coach corrections follow the structure:
  ```json
  {
      "original": "<user's phrase>",
      "improved": "<better alternative>",
      "reason": "<explanation why alternative is better>"
  }
  ```
  The profile must learn from these corrections when a session ends:
  - **Weak Areas Categorization**:
    Analyze the text in `reason` + `original` + `improved`:
    1. *Filler Words*: text contains "filler", "um", "uh", "like", "you know", "sort of", "kind of" -> `"filler words"`
    2. *STAR Structure*: mode is `"answer_training"` or text contains "star", "structure", "situation", "task", "action", "result" -> `"STAR structure"`
    3. *Conciseness*: text contains "concise", "brief", "rambling", "wordy", "long-winded" -> `"conciseness"`
    4. *Grammar & Syntax*: text contains "grammar", "tense", "verb", "plural", "preposition" -> `"grammar & syntax"`
    5. *Professional Vocabulary*: text contains "vocabulary", "formal", "slang", "phrasing", "word choice" -> `"professional vocabulary"`
    6. *Clarity*: text contains "clarity", "vague", "clear", "confusing", "ambiguous" -> `"clarity"`
    7. *Concrete Examples*: text contains "example", "specific", "concrete", "metric", "quantify" -> `"concrete examples"`
    Fallback: `"natural phrasing"`.
  - **Weak Areas Progression**:
    New tags are prepended/appended to `weak_areas` (deduplicated, capped at 5). Any area newly added to `weak_areas` is purged from `strong_areas`.
  - **Strong Areas & Weak Area Graduation**:
    - If a session had 0 corrections over $\ge 2$ exchanges:
      - The user demonstrated mastery in this session's domain!
      - Areas tested in this mode (e.g. `"filler words"` in English improvement, or `"STAR structure"` in answer training) are graduated from `weak_areas` to `strong_areas`.
      - Mode-specific strengths are added:
        - `"conversation"`: `"conversational fluency"`, `"natural pacing"`
        - `"answer_training"`: `"STAR structure"`, `"answer structure"`
        - `"english_improvement"`: `"grammatical accuracy"`, `"clear articulation"`
    - Strong areas are capped at 5 and deduplicated.
  - **Skill Level Transitions**:
    Evaluate correction rate $R = C / N$ ($C$ = corrections, $N$ = exchanges, $N \ge 2$):
    - Current `"beginner"`: if $R \le 0.34$, promote to `"intermediate"`.
    - Current `"intermediate"`:
      - If $R == 0$ and $N \ge 3$ and `sessions_count` $\ge 1$, promote to `"advanced"`.
      - If $R \ge 0.75$ and $N \ge 3$, adjust to `"beginner"` for foundational coaching.
    - Current `"advanced"`:
      - If $R \ge 0.5$ and $N \ge 3$, adjust back to `"intermediate"`.
  - **Telemetry & Metadata**:
    Update `sessions_count += 1`, record `last_mode`, `last_session_id`, and `last_updated`.

---

## 3. Implementation Blueprint

### 3.1 Idempotent Schema Migration for `backend/schema.sql`

Add the following section to `backend/schema.sql` immediately after Milestone 2 enhancements:

```sql
-- -----------------------------------------------------------------------------
-- Milestone 3 Idempotent Schema Enhancements
-- Phase 3 AI Communication Coach Agent & Profile Learning
-- -----------------------------------------------------------------------------
-- Ensure coach_sessions supports all aliases and query forms
ALTER TABLE coach_sessions ADD COLUMN IF NOT EXISTS history JSONB DEFAULT '[]'::jsonb;
ALTER TABLE coach_sessions ADD COLUMN IF NOT EXISTS corrections JSONB DEFAULT '[]'::jsonb;
ALTER TABLE coach_sessions ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'in_progress';
ALTER TABLE coach_sessions ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now());
ALTER TABLE coach_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now());
CREATE INDEX IF NOT EXISTS idx_coach_sessions_status ON coach_sessions(status);

-- Optional top-level columns on users for direct column access
ALTER TABLE users ADD COLUMN IF NOT EXISTS skill_level TEXT DEFAULT 'intermediate';
ALTER TABLE users ADD COLUMN IF NOT EXISTS weak_areas JSONB DEFAULT '[]'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS strong_areas JSONB DEFAULT '[]'::jsonb;
```

### 3.2 Complete Code Blueprint for `backend/app/db/coach_persistence.py`

Below is the complete, self-contained architecture for `backend/app/db/coach_persistence.py`:

```python
"""Supabase Coach Session Persistence & Profile Learning Service for VOXPREP Backend.
Milestone 3: Phase 3 AI Communication Coach Agent.

Provides high-level database operations for:
- Saving and retrieving coach sessions (save_coach_session, get_coach_session)
- Fetching user profiles with defaults (get_user_profile)
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
        "name": "Learner",
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
```

---

## 4. Caveats

1. **Live Supabase vs MockSupabaseClient**:
   - In offline test environments (which `backend/app/db/supabase.py` automatically enters when dummy credentials are used), `MockSupabaseClient` uses an in-memory dictionary.
   - Live PostgreSQL strictly checks column presence. The dual-try pattern implemented in `save_coach_session` and `update_user_communication_profile` ensures that if a deployment runs against an older database migration lacking the `ALTER TABLE` enhancements, it will still successfully write the core baseline columns without throwing 500 errors.
2. **Foreign Key Constraints on New Users**:
   - In `backend/schema.sql`, `coach_sessions.user_id` has `REFERENCES users(id) ON DELETE CASCADE`.
   - If a caller starts a coach session with an arbitrary UUID that does not yet exist in `users`, direct insertion into PostgreSQL `coach_sessions` would fail a foreign key constraint unless `users` contains that ID first.
   - `get_user_profile(user_id)` proactively inserts the baseline user into `users` before `save_coach_session` inserts into `coach_sessions`. This completely eliminates FK violation errors.
3. **Empty History on Instant Termination**:
   - If a user ends a session immediately after starting (0 exchanges), `update_user_communication_profile` safely handles `total_exchanges == 0` without division-by-zero, incrementing `sessions_count` while leaving skill levels unchanged.

---

## 5. Conclusion

1. **Schema Reconciliation is Complete**:
   `backend/schema.sql` requires idempotent additions for `coach_sessions` (`history`, `corrections`, `status`, `started_at`, `updated_at`) and `users` (`skill_level`, `weak_areas`, `strong_areas`).
2. **Persistence Architecture is Robust**:
   `backend/app/db/coach_persistence.py` provides:
   - `save_coach_session(session_id, data)`
   - `get_coach_session(session_id)`
   - `get_user_profile(user_id)`
   - `update_user_communication_profile(user_id, session_data)`
   - In-memory backup cache with thread locking (`_coach_lock`)
   - Bidirectional field normalization (`_normalize_coach_session_row`, `_normalize_user_profile`)
   - Seamless dual-write fallback between PostgreSQL and `MockSupabaseClient`.
3. **Profile Learning Algorithm is Deterministic & Adaptive**:
   It classifies correction categories, adapts `skill_level` (`beginner`, `intermediate`, `advanced`), graduates mastered weak areas to strong areas upon clean sessions, and persists state across sessions.

---

## 6. Verification Method

To independently verify the architecture:

### 6.1 Schema Validation
```powershell
.venv\Scripts\pytest backend\tests\test_db_schema.py -v
```
Verify that `backend/schema.sql` syntax remains valid and passes all schema assertions.

### 6.2 Target Persistence Tests to Implement in `backend/tests/test_coach_persistence.py`
The implementer can run:
```powershell
.venv\Scripts\pytest backend\tests\test_coach_persistence.py -v
```
Verifying:
1. `test_save_and_get_coach_session`:
   - Saves a session with `exchanges`, verifies retrieval under both `history` and `exchanges`, and checks `status` / `is_complete`.
2. `test_get_user_profile_default`:
   - Retrieves profile for unknown UUID, asserts `skill_level == "intermediate"`, `weak_areas == []`, `strong_areas == []`, `sessions_count == 0`.
3. `test_get_user_profile_demo_user`:
   - Retrieves profile for `00000000-0000-0000-0000-000000000001`, asserts `weak_areas == ["filler words"]`, `strong_areas == ["clarity"]`.
4. `test_update_user_profile_learning`:
   - Submits session with corrections for filler words and STAR method, asserts `weak_areas` updated to `["filler words", "STAR structure"]`, `sessions_count` increments from 1 to 2.
5. `test_update_user_profile_graduation_and_promotion`:
   - Submits clean session with 0 corrections across 3 exchanges, asserts `intermediate` promotes to `advanced` and weak areas graduate to `strong_areas`.

### 6.3 Full Suite Regression
```powershell
.venv\Scripts\pytest
```
Must pass all 249+ tests with 0 failures.
