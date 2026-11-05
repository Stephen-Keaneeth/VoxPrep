import { create } from "zustand";

export type SectionId = 1 | 2 | 3 | 4 | 5;

export interface ResumeData {
  fileName: string;
  fileSize: string;
  uploadedAt: string;
  candidateName?: string;
  targetRole: string;
  skills: string[];
  recentCompany: string;
  summary: string;
}

interface AppState {
  activeSection: SectionId;
  setActiveSection: (section: SectionId) => void;

  // Resume state
  resume: ResumeData | null;
  setResume: (resume: ResumeData | null) => void;
  isResumeBased: boolean;
  setIsResumeBased: (enabled: boolean) => void;

  // Video call state (Section 2)
  isCameraOn: boolean;
  setCameraOn: (on: boolean) => void;
  isMicOn: boolean;
  setMicOn: (on: boolean) => void;
  isCallActive: boolean;
  setCallActive: (active: boolean) => void;
  currentQuestionIndex: number;
  nextQuestion: () => void;
  resetQuestions: () => void;
  isSetupModalOpen: boolean;
  setSetupModalOpen: (open: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeSection: 1,
  setActiveSection: (section) => set({ activeSection: section }),

  // Default mock parsed resume or null
  resume: {
    fileName: "Anish_Senior_Engineer_Resume.pdf",
    fileSize: "148 KB",
    uploadedAt: "Nov 5, 2026",
    candidateName: "Anish",
    targetRole: "Senior Backend / Distributed Systems Engineer",
    skills: ["PostgreSQL", "Kafka", "Distributed Systems", "Python", "Go", "Next.js", "Redis"],
    recentCompany: "CloudScale Systems",
    summary:
      "5+ years architecting event-driven microservices, high-throughput caching tiers, and real-time streaming pipelines.",
  },
  setResume: (resume) => set({ resume }),
  isResumeBased: true,
  setIsResumeBased: (isResumeBased) => set({ isResumeBased }),

  isCameraOn: false,
  setCameraOn: (isCameraOn) => set({ isCameraOn }),
  isMicOn: true,
  setMicOn: (isMicOn) => set({ isMicOn }),
  isCallActive: true,
  setCallActive: (isCallActive) => set({ isCallActive }),
  currentQuestionIndex: 0,
  nextQuestion: () =>
    set((state) => ({
      currentQuestionIndex: (state.currentQuestionIndex + 1) % 5,
    })),
  resetQuestions: () => set({ currentQuestionIndex: 0 }),
  isSetupModalOpen: false,
  setSetupModalOpen: (isSetupModalOpen) => set({ isSetupModalOpen }),
}));
