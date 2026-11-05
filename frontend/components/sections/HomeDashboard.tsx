"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/store/useStore";
import { Video, MessageSquare, ArrowUpRight, FileText, Sparkles, CheckCircle2 } from "lucide-react";
import ResumeUploadModal from "@/components/interview/ResumeUploadModal";

export default function HomeDashboard() {
  const router = useRouter();
  const {
    setActiveSection,
    resume,
    isResumeBased,
    setSetupModalOpen,
    interviewHistory,
    coachHistory,
    setLatestEvaluation,
  } = useAppStore();

  // Dynamic calculations from Supabase store state
  const totalInterviewSessions = interviewHistory.length;
  const avgInterviewScore =
    totalInterviewSessions > 0
      ? Math.round(
          interviewHistory.reduce((acc, s) => acc + (s.scores?.overall_score || 85), 0) /
            totalInterviewSessions
        )
      : 86;

  const totalCoachSessions = coachHistory.length;
  const avgCoachScore =
    totalCoachSessions > 0
      ? Math.round(
          coachHistory.reduce((acc, s) => acc + (s.summary?.grammar_score || 80), 0) /
            totalCoachSessions
        )
      : 79;

  const latestWpm =
    coachHistory.length > 0 && coachHistory[0]?.summary?.avg_wpm
      ? coachHistory[0].summary.avg_wpm
      : 138;

  const overallReadiness = Math.round(avgInterviewScore * 0.55 + avgCoachScore * 0.45);

  const totalMinutes = totalInterviewSessions * 15 + totalCoachSessions * 8;
  const hours = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;
  const practiceTimeString = `${hours > 0 ? `${hours}h ` : ""}${mins}m`;
  const totalSessionsCount = totalInterviewSessions + totalCoachSessions;

  // Unified recent mock sessions list
  const recentSessions = [
    ...interviewHistory.map((s, idx) => ({
      id: s.id || `int-${idx}`,
      type: "interview" as const,
      agentTitle: "Interview Agent",
      topic: s.role_applied || "Technical System Architecture",
      isResumeTailored: Boolean(resume && isResumeBased),
      format: "Video Call" as const,
      duration: "14m 20s",
      score: s.scores?.overall_score || 88,
      createdAt: s.created_at || new Date().toISOString(),
      interviewRecord: s,
    })),
    ...coachHistory.map((c, idx) => ({
      id: c.id || `coa-${idx}`,
      type: "coach" as const,
      agentTitle: "Communication Agent",
      topic:
        c.mode === "answer_training"
          ? "STAR Structuring & Conciseness"
          : c.mode === "conversation"
          ? "Everyday Fluency & Articulation"
          : "Executive Vocabulary Practice",
      isResumeTailored: false,
      format: "Voice Coach" as const,
      duration: "09m 10s",
      score: c.summary?.grammar_score || 82,
      createdAt: c.created_at || new Date().toISOString(),
      interviewRecord: undefined,
    })),
  ]
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .slice(0, 5);

  return (
    <section className="space-y-6">
      <ResumeUploadModal />

      {/* Overview Intro */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Candidate Readiness Overview</h2>
          <p className="text-sm text-slate-400 mt-1">
            Holistic preparation metrics, video mock interview scores, and speaking progress.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/interview"
            onClick={() => setActiveSection(2)}
            className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-4 py-2 rounded-lg flex items-center gap-1.5 transition-colors shadow-sm"
          >
            <Video className="w-4 h-4" />
            <span>Start Video Interview</span>
          </Link>
          <Link
            href="/coach"
            onClick={() => setActiveSection(3)}
            className="bg-[#171e2e] hover:bg-[#1e273a] border border-subtle text-slate-200 text-xs font-semibold px-4 py-2 rounded-lg flex items-center gap-1.5 transition-colors"
          >
            <MessageSquare className="w-4 h-4 text-amber-400" />
            <span>Practice with Coach</span>
          </Link>
        </div>
      </div>

      {/* Resume Integration Banner */}
      <div className="card-clean p-4 bg-[#0d162a] border border-blue-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 shrink-0">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs font-semibold text-white flex items-center gap-2">
              <span>{resume ? `Resume Connected: ${resume.fileName}` : "No Resume Uploaded"}</span>
              {resume && isResumeBased && (
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.2 rounded flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>Adaptive Mode Active</span>
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {resume
                ? `Evaluating for ${resume.targetRole} (${resume.skills.slice(0, 4).join(", ")}...)`
                : "Upload your resume so the AI interviewer asks tailored questions about your real projects."}
            </p>
          </div>
        </div>

        <button
          onClick={() => setSetupModalOpen(true)}
          className="text-xs font-medium bg-[#1e293b] hover:bg-slate-700 text-blue-300 px-3.5 py-2 rounded-lg border border-subtle flex items-center gap-1.5 shrink-0 transition-colors"
        >
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          <span>{resume ? "Update Resume / Skills" : "Upload Resume"}</span>
        </button>
      </div>

      {/* 4 Core Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">Overall Readiness</div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-white">{overallReadiness}%</span>
            <span className="text-xs text-emerald-400 font-medium">+4.5%</span>
          </div>
          <div className="mt-3 text-xs text-slate-400">Benchmark: Job Ready</div>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">Interview Score</div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-blue-400">{avgInterviewScore}/100</span>
            <span className="text-xs text-slate-400">{totalInterviewSessions} sessions</span>
          </div>
          <div className="mt-3 text-xs text-slate-400">Technical & HR video rounds</div>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">Communication Score</div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-white">{avgCoachScore}/100</span>
            <span className="text-xs text-emerald-400 font-medium">{latestWpm} WPM</span>
          </div>
          <div className="mt-3 text-xs text-slate-400">Fluency, pace & grammar</div>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">Practice Time</div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-white">{practiceTimeString}</span>
            <span className="text-xs text-slate-400">This week</span>
          </div>
          <div className="mt-3 text-xs text-slate-400">{totalSessionsCount} mock sessions logged</div>
        </div>
      </div>

      {/* Recent Activity Table */}
      <div className="card-clean overflow-hidden">
        <div className="px-5 py-4 border-b border-subtle flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white">Recent Mock Sessions</h3>
          <span className="text-xs text-slate-400">
            {recentSessions.length > 0 ? `Showing latest ${recentSessions.length} entries` : "No sessions logged"}
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#0e1627] text-slate-400 uppercase font-mono border-b border-subtle">
              <tr>
                <th className="px-5 py-3">Session</th>
                <th className="px-5 py-3">Topic / Focus</th>
                <th className="px-5 py-3">Format</th>
                <th className="px-5 py-3">Duration</th>
                <th className="px-5 py-3">Score</th>
                <th className="px-5 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-subtle text-slate-300">
              {recentSessions.length > 0 ? (
                recentSessions.map((session) => (
                  <tr key={session.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-5 py-3.5 font-medium text-white">{session.agentTitle}</td>
                    <td className="px-5 py-3.5 text-slate-300">
                      {session.topic}{" "}
                      {session.isResumeTailored && (
                        <span className="text-blue-400 text-[11px]">(Resume Tailored)</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`px-2 py-0.5 rounded font-mono text-[11px] ${
                          session.format === "Video Call"
                            ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                            : "bg-slate-800 text-slate-300 border border-subtle"
                        }`}
                      >
                        {session.format}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-slate-400 font-mono">{session.duration}</td>
                    <td
                      className={`px-5 py-3.5 font-mono font-medium ${
                        session.score >= 85 ? "text-emerald-400" : "text-blue-400"
                      }`}
                    >
                      {session.score} / 100
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <button
                        onClick={() => {
                          if (session.type === "interview") {
                            if (session.interviewRecord) {
                              setLatestEvaluation(session.interviewRecord);
                            }
                            setActiveSection(4);
                            router.push("/analytics/interview");
                          } else {
                            setActiveSection(5);
                            router.push("/analytics/communication");
                          }
                        }}
                        className="text-blue-400 hover:text-blue-300 flex items-center gap-1 ml-auto font-medium"
                      >
                        <span>Report</span>
                        <ArrowUpRight className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-center text-slate-400">
                    No mock sessions recorded yet. Start your first video interview or practice with the coach above!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
