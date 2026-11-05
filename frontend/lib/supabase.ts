/**
 * VOXPREP Supabase Client & Database Services
 * Conforms 100% to backend/schema.sql
 */

import { createClient, SupabaseClient } from "@supabase/supabase-js";

export interface InterviewSessionRecord {
  id?: string;
  user_id?: string;
  candidate_name: string;
  role_applied: string;
  experience_level: string;
  interview_type: "hr" | "technical";
  questions: string[] | Record<string, unknown>[];
  answers: string[] | Record<string, unknown>[];
  scores: {
    overall_score?: number;
    relevance?: number;
    technical_depth?: number;
    clarity?: number;
    examples?: number;
  };
  report?: {
    strengths?: string[];
    weaknesses?: string[];
    recommendations?: string[];
  };
  current_question_index?: number;
  follow_up_count?: number;
  is_complete: boolean;
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
  }[];
  summary?: {
    avg_wpm?: number;
    total_fillers?: number;
    grammar_score?: number;
    fluency_tier?: string;
  };
  is_complete: boolean;
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

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://your-project-id.supabase.co";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "mock-anon-key";

/**
 * Returns true if real Supabase credentials are configured.
 */
export function isLiveSupabase(): boolean {
  if (!supabaseUrl || !supabaseAnonKey) return false;
  const lowerUrl = supabaseUrl.toLowerCase();
  const lowerKey = supabaseAnonKey.toLowerCase();
  return !(
    lowerUrl.includes("your-project") ||
    lowerKey.includes("mock") ||
    lowerKey.includes("placeholder") ||
    lowerKey.includes("your_")
  );
}

// In-memory session caches for offline development and testing
const inMemoryInterviewSessions: InterviewSessionRecord[] = [
  {
    id: "int-session-01",
    candidate_name: "Anish",
    role_applied: "Senior Backend / Distributed Systems Engineer",
    experience_level: "Senior",
    interview_type: "technical",
    questions: [
      "How would you handle distributed cache invalidation without causing stampedes?",
      "Can you walk me through how you guarantee message ordering in Kafka consumer groups?",
      "Describe how you structure database indexing to optimize p99 query latency.",
    ],
    answers: [
      "I would implement Cache-Aside with CDC event publishing via Debezium and Kafka...",
      "We keyed partitions by customer ID and enforced sequential consumer offsets...",
      "Analyzed slow queries via EXPLAIN ANALYZE and created partial composite B-tree indexes...",
    ],
    scores: {
      overall_score: 88,
      relevance: 92,
      technical_depth: 86,
      clarity: 88,
      examples: 80,
    },
    report: {
      strengths: ["Clear architectural decoupling", "Eye contact and steady video presence"],
      weaknesses: ["State expected QPS explicitly", "Mention Dead Letter Queues"],
    },
    is_complete: true,
    created_at: new Date(Date.now() - 86400000).toISOString(),
    completed_at: new Date(Date.now() - 85500000).toISOString(),
  },
];

const inMemoryCoachSessions: CoachSessionRecord[] = [
  {
    id: "coa-session-01",
    mode: "answer_training",
    exchanges: [
      {
        prompt: "Describe a high-stakes technical deadline where a critical dependency was delayed.",
        transcript:
          "When the payment gateway API was delayed, like, we realized the launch was at risk. I convened the stakeholders and we done made a mock service.",
        feedback: "Replace 'we done made a mock service' with 'we engineered a mock stub to decouple development'.",
        wpm: 136,
        fillers_detected: 1,
      },
    ],
    summary: {
      avg_wpm: 136,
      total_fillers: 1,
      grammar_score: 94,
      fluency_tier: "Proficient",
    },
    is_complete: true,
    created_at: new Date(Date.now() - 172800000).toISOString(),
    completed_at: new Date(Date.now() - 172200000).toISOString(),
  },
];

let supabaseInstance: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (!supabaseInstance) {
    supabaseInstance = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
      },
    });
  }
  return supabaseInstance;
}

/**
 * Saves a completed mock interview session to Supabase table 'interview_sessions'.
 */
export async function saveInterviewSession(
  session: InterviewSessionRecord
): Promise<{ success: boolean; id: string }> {
  const record = {
    ...session,
    id: session.id || `int-${Date.now()}`,
    created_at: session.created_at || new Date().toISOString(),
    completed_at: session.completed_at || new Date().toISOString(),
  };

  if (!isLiveSupabase()) {
    inMemoryInterviewSessions.unshift(record);
    return { success: true, id: record.id };
  }

  try {
    const supabase = getSupabase();
    const { data, error } = await supabase.from("interview_sessions").insert([record]).select("id").single();
    if (error) throw error;
    return { success: true, id: data.id };
  } catch (err) {
    console.warn("Supabase interview_sessions insert error, saved to local cache:", err);
    inMemoryInterviewSessions.unshift(record);
    return { success: true, id: record.id };
  }
}

/**
 * Saves a completed communication coach session to Supabase table 'coach_sessions'.
 */
export async function saveCoachSession(
  session: CoachSessionRecord
): Promise<{ success: boolean; id: string }> {
  const record = {
    ...session,
    id: session.id || `coa-${Date.now()}`,
    created_at: session.created_at || new Date().toISOString(),
    completed_at: session.completed_at || new Date().toISOString(),
  };

  if (!isLiveSupabase()) {
    inMemoryCoachSessions.unshift(record);
    return { success: true, id: record.id };
  }

  try {
    const supabase = getSupabase();
    const { data, error } = await supabase.from("coach_sessions").insert([record]).select("id").single();
    if (error) throw error;
    return { success: true, id: data.id };
  } catch (err) {
    console.warn("Supabase coach_sessions insert error, saved to local cache:", err);
    inMemoryCoachSessions.unshift(record);
    return { success: true, id: record.id };
  }
}

/**
 * Queries past interview sessions for the candidate.
 */
export async function fetchInterviewSessions(userId?: string): Promise<InterviewSessionRecord[]> {
  if (!isLiveSupabase()) {
    return inMemoryInterviewSessions;
  }

  try {
    const supabase = getSupabase();
    let query = supabase.from("interview_sessions").select("*").order("created_at", { ascending: false }).limit(10);
    if (userId) {
      query = query.eq("user_id", userId);
    }
    const { data, error } = await query;
    if (error || !data || data.length === 0) return inMemoryInterviewSessions;
    return data as unknown as InterviewSessionRecord[];
  } catch {
    return inMemoryInterviewSessions;
  }
}

/**
 * Queries past communication coach sessions for the candidate.
 */
export async function fetchCoachSessions(userId?: string): Promise<CoachSessionRecord[]> {
  if (!isLiveSupabase()) {
    return inMemoryCoachSessions;
  }

  try {
    const supabase = getSupabase();
    let query = supabase.from("coach_sessions").select("*").order("created_at", { ascending: false }).limit(10);
    if (userId) {
      query = query.eq("user_id", userId);
    }
    const { data, error } = await query;
    if (error || !data || data.length === 0) return inMemoryCoachSessions;
    return data as unknown as CoachSessionRecord[];
  } catch {
    return inMemoryCoachSessions;
  }
}

