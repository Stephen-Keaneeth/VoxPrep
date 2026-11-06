import { create } from "zustand";
import type {
  UserProfile,
  InterviewReport,
  CoachEndResponse,
} from "@/lib/api";
import type { InterviewSessionRecord, CoachSessionRecord } from "@/lib/supabase";

export type SectionId = 1 | 2 | 3 | 4 | 5;

// Backward-compatible type alias for components using UserState
export type UserState = UserProfile & { token?: string };

// Backward-compatible type alias for legacy components
export interface ResumeData {
  fileName: string;
  fileSize: string;
  uploadedAt: string;
  candidateName?: string;
  targetRole: string;
  experienceLevel?: string;
  skills: string[];
  recentCompany: string;
  summary: string;
  customQuestions?: string[];
}

function getInitialGuestId(): string {
  if (typeof window !== "undefined") {
    try {
      const existing = window.localStorage.getItem("voxprep_guest_user_id");
      if (existing) return existing;
      const generated =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `guest-${Date.now()}`;
      window.localStorage.setItem("voxprep_guest_user_id", generated);
      return generated;
    } catch {
      // localStorage may fail in private mode
    }
  }
  return "guest-user-default";
}

export interface AppState {
  // Live Authenticated User Session
  user: UserProfile | null;
  token: string | null;
  guestUserId: string;

  // Active Session IDs
  interviewSessionId: string | null;
  coachSessionId: string | null;

  // Live Report Payloads
  interviewReport: InterviewReport | null;
  coachReport: CoachEndResponse | null;

  // Primary Actions
  setUser: (user: UserProfile | null, token?: string | null) => void;
  setToken: (token: string | null) => void;
  setGuestUserId: (guestUserId: string) => void;
  setInterviewSessionId: (id: string | null) => void;
  setCoachSessionId: (id: string | null) => void;
  setInterviewReport: (report: InterviewReport | null) => void;
  setCoachReport: (report: CoachEndResponse | null) => void;
  clearSession: () => void;

  // Minimal UI Navigation & Media State
  activeSection: SectionId;
  setActiveSection: (section: SectionId) => void;
  isCameraOn: boolean;
  setCameraOn: (on: boolean) => void;
  isMicOn: boolean;
  setMicOn: (on: boolean) => void;
  isCallActive: boolean;
  setCallActive: (active: boolean) => void;
  isSetupModalOpen: boolean;
  setSetupModalOpen: (open: boolean) => void;
  currentQuestionIndex: number;
  nextQuestion: () => void;
  resetQuestions: () => void;

  // Clean compatibility stubs for un-rebuilt legacy views (purged of all mock bloat)
  resume: ResumeData | null;
  setResume: (resume: ResumeData | null) => void;
  isResumeBased: boolean;
  setIsResumeBased: (enabled: boolean) => void;
  interviewHistory: InterviewSessionRecord[];
  addInterviewSession: (session: InterviewSessionRecord) => void;
  coachHistory: CoachSessionRecord[];
  addCoachSession: (session: CoachSessionRecord) => void;
  latestEvaluation: InterviewSessionRecord | null;
  setLatestEvaluation: (evalRecord: InterviewSessionRecord | null) => void;
}

export const useStore = create<AppState>((set) => ({
  // Live user session (zero mock candidate, strictly null until logged in)
  user: null,
  token: null,
  guestUserId: getInitialGuestId(),

  // Active session tracking
  interviewSessionId: null,
  coachSessionId: null,

  // Live report storage
  interviewReport: null,
  coachReport: null,

  // Store mutations
  setUser: (user, token) =>
    set((state) => ({
      user,
      token: token !== undefined ? token : state.token,
    })),
  setToken: (token) => set({ token }),
  setGuestUserId: (guestUserId) => set({ guestUserId }),
  setInterviewSessionId: (interviewSessionId) => set({ interviewSessionId }),
  setCoachSessionId: (coachSessionId) => set({ coachSessionId }),
  setInterviewReport: (interviewReport) => set({ interviewReport }),
  setCoachReport: (coachReport) => set({ coachReport }),
  clearSession: () =>
    set({
      interviewSessionId: null,
      coachSessionId: null,
      interviewReport: null,
      coachReport: null,
      isCallActive: false,
    }),

  // Navigation & interaction controls
  activeSection: 1,
  setActiveSection: (section) => set({ activeSection: section }),
  isCameraOn: false,
  setCameraOn: (isCameraOn) => set({ isCameraOn }),
  isMicOn: true,
  setMicOn: (isMicOn) => set({ isMicOn }),
  isCallActive: false,
  setCallActive: (isCallActive) => set({ isCallActive }),
  isSetupModalOpen: false,
  setSetupModalOpen: (isSetupModalOpen) => set({ isSetupModalOpen }),
  currentQuestionIndex: 0,
  nextQuestion: () =>
    set((state) => ({
      currentQuestionIndex: (state.currentQuestionIndex + 1) % 5,
    })),
  resetQuestions: () => set({ currentQuestionIndex: 0 }),

  // Clean empty state (all fake resumes, questions, and histories purged)
  resume: null,
  setResume: (resume) => set({ resume }),
  isResumeBased: false,
  setIsResumeBased: (isResumeBased) => set({ isResumeBased }),
  interviewHistory: [],
  addInterviewSession: (session) =>
    set((state) => ({
      interviewHistory: [session, ...state.interviewHistory],
      latestEvaluation: session,
    })),
  coachHistory: [],
  addCoachSession: (session) =>
    set((state) => ({
      coachHistory: [session, ...state.coachHistory],
    })),
  latestEvaluation: null,
  setLatestEvaluation: (latestEvaluation) => set({ latestEvaluation }),
}));

// Backward-compatible alias for existing imports
export const useAppStore = useStore;
export default useStore;
