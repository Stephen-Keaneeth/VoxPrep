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
