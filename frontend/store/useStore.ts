import { create } from "zustand";
import { InterviewSessionRecord, CoachSessionRecord } from "@/lib/supabase";

export type SectionId = 1 | 2 | 3 | 4 | 5;

export interface UserState {
  id: string;
  email: string;
  name: string;
  token?: string;
}

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

interface AppState {
  activeSection: SectionId;
  setActiveSection: (section: SectionId) => void;

  // Authenticated user state
  user: UserState | null;
  setUser: (user: UserState | null) => void;

  // Resume state
  resume: ResumeData | null;
  setResume: (resume: ResumeData | null) => void;
  isResumeBased: boolean;
  setIsResumeBased: (enabled: boolean) => void;

  // Video call & session state (Section 2)
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

  // Database session history & latest evaluation
  interviewHistory: InterviewSessionRecord[];
  addInterviewSession: (session: InterviewSessionRecord) => void;
  coachHistory: CoachSessionRecord[];
  addCoachSession: (session: CoachSessionRecord) => void;
  latestEvaluation: InterviewSessionRecord | null;
  setLatestEvaluation: (evalRecord: InterviewSessionRecord | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeSection: 1,
  setActiveSection: (section) => set({ activeSection: section }),

  // Default candidate user
  user: {
    id: "user-101",
    email: "anish@voxprep.internal",
    name: "Anish (Candidate)",
  },
  setUser: (user) => set({ user }),

  // Default mock parsed resume
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
    customQuestions: [
      '"I reviewed your resume from CloudScale Systems where you architected event-driven systems using Kafka. Could you walk me through how you guaranteed message ordering and fault-tolerance?"',
      '"Under your core technical competencies, you highlighted PostgreSQL optimization. Can you describe a specific lock contention or indexing challenge you resolved?"',
      '"In your role as Senior Backend Engineer, how did you approach decoupling monolithic dependencies with zero downtime?"',
      '"You have extensive experience with Redis caching. How did you design cache invalidation and prevent thundering herd spikes?"',
      '"Based on your background, what distributed systems architectural challenges are you most eager to tackle next?"',
    ],
  },
  setResume: (resume) => set({ resume }),
  isResumeBased: true,
  setIsResumeBased: (isResumeBased) => set({ isResumeBased }),

  isCameraOn: false,
  setCameraOn: (isCameraOn) => set({ isCameraOn }),
  isMicOn: true,
  setMicOn: (isMicOn) => set({ isMicOn }),
  isCallActive: false,
  setCallActive: (isCallActive) => set({ isCallActive }),
  currentQuestionIndex: 0,
  nextQuestion: () =>
    set((state) => ({
      currentQuestionIndex: (state.currentQuestionIndex + 1) % 5,
    })),
  resetQuestions: () => set({ currentQuestionIndex: 0 }),
  isSetupModalOpen: false,
  setSetupModalOpen: (isSetupModalOpen) => set({ isSetupModalOpen }),

  // Session history matching schema.sql
  interviewHistory: [
    {
      id: "int-session-01",
      candidate_name: "Anish",
      role_applied: "Distributed System Design",
      experience_level: "Senior",
      interview_type: "technical",
      questions: ["How would you handle distributed cache invalidation?"],
      answers: ["I would implement Cache-Aside with CDC event publishing..."],
      scores: {
        overall_score: 88,
        relevance: 92,
        technical_depth: 86,
        clarity: 88,
        examples: 80,
      },
      report: {
        strengths: [
          "Video Presence & Composure: Maintained eye contact with the camera and steady pacing.",
          "Concise Delivery: Stayed within the 90–120 second recommended window without drifting.",
          "System Resilience: Accurately isolated consumer failure domains with circuit breakers.",
        ],
        weaknesses: [
          "Quantitative Metrics: State expected QPS and storage costs explicitly.",
          "Error Handling: Explicitly mention Dead Letter Queues (DLQ).",
        ],
      },
      is_complete: true,
      created_at: new Date(Date.now() - 86400000).toISOString(),
    },
  ],
  addInterviewSession: (session) =>
    set((state) => ({
      interviewHistory: [session, ...state.interviewHistory],
      latestEvaluation: session,
    })),

  coachHistory: [
    {
      id: "coa-session-01",
      mode: "answer_training",
      exchanges: [
        {
          prompt: "Describe a high-stakes technical deadline where a critical dependency was delayed.",
          transcript:
            "When the payment gateway API was delayed, like, we realized the launch was at risk. I convened the stakeholders and we done made a mock service.",
          feedback:
            "Replace 'we done made a mock service' with 'we engineered a mock stub to decouple development'.",
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
    },
  ],
  addCoachSession: (session) =>
    set((state) => ({
      coachHistory: [session, ...state.coachHistory],
    })),

  latestEvaluation: null,
  setLatestEvaluation: (latestEvaluation) => set({ latestEvaluation }),
}));
