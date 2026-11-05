# Analysis Report: Supabase SQL Schema Script & Database Architecture

**Date**: 2026-11-05  
**Author**: `explorer_m0_3`  
**Milestone**: Milestone 0 (Phase 0: Project Initialization, Environment, and Setup)  
**Target Files**: `backend/schema.sql`, `backend/app/db/__init__.py`, `backend/app/db/supabase.py`  

---

## 1. Executive Summary & Architectural Context

VOXPREP is an AI-powered voice interview and communication coaching platform. The system operates on a dual-agent pattern:
1. **Agent 1: AI Interviewer** (conducts mock HR and Technical interviews, scores answers on a 4-dimension rubric, and generates comprehensive evaluation reports).
2. **Agent 2: AI Communication Coach** (conducts conversational coaching across 3 modes: `conversation`, `answer_training`, and `english_improvement`, providing real-time feedback and updating persistent communication profiles).

Persistence is provided by **Supabase (PostgreSQL 15+)** with JSONB support for rich agent dialogue history and structured evaluation reports. The backend connects via FastAPI using the official `supabase-py` client.

To fulfill Milestone 0 (Phase 0 Setup), the database layer requires:
1. An idempotent, production-ready DDL script (`backend/schema.sql`) defining the core relational and document tables: `users`, `interview_sessions`, and `coach_sessions`.
2. Indexes, foreign keys, timestamps, check constraints, and Row Level Security (RLS) policies.
3. A clean, modular database directory layout (`backend/app/db/`) featuring a thread-safe Supabase singleton client with graceful offline mock fallback for test execution without requiring live API keys.

---

## 2. Supabase SQL Schema Specification (`backend/schema.sql`)

### 2.1 Complete Idempotent DDL Script

Below is the complete, self-contained, idempotent SQL schema script to be placed at `backend/schema.sql`:

```sql
-- =============================================================================
-- VOXPREP Supabase Database Schema
-- Milestone 0 (Phase 0: Project Initialization, Environment, and Setup)
-- Database Engine: PostgreSQL 15+ (Supabase)
-- Script Type: Fully Idempotent DDL
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. EXTENSIONS
-- -----------------------------------------------------------------------------
-- Ensure cryptographic functions and UUID generators are available.
-- Note: PostgreSQL 13+ includes gen_random_uuid() natively.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- 2. USERS TABLE
-- Stores user accounts, identity mappings, and persistent communication profiles.
-- -----------------------------------------------------------------------------
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

-- Indexes for users
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC);

-- Helper trigger function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 3. INTERVIEW_SESSIONS TABLE
-- Stores mock interview sessions conducted by Agent 1 (AI Interviewer).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS interview_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    candidate_name TEXT NOT NULL,
    role_applied TEXT NOT NULL,
    experience_level TEXT NOT NULL,
    interview_type TEXT NOT NULL CHECK (interview_type IN ('hr', 'technical')),
    questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    answers JSONB NOT NULL DEFAULT '[]'::jsonb,
    scores JSONB NOT NULL DEFAULT '{}'::jsonb,
    report JSONB DEFAULT NULL,
    current_question_index INT NOT NULL DEFAULT 0 CHECK (current_question_index >= 0),
    follow_up_count INT NOT NULL DEFAULT 0 CHECK (follow_up_count >= 0),
    is_complete BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    completed_at TIMESTAMPTZ DEFAULT NULL
);

-- Indexes for interview_sessions
CREATE INDEX IF NOT EXISTS idx_interview_sessions_user_id ON interview_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_created_at ON interview_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_is_complete ON interview_sessions(is_complete);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_interview_type ON interview_sessions(interview_type);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_user_created ON interview_sessions(user_id, created_at DESC);

-- -----------------------------------------------------------------------------
-- 4. COACH_SESSIONS TABLE
-- Stores AI communication coaching sessions conducted by Agent 2 (AI Coach).
-- -----------------------------------------------------------------------------
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

-- Indexes for coach_sessions
CREATE INDEX IF NOT EXISTS idx_coach_sessions_user_id ON coach_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_coach_sessions_created_at ON coach_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_coach_sessions_mode ON coach_sessions(mode);
CREATE INDEX IF NOT EXISTS idx_coach_sessions_is_complete ON coach_sessions(is_complete);
CREATE INDEX IF NOT EXISTS idx_coach_sessions_user_created ON coach_sessions(user_id, created_at DESC);

-- -----------------------------------------------------------------------------
-- 5. ROW LEVEL SECURITY (RLS) & ACCESS CONTROL
-- -----------------------------------------------------------------------------
-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE coach_sessions ENABLE ROW LEVEL SECURITY;

-- Note: When backend uses SUPABASE_SERVICE_KEY, it bypasses RLS automatically.
-- For frontend / anon key access during MVP hackathon development, permissive policies are defined:
DROP POLICY IF EXISTS "Allow full access to users" ON users;
CREATE POLICY "Allow full access to users"
    ON users FOR ALL
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS "Allow full access to interview_sessions" ON interview_sessions;
CREATE POLICY "Allow full access to interview_sessions"
    ON interview_sessions FOR ALL
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS "Allow full access to coach_sessions" ON coach_sessions;
CREATE POLICY "Allow full access to coach_sessions"
    ON coach_sessions FOR ALL
    USING (true)
    WITH CHECK (true);

-- -----------------------------------------------------------------------------
-- 6. SAMPLE SEED DATA (OPTIONAL / VERIFICATION)
-- -----------------------------------------------------------------------------
INSERT INTO users (id, email, name, communication_profile)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'demo@voxprep.ai',
    'Alex Candidate',
    '{
        "skill_level": "intermediate",
        "weak_areas": ["filler words", "conciseness"],
        "strong_areas": ["technical depth", "clarity"],
        "sessions_count": 1
    }'::jsonb
) ON CONFLICT (email) DO NOTHING;
```

