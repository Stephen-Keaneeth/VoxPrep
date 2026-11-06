/**
 * VOXPREP Authoritative Frontend API Client
 * 100% strictly typed client aligned with the FastAPI backend routers:
 * - app/routers/auth.py
 * - app/routers/voice.py
 * - app/routers/interview.py
 * - app/routers/coach.py
 * - app/models/report.py
 * - app/main.py
 *
 * Base URL defaults to process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// =============================================================================
// Error Handling & Standard Backend Error Envelope
// =============================================================================

export interface ApiValidationErrorItem {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

export interface ApiErrorEnvelope {
  detail: string | ApiValidationErrorItem[];
  error_type?: "http_error" | "validation_error" | "internal_server_error" | string;
  status_code?: number;
}

export class ApiError extends Error {
  status: number;
  detail: string | ApiValidationErrorItem[];
  errorType?: string;

  constructor(status: number, detail: string | ApiValidationErrorItem[], errorType?: string) {
    let message = `API request failed with status ${status}`;
    if (typeof detail === "string") {
      message = detail;
    } else if (Array.isArray(detail)) {
      message = detail
        .map((item) => (item.msg ? `${item.loc?.join(".") || "field"}: ${item.msg}` : JSON.stringify(item)))
        .join("; ");
    }
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.errorType = errorType;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail: string | ApiValidationErrorItem[] = res.statusText || "Unknown server error";
    let errorType: string | undefined;

    try {
      const errJson = (await res.json()) as ApiErrorEnvelope;
      if (errJson && errJson.detail !== undefined) {
        detail = errJson.detail;
        errorType = errJson.error_type;
      }
    } catch {
      // Body not JSON; retain default statusText
    }

    throw new ApiError(res.status, detail, errorType);
  }

  return (await res.json()) as T;
}

// =============================================================================
// 1. Health Probe Models (backend/app/main.py)
// =============================================================================

export interface HealthResponse {
  status: "ok" | string;
}

// =============================================================================
// 2. Authentication Models (backend/app/routers/auth.py)
// =============================================================================

export interface RegisterRequest {
  email: string;
  password: string;
  name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface UserProfile {
  id: string;
  email: string;
  name?: string;
  token?: string;
}

export interface AuthResponse {
  user: UserProfile;
  access_token: string;
}

// Backward compatibility alias
export type AuthUser = UserProfile;

// =============================================================================
// 3. Voice Pipeline Models (backend/app/routers/voice.py)
// =============================================================================

export interface VoiceProcessResponse {
  transcript: string;
  spoken_response: string;
  audio_base64: string | null;
  session_id: string | null;
  // Backward compatibility alias for UI components
  ai_response?: string;
  audio_url?: string;
}

// =============================================================================
// 4. Interviewer Agent Models (backend/app/routers/interview.py & models/report.py)
// =============================================================================

export interface InterviewStartRequest {
  candidate_name: string;
  role: string;
  experience_level: string;
  interview_type: "hr" | "technical";
  user_id?: string | null;
}

export interface InterviewStartResponse {
  session_id: string;
  opening_message: string;
}

export interface InterviewRespondRequest {
  session_id: string;
  answer_text: string;
}

export interface InterviewRespondResponse {
  spoken_response: string;
  is_complete: boolean;
  follow_up_or_next: "follow_up" | "next";
  question_index: number;
  current_question_index: number;
  total_questions: number;
}

export interface DimensionScores {
  relevance: number;
  clarity: number;
  depth: number;
  examples: number;
}

export interface QuestionBreakdownItem {
  question: string;
  answer_summary: string;
  scores: DimensionScores;
  feedback: string;
}

export interface InterviewReport {
  overall_score: number;
  dimension_scores: DimensionScores;
  strengths: string[];
  areas_for_improvement: string[];
  question_breakdown: QuestionBreakdownItem[];
  action_items: string[];
  coach_recommendation?: string;
  summary?: string;
  // Aliases mirroring backend model_post_init for backward compatibility
  weaknesses?: string[];
  improvement_tips?: string[];
}

export type BackendInterviewReport = InterviewReport;

export interface InterviewEndRequest {
  session_id: string;
}

export interface InterviewEndResponse {
  session_id: string;
  status: "completed" | string;
  message: string;
  report: InterviewReport;
}

// =============================================================================
// 5. Communication Coach Agent Models (backend/app/routers/coach.py)
// =============================================================================

export interface CoachCorrection {
  original: string;
  improved: string;
  reason: string;
}

export interface CoachStartRequest {
  user_id: string;
  mode: "conversation" | "answer_training" | "english_improvement";
}

export interface CoachStartResponse {
  session_id: string;
  opening_message: string;
  mode: "conversation" | "answer_training" | "english_improvement" | string;
}

export interface CoachRespondRequest {
  session_id: string;
  user_text: string;
}

export interface CoachRespondResponse {
  coach_message: string;
  correction: CoachCorrection | null;
  next_prompt: string;
}

export interface CoachEndRequest {
  session_id: string;
}

export interface CoachSessionSummary {
  exchanges_count: number;
  corrections_count: number;
  mode: string;
  key_learnings: string[];
  encouragement: string;
  [key: string]: unknown;
}

export interface UserCommunicationProfile {
  skill_level: "beginner" | "intermediate" | "advanced" | string;
  weak_areas: string[];
  strong_areas: string[];
  sessions_count: number;
  last_mode?: string;
  last_session_id?: string;
  last_updated?: string;
  [key: string]: unknown;
}

export interface CoachEndResponse {
  session_id: string;
  status: "completed" | string;
  summary: CoachSessionSummary;
  profile_updated: UserCommunicationProfile;
  updated_profile?: UserCommunicationProfile;
}

// =============================================================================
// Score Normalization Utility (1.0 - 10.0 scale -> 0 - 100% percentage display)
// =============================================================================

/**
 * Normalizes scores on the 1.0 - 10.0 backend scale into 0 - 100 integer percentages.
 * Rule: score <= 10 ? Math.round(score * 10) : Math.round(score)
 */
