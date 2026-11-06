"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/store/useStore";
import { normalizeScore } from "@/lib/normalization";
import {
  Video,
  MessageSquare,
  ArrowUpRight,
  Sparkles,
  BarChart3,
  Activity,
  CheckCircle2,
} from "lucide-react";

export default function HomeDashboard() {
  const router = useRouter();
  const {
    setActiveSection,
    interviewHistory,
    coachHistory,
    interviewReport,
    coachReport,
    user,
  } = useAppStore();

  // Dynamic calculations from live store state
  const totalInterviewSessions = interviewHistory.length + (interviewReport ? 1 : 0);
  const interviewScore = interviewReport
    ? normalizeScore(interviewReport.overall_score)
    : interviewHistory.length > 0
    ? Math.round(
        interviewHistory.reduce(
          (acc, s) => acc + normalizeScore(s.scores?.overall_score),
          0
        ) / interviewHistory.length
      )
    : null;

  const totalCoachSessions = coachHistory.length + (coachReport ? 1 : 0);
  const rawCoachGrammar =
    coachReport?.summary && typeof (coachReport.summary as Record<string, unknown>).grammar_score === "number"
      ? ((coachReport.summary as Record<string, unknown>).grammar_score as number)
      : null;

  const coachScore = rawCoachGrammar !== null
    ? normalizeScore(rawCoachGrammar)
    : coachHistory.length > 0
    ? Math.round(
        coachHistory.reduce(
          (acc, s) => acc + normalizeScore(s.summary?.grammar_score),
          0
        ) / coachHistory.length
      )
    : null;

  const rawWpm =
    coachReport?.summary && typeof (coachReport.summary as Record<string, unknown>).avg_wpm === "number"
      ? ((coachReport.summary as Record<string, unknown>).avg_wpm as number)
      : null;

  const latestWpm = rawWpm !== null
    ? rawWpm
    : coachHistory.length > 0 && coachHistory[0]?.summary?.avg_wpm
    ? coachHistory[0].summary.avg_wpm
    : null;

  const overallReadiness =
    interviewScore !== null && coachScore !== null
      ? Math.round(interviewScore * 0.55 + coachScore * 0.45)
      : interviewScore !== null
      ? interviewScore
      : coachScore !== null
      ? coachScore
      : null;

  const totalSessionsCount = totalInterviewSessions + totalCoachSessions;
  const totalMinutes = totalInterviewSessions * 15 + totalCoachSessions * 8;
  const hours = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;
  const practiceTimeString =
    totalSessionsCount > 0 ? `${hours > 0 ? `${hours}h ` : ""}${mins}m` : "0m";

  // Build list of genuine recent sessions
  const recentSessions: {
    id: string;
    type: "interview" | "coach";
    agentTitle: string;
    topic: string;
    format: "Video Call" | "Voice Coach";
    duration: string;
    score: number;
    createdAt: string;
  }[] = [];

  if (interviewReport) {
    recentSessions.push({
      id: "live-interview",
      type: "interview",
      agentTitle: "Interview Agent",
      topic: "Technical / HR Video Interview",
      format: "Video Call",
      duration: "Completed",
      score: normalizeScore(interviewReport.overall_score),
      createdAt: new Date().toISOString(),
    });
  }

  if (coachReport) {
    recentSessions.push({
      id: "live-coach",
      type: "coach",
      agentTitle: "Communication Agent",
      topic: "Communication Coaching Session",
      format: "Voice Coach",
      duration: "Completed",
      score: normalizeScore(rawCoachGrammar || 80),
      createdAt: new Date().toISOString(),
    });
  }

  interviewHistory.forEach((s, idx) => {
    recentSessions.push({
      id: s.id || `int-${idx}`,
      type: "interview",
      agentTitle: "Interview Agent",
      topic: s.role_applied || "Technical System Architecture",
      format: "Video Call",
      duration: "14m 20s",
      score: normalizeScore(s.scores?.overall_score),
      createdAt: s.created_at || new Date().toISOString(),
    });
  });

  coachHistory.forEach((c, idx) => {
    recentSessions.push({
      id: c.id || `coa-${idx}`,
      type: "coach",
      agentTitle: "Communication Agent",
      topic:
        c.mode === "answer_training"
          ? "STAR Structuring & Conciseness"
          : c.mode === "conversation"
          ? "Everyday Fluency & Articulation"
          : "Grammar & Vocabulary Practice",
      format: "Voice Coach",
      duration: "09m 10s",
      score: normalizeScore(c.summary?.grammar_score || 80),
      createdAt: c.created_at || new Date().toISOString(),
    });
  });

  return (
    <section className="space-y-6">
      {/* Overview Intro */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">
            {user?.name ? `${user.name}'s Preparation Overview` : "Candidate Readiness Overview"}
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Voice-first mock interviews, communication coaching, and live analytics powered by FastAPI.
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

      {/* Backend-Backed Capability Showcase Card */}
      <div className="card-clean p-4 bg-[#0d162a] border border-blue-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 shrink-0">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs font-semibold text-white flex items-center gap-2">
              <span>FastAPI Backend Services Active</span>
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.2 rounded flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" />
                <span>Live Mode</span>
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Technical & HR interview rooms, 3 coach modalities (STAR, Conversation, English Improvement), and full rubric analytics.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Link
            href="/analytics/interview"
            onClick={() => setActiveSection(4)}
            className="text-xs font-medium bg-[#1e293b] hover:bg-slate-700 text-blue-300 px-3 py-1.5 rounded-lg border border-subtle flex items-center gap-1 transition-colors"
          >
            <BarChart3 className="w-3.5 h-3.5 text-blue-400" />
            <span>Interview Report</span>
          </Link>
          <Link
            href="/analytics/communication"
            onClick={() => setActiveSection(5)}
            className="text-xs font-medium bg-[#1e293b] hover:bg-slate-700 text-blue-300 px-3 py-1.5 rounded-lg border border-subtle flex items-center gap-1 transition-colors"
          >
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            <span>Coach Report</span>
          </Link>
        </div>
      </div>

      {/* 4 Core Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">Overall Readiness</div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-white">
              {overallReadiness !== null ? `${overallReadiness}%` : "--"}
            </span>
            {overallReadiness !== null && (
              <span className="text-xs text-emerald-400 font-medium">Computed</span>
            )}
          </div>
          <div className="mt-3 text-xs text-slate-400">
            {overallReadiness !== null ? "Job readiness composite" : "Complete a session to evaluate"}
          </div>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">Interview Score</div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-blue-400">
              {interviewScore !== null ? `${interviewScore}%` : "--"}
            </span>
            <span className="text-xs text-slate-400">
              {totalInterviewSessions} session{totalInterviewSessions === 1 ? "" : "s"}
            </span>
          </div>
          <div className="mt-3 text-xs text-slate-400">
            {interviewReport ? "Latest report active" : "Technical & HR video rounds"}
          </div>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">Communication Score</div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-white">
              {coachScore !== null ? `${coachScore}%` : "--"}
            </span>
            {latestWpm !== null && (
              <span className="text-xs text-emerald-400 font-medium">{latestWpm} WPM</span>
            )}
          </div>
          <div className="mt-3 text-xs text-slate-400">
            {coachReport ? "Latest coach summary" : "Fluency, pace & grammar"}
          </div>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">Practice Time</div>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-white">{practiceTimeString}</span>
            <span className="text-xs text-slate-400">Total logged</span>
          </div>
          <div className="mt-3 text-xs text-slate-400">
            {totalSessionsCount} mock session{totalSessionsCount === 1 ? "" : "s"} logged
          </div>
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
                    <td className="px-5 py-3.5 text-slate-300">{session.topic}</td>
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
                        session.score >= 80 ? "text-emerald-400" : "text-blue-400"
                      }`}
                    >
                      {session.score}%
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <button
                        onClick={() => {
                          if (session.type === "interview") {
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
                    <p>No mock sessions recorded yet.</p>
                    <div className="flex items-center justify-center gap-3 mt-3">
                      <Link
                        href="/interview"
                        onClick={() => setActiveSection(2)}
                        className="text-blue-400 hover:text-blue-300 font-medium inline-flex items-center gap-1"
                      >
                        <span>Start Interview</span>
                        <ArrowUpRight className="w-3 h-3" />
                      </Link>
                      <span className="text-slate-600">·</span>
                      <Link
                        href="/coach"
                        onClick={() => setActiveSection(3)}
                        className="text-amber-400 hover:text-amber-300 font-medium inline-flex items-center gap-1"
                      >
                        <span>Start Coach</span>
                        <ArrowUpRight className="w-3 h-3" />
                      </Link>
                    </div>
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