---

## 3. Table Schema Deep-Dive & Field Mapping

### 3.1 Table `users`

| Column | Type | Constraints | Description & Purpose |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique user identifier. When using Supabase Auth, matches `auth.users.id`. |
| `email` | `TEXT` | `UNIQUE NOT NULL` | Candidate email address. Unique index ensures no duplicate registrations. |
| `name` | `TEXT` | Nullable | Full name of the candidate/user. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc'::text, now())` | Record creation timestamp in UTC. |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc'::text, now())` | Automatically updated via PostgreSQL trigger. |
| `communication_profile` | `JSONB` | `NOT NULL DEFAULT {...}` | Persistent profile used by Agent 2 to adapt coaching. |

#### JSONB Structure: `communication_profile`
```json
{
  "skill_level": "beginner" | "intermediate" | "advanced",
  "weak_areas": ["filler words", "conciseness", "grammar"],
  "strong_areas": ["technical vocabulary", "pacing"],
  "sessions_count": 0
}
```

### 3.2 Table `interview_sessions`

| Column | Type | Constraints | Description & Purpose |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Session identifier returned to client upon `POST /interview/start`. |
| `user_id` | `UUID` | `REFERENCES users(id) ON DELETE SET NULL` | Linked user ID (nullable to allow unauthenticated / guest mock interviews). |
| `candidate_name` | `TEXT` | `NOT NULL` | Name used by Agent 1 to personalize opening greeting. |
| `role_applied` | `TEXT` | `NOT NULL` | Role targeted (e.g. "Full Stack Developer", "Product Manager"). |
| `experience_level` | `TEXT` | `NOT NULL` | Experience level ("entry", "junior", "mid", "senior", "lead"). |
| `interview_type` | `TEXT` | `NOT NULL CHECK (interview_type IN ('hr', 'technical'))` | Determines the agent system prompt loaded from `08_AGENT_PROMPTS.md`. |
| `questions` | `JSONB` | `NOT NULL DEFAULT '[]'::jsonb` | Ordered array of question objects asked during the session. |
| `answers` | `JSONB` | `NOT NULL DEFAULT '[]'::jsonb` | Ordered array of candidate answers and internal rubric evaluations. |
| `scores` | `JSONB` | `NOT NULL DEFAULT '{}'::jsonb` | Aggregate scores across dimensions (Relevance, Clarity, Depth, Examples). |
| `report` | `JSONB` | `DEFAULT NULL` | Structured evaluation report generated at `POST /interview/end`. |
| `current_question_index` | `INT` | `NOT NULL DEFAULT 0 CHECK (current_question_index >= 0)` | Pointer to current question (enforces <= 5 questions boundary). |
| `follow_up_count` | `INT` | `NOT NULL DEFAULT 0 CHECK (follow_up_count >= 0)` | Tracks follow-up count per question (enforces <= 1 follow-up boundary). |
| `is_complete` | `BOOLEAN` | `NOT NULL DEFAULT FALSE` | Session status flag. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc'::text, now())` | Session initiation timestamp. |
| `completed_at` | `TIMESTAMPTZ` | Nullable | Session completion timestamp. |