export function normalizeScore(score: number): number {
  if (score <= 10) {
    return Math.round(score * 10);
  }
  return Math.round(score);
}

// =============================================================================
// Typed Endpoint Client Functions
// =============================================================================

/**
 * GET /health
 * Service liveness probe.
 */
export async function checkHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`, {
    method: "GET",
    signal,
  });
  return handleResponse<HealthResponse>(res);
}

/**
 * Checks if the backend is reachable and reports healthy status.
 */
export async function checkBackendHealth(): Promise<boolean> {
  try {
    const data = await checkHealth(AbortSignal.timeout(3000));
    return data.status === "ok";
  } catch {
    return false;
  }
}

/**
 * POST /auth/register
 * Registers new user account with Supabase Auth and seeds user communication profile.
 */
export async function register(req: RegisterRequest): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<AuthResponse>(res);
}

export async function registerUser(
  email: string,
  password: string,
  name?: string
): Promise<AuthResponse> {
  return register({ email, password, name });
}

/**
 * POST /auth/login
 * Authenticates user credentials with Supabase Auth.
 */
export async function login(req: LoginRequest): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<AuthResponse>(res);
}

export async function loginUser(email: string, password: string): Promise<AuthResponse> {
  return login({ email, password });
}

/**
 * POST /voice/process
 * Complete voice pipeline: STT -> LLM dialog reply -> TTS synthesis.
 */
export async function processVoice(formData: FormData): Promise<VoiceProcessResponse> {
  const res = await fetch(`${API_BASE_URL}/voice/process`, {
    method: "POST",
    body: formData,
  });
  const data = await handleResponse<VoiceProcessResponse>(res);
  if (!data.ai_response) {
    data.ai_response = data.spoken_response;
  }
  return data;
}

export async function sendVoiceAudio(
  audioBlob: Blob,
  agentType: "interview" | "coach" | string = "interview",
  conversationHistory: string = "",
  sessionId?: string
): Promise<VoiceProcessResponse> {
  const formData = new FormData();
  formData.append("file", audioBlob, "recording.wav");
  formData.append("agent_type", agentType);
  if (sessionId) {
    formData.append("session_id", sessionId);
  }
  if (conversationHistory) {
    formData.append("conversation_history", conversationHistory);
  }
  return processVoice(formData);
}

/**
 * POST /interview/start
 * Initializes a structured mock interview session.
 */
export async function startInterview(
  req: InterviewStartRequest
): Promise<InterviewStartResponse> {
  const res = await fetch(`${API_BASE_URL}/interview/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<InterviewStartResponse>(res);
}

