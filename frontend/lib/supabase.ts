/**
 * VOXPREP Supabase Client & Database Types
 * Cleaned per single-source-of-truth mandate.
 *
 * Direct database calls and in-memory mock session stores have been purged.
 * All data persistence is performed via the FastAPI backend REST API.
 */

export interface InterviewSessionRecord {
  id?: string;
  user_id?: string;
  candidate_name: string;
  role_applied: string;
  role?: string;
  experience_level: string;
  interview_type: "hr" | "technical";
  questions: string[] | Record<string, unknown>[];
  answers: string[] | Record<string, unknown>[];
  scores: {
    overall_score?: number;
    relevance?: number;
    technical_depth?: number;
    depth?: number;
    clarity?: number;
    examples?: number;
  };
  report?: {
    overall_score?: number;
    dimension_scores?: {
      relevance?: number;
      clarity?: number;
      depth?: number;
      examples?: number;
    };
    strengths?: string[];
    weaknesses?: string[];
    areas_for_improvement?: string[];
    question_breakdown?: {
      question: string;
      answer_summary: string;
      scores: { relevance: number; clarity: number; depth: number; examples: number };
      feedback: string;
    }[];
    action_items?: string[];
    improvement_tips?: string[];
    coach_recommendation?: string;
    summary?: string;
  };
  current_question_index?: number;
  follow_up_count?: number;
  is_complete: boolean;
  status?: string;
  created_at?: string;
  completed_at?: string;
}

export interface CoachSessionRecord {
  id?: string;
  user_id?: string;
  mode: "conversation" | "answer_training" | "english_improvement";
  exchanges: {
    prompt: string;
    transcript: string;
    feedback: string;
    wpm?: number;
    fillers_detected?: number;
    correction?: {
      original: string;
      improved: string;
      reason: string;
    } | null;
  }[];
  summary?: {
    avg_wpm?: number;
    total_fillers?: number;
    grammar_score?: number;
    fluency_tier?: string;
    exchanges_count?: number;
    corrections_count?: number;
    encouragement?: string;
    key_learnings?: string[];
  };
  is_complete: boolean;
  status?: string;
  created_at?: string;
  completed_at?: string;
}

export interface CommunicationProfile {
  skill_level: "beginner" | "intermediate" | "advanced";
  weak_areas: string[];
  strong_areas: string[];
  sessions_count: number;
  avg_wpm?: number;
  filler_rate?: number;
}

/**
 * Returns false. Client components must not bypass the FastAPI backend.
 */
export function isLiveSupabase(): boolean {
  return false;
}

/**
 * Client stub: Returns null as direct Supabase access is prohibited from frontend.
 */
export function getSupabase(): null {
  return null;
}

/**
 * Safe no-op bridge: persistence is handled via FastAPI /interview/end.
 */
export async function saveInterviewSession(
  session: InterviewSessionRecord
): Promise<{ success: boolean; id: string }> {
  return { success: true, id: session.id || "" };
}

/**
 * Safe no-op bridge: persistence is handled via FastAPI /coach/end.
 */
export async function saveCoachSession(
  session: CoachSessionRecord
): Promise<{ success: boolean; id: string }> {
  return { success: true, id: session.id || "" };
}

/**
 * Safe no-op query: past sessions are queried via FastAPI endpoints.
 */
export async function fetchInterviewSessions(
  _userId?: string
): Promise<InterviewSessionRecord[]> {
  void _userId;
  return [];
}

/**
 * Safe no-op query: past sessions are queried via FastAPI endpoints.
 */
export async function fetchCoachSessions(
  _userId?: string
): Promise<CoachSessionRecord[]> {
  void _userId;
  return [];
}