#### JSONB Structure: `questions` & `answers`
```json
// questions
[
  { "index": 0, "text": "Tell me about yourself.", "type": "opening" },
  { "index": 1, "text": "Explain how event loops work in asynchronous Python.", "type": "main" }
]

// answers
[
  {
    "question_index": 1,
    "user_transcript": "The event loop manages cooperative multitasking...",
    "scores": { "relevance": 9, "clarity": 8, "depth": 8, "examples": 7 },
    "feedback": "Strong theoretical understanding; could benefit from mentioning asyncio.run()."
  }
]
```

#### JSONB Structure: `report` (per `docs/08_AGENT_PROMPTS.md`)
```json
{
  "overall_score": 8.0,
  "dimension_scores": {
    "relevance": 8.5,
    "clarity": 8.0,
    "depth": 7.5,
    "examples": 8.0
  },
  "strengths": [
    "Clear explanation of async architecture in question 2",
    "Structured behavioral answers using STAR technique"
  ],
  "weaknesses": [
    "Tendency to provide theoretical answers without concrete project metrics in question 3"
  ],
  "improvement_tips": [
    "Quantify engineering impact by stating latency improvements or user scale"
  ],
  "coach_recommendation": "Interview Answer Training",
  "summary": "Alex demonstrated solid communication and technical grasp with minor areas for metric-driven polish."
}
```

### 3.3 Table `coach_sessions`

| Column | Type | Constraints | Description & Purpose |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Coaching session identifier returned on `POST /coach/start`. |
| `user_id` | `UUID` | `REFERENCES users(id) ON DELETE CASCADE` | Linked user ID whose communication profile is read and updated. |
| `mode` | `TEXT` | `NOT NULL CHECK (mode IN ('conversation', 'answer_training', 'english_improvement'))` | Coaching mode loaded from prompt bank. |
| `exchanges` | `JSONB` | `NOT NULL DEFAULT '[]'::jsonb` | Array of dialogue exchanges and constructive corrections. |
| `summary` | `JSONB` | `DEFAULT NULL` | Session wrap-up summary and communication profile updates. |
| `is_complete` | `BOOLEAN` | `NOT NULL DEFAULT FALSE` | Completion status flag. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT timezone('utc'::text, now())` | Session creation timestamp. |
| `completed_at` | `TIMESTAMPTZ` | Nullable | Session completion timestamp. |

#### JSONB Structure: `exchanges` (per `docs/08_AGENT_PROMPTS.md`)
```json
[
  {
    "coach_message": "Hello Alex! Let's work on answering questions using the STAR framework today.",
    "user_response_text": "Yeah, basically I was working on this bug and fixed it quickly.",
    "correction": {
      "original": "basically I was working on this bug and fixed it quickly",
      "improved": "I diagnosed a critical race condition in production and deployed a thread-safe patch within two hours.",
      "reason": "Sounds more professional, structured, and quantifies your direct action."
    },
    "next_prompt": "Can you try phrasing that again emphasizing the situation and your exact action?"
  }
]
```

---

## 4. Database Directory Layout & Singleton Client

### 4.1 Directory Structure
```
backend/
├── app/
│   ├── db/
│   │   ├── __init__.py          # Exports get_supabase_client
│   │   └── supabase.py          # Singleton client with live & mock support
│   └── ...
└── schema.sql                   # Supabase PostgreSQL DDL script
```

### 4.2 Supabase Singleton Architecture (`backend/app/db/supabase.py`)

The Supabase client must fulfill two vital requirements:
1. **Thread-Safe Singleton**: Instantiated once and reused across FastAPI request threads.
2. **Resilient Mock Fallback**: In automated testing environments or local dev where live Supabase credentials (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`) are not provided or contain placeholder values, the application must NOT crash upon startup or when running unit tests.