export async function startInterviewSession(
  req: InterviewStartRequest
): Promise<InterviewStartResponse> {
  return startInterview(req);
}

/**
 * POST /interview/respond
 * Evaluates candidate answer, scores rubric, and progresses interview.
 */
export async function respondInterview(
  req: InterviewRespondRequest
): Promise<InterviewRespondResponse> {
  const res = await fetch(`${API_BASE_URL}/interview/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<InterviewRespondResponse>(res);
}

export async function submitInterviewAnswer(
  sessionId: string,
  answerText: string
): Promise<InterviewRespondResponse> {
  return respondInterview({ session_id: sessionId, answer_text: answerText });
}

/**
 * POST /interview/end
 * Concludes interview session, generates evaluation report, and persists state.
 */
export async function endInterview(
  req: InterviewEndRequest
): Promise<InterviewEndResponse> {
  const res = await fetch(`${API_BASE_URL}/interview/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<InterviewEndResponse>(res);
}

export async function endInterviewSession(
  sessionId: string
): Promise<InterviewEndResponse> {
  return endInterview({ session_id: sessionId });
}

/**
 * GET /interview/report/{session_id}
 * Retrieves comprehensive performance report for a completed interview session.
 */
export async function getInterviewReport(
  sessionId: string
): Promise<InterviewReport> {
  const res = await fetch(`${API_BASE_URL}/interview/report/${encodeURIComponent(sessionId)}`, {
    method: "GET",
  });
  return handleResponse<InterviewReport>(res);
}

/**
 * POST /coach/start
 * Initializes communication coach session in one of 3 modes.
 */
export async function startCoach(
  req: CoachStartRequest
): Promise<CoachStartResponse> {
  const res = await fetch(`${API_BASE_URL}/coach/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<CoachStartResponse>(res);
}

export async function startCoachSession(
  userId: string,
  mode: "conversation" | "answer_training" | "english_improvement"
): Promise<CoachStartResponse> {
  return startCoach({ user_id: userId, mode });
}

/**
 * POST /coach/respond
 * Processes user speech, returns supportive message and up to 1-2 linguistic corrections.
 */
export async function respondCoach(
  req: CoachRespondRequest
): Promise<CoachRespondResponse> {
  const res = await fetch(`${API_BASE_URL}/coach/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<CoachRespondResponse>(res);
}

export async function submitCoachResponse(
  sessionId: string,
  userText: string
): Promise<CoachRespondResponse> {
  return respondCoach({ session_id: sessionId, user_text: userText });
}

/**
 * POST /coach/end
 * Concludes coach session, updates communication profile, and persists state.
 */
export async function endCoach(
  req: CoachEndRequest
): Promise<CoachEndResponse> {
  const res = await fetch(`${API_BASE_URL}/coach/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<CoachEndResponse>(res);
}

export async function endCoachSession(
  sessionId: string
): Promise<CoachEndResponse> {
  return endCoach({ session_id: sessionId });
}

// =============================================================================
// Unified API Namespace Export
// =============================================================================

export const api = {
  health: {
    check: checkHealth,
    isHealthy: checkBackendHealth,
  },
  auth: {
    register,
    login,
  },
  voice: {
    process: processVoice,
    sendAudio: sendVoiceAudio,
  },
  interview: {
    start: startInterview,
    respond: respondInterview,
    end: endInterview,
    getReport: getInterviewReport,
  },
  coach: {
    start: startCoach,
    respond: respondCoach,
    end: endCoach,
  },
  utils: {
    normalizeScore,
  },
};

export const apiClient = {
  checkHealth,
  checkBackendHealth,
  register,
  registerUser,
  login,
  loginUser,
  processVoice,
  sendVoiceAudio,
  startInterview,
  startInterviewSession,
  respondInterview,
  submitInterviewAnswer,
  endInterview,
  endInterviewSession,
  getInterviewReport,
  startCoach,
  startCoachSession,
  respondCoach,
  submitCoachResponse,
  endCoach,
  endCoachSession,
  normalizeScore,
};

export default api;