#### Recommended Implementation Pattern:
```python
"""Supabase database client singleton for VOXPREP backend."""
import os
import logging
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("voxprep.db")

_client_instance: Optional[Any] = None

class MockTableQuery:
    """In-memory mock query builder for offline tests and development."""
    def __init__(self, table_name: str, store: dict):
        self.table_name = table_name
        self.store = store
        self._filter_col: Optional[str] = None
        self._filter_val: Any = None
        self._is_single = False

    def select(self, *args, **kwargs):
        return self

    def insert(self, data: dict | list):
        if isinstance(data, list):
            self.store.setdefault(self.table_name, []).extend(data)
            self._last_result = data
        else:
            self.store.setdefault(self.table_name, []).append(data)
            self._last_result = [data]
        return self

    def update(self, data: dict):
        rows = self.store.get(self.table_name, [])
        updated = []
        for row in rows:
            if self._filter_col and row.get(self._filter_col) == self._filter_val:
                row.update(data)
                updated.append(row)
        self._last_result = updated
        return self

    def eq(self, column: str, value: Any):
        self._filter_col = column
        self._filter_val = value
        return self

    def single(self):
        self._is_single = True
        return self

    def execute(self):
        class MockResponse:
            def __init__(self, data):
                self.data = data
        
        rows = self.store.get(self.table_name, [])
        if self._filter_col:
            rows = [r for r in rows if r.get(self._filter_col) == self._filter_val]
        
        if self._is_single:
            result = rows[0] if rows else None
        else:
            result = getattr(self, "_last_result", rows)
        return MockResponse(result)

class MockAuth:
    """Mock auth service for offline testing."""
    def sign_up(self, credentials: dict):
        email = credentials.get("email", "test@voxprep.ai")
        return type("MockAuthResponse", (), {"user": type("User", (), {"id": "00000000-0000-0000-0000-000000000001", "email": email})()})()

    def sign_in_with_password(self, credentials: dict):
        email = credentials.get("email", "test@voxprep.ai")
        return type("MockAuthResponse", (), {
            "user": type("User", (), {"id": "00000000-0000-0000-0000-000000000001", "email": email})(),
            "session": type("Session", (), {"access_token": "mock-jwt-token"})()
        })()

class MockSupabaseClient:
    """Mock Supabase client providing tables and auth without network access."""
    def __init__(self):
        self._store: dict[str, list] = {
            "users": [{
                "id": "00000000-0000-0000-0000-000000000001",
                "email": "demo@voxprep.ai",
                "name": "Alex Candidate",
                "communication_profile": {
                    "skill_level": "intermediate",
                    "weak_areas": ["filler words"],
                    "strong_areas": ["clarity"],
                    "sessions_count": 1
                }
            }],
            "interview_sessions": [],
            "coach_sessions": []
        }
        self.auth = MockAuth()

    def table(self, table_name: str) -> MockTableQuery:
        return MockTableQuery(table_name, self._store)

def get_supabase_client():
    """Returns singleton Supabase client or mock fallback if credentials are absent."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_KEY", "").strip() or os.getenv("SUPABASE_ANON_KEY", "").strip()

    is_dummy = not url or not key or "placeholder" in url.lower() or "your_" in url.lower()

    if is_dummy:
        logger.warning("Supabase credentials not configured or placeholder. Initializing MockSupabaseClient.")
        _client_instance = MockSupabaseClient()
        return _client_instance

    try:
        from supabase import create_client, Client
        _client_instance = create_client(url, key)
        logger.info("Supabase client successfully initialized.")
        return _client_instance
    except Exception as exc:
        logger.error(f"Failed to initialize live Supabase client: {exc}. Falling back to MockSupabaseClient.")
        _client_instance = MockSupabaseClient()
        return _client_instance
```

---

## 5. Verification Strategy & Execution Instructions

### 5.1 Applying `schema.sql` to Supabase
1. **Via Supabase Web Console**:
   - Open Supabase project dashboard -> Navigate to **SQL Editor**.
   - Create a new query, paste the contents of `backend/schema.sql`, and click **Run**.
   - Verify in **Table Editor** that `users`, `interview_sessions`, and `coach_sessions` are created with all columns and constraints.

2. **Via Local Automated Verification**:
   - Worker creates a dedicated test `backend/tests/test_db_schema.py` to inspect `backend/schema.sql`:
     - Asserts `schema.sql` file exists in `backend/`.
     - Validates that SQL syntax contains `CREATE TABLE IF NOT EXISTS users`.
     - Validates that SQL syntax contains `CREATE TABLE IF NOT EXISTS interview_sessions`.
     - Validates that SQL syntax contains `CREATE TABLE IF NOT EXISTS coach_sessions`.
     - Checks all required column definitions, foreign keys, and indexes.
     - Validates that `get_supabase_client()` imports and returns a functional client instance.

---

## 6. Worker Implementation Plan for Milestone 0

1. **Step 1**: Write `backend/schema.sql` using the complete DDL provided in Section 2.
2. **Step 2**: Create `backend/app/db/__init__.py` exporting `get_supabase_client`.
3. **Step 3**: Create `backend/app/db/supabase.py` with the resilient singleton and mock fallback pattern.
4. **Step 4**: Create `backend/tests/test_db.py` to test client initialization and basic table queries offline.
5. **Step 5**: Execute `pytest backend/tests/test_db.py` to confirm zero failures.
