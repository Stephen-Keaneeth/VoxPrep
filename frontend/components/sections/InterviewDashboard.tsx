"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useStore } from "@/store/useStore";
import { apiClient, ApiError } from "@/lib/api";
import { normalizeScore } from "@/lib/normalization";
import { toast } from "@/store/useToast";
import {
  Download,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  ArrowRight,
  ListOrdered,
  Award,
  Compass,
  FileQuestion,
  Loader2,
  RefreshCw,
} from "lucide-react";

export default function InterviewDashboard() {
  const {
    interviewReport,
    interviewSessionId,
    setInterviewReport,
    setActiveSection,
  } = useStore();

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchReport = useCallback(
    async (sessionId: string) => {
      setIsLoading(true);
      setErrorMsg(null);
      try {
        const report = await apiClient.getInterviewReport(sessionId);
        setInterviewReport(report);
        toast.success("Report Synced", "Successfully loaded interview evaluation.");
      } catch (err: unknown) {
        let msg = "Could not retrieve the interview report from the server.";
        if (err instanceof ApiError) {
          msg = err.message;
        } else if (err instanceof Error) {
          msg = err.message;
        }
        setErrorMsg(msg);
      } finally {
        setIsLoading(false);
      }
    },
    [setInterviewReport]
  );

  // Automatically fetch from backend if report is not in memory but active sessionId is known
  useEffect(() => {
    if (!interviewReport && interviewSessionId) {
      void fetchReport(interviewSessionId);
    }
  }, [interviewReport, interviewSessionId, fetchReport]);

  // Loading State
  if (isLoading) {
    return (
      <div className="card-clean p-12 text-center space-y-4 max-w-xl mx-auto my-12 bg-[#0d1527] border border-blue-500/20">
        <div className="w-12 h-12 rounded-full bg-blue-600/20 text-blue-400 mx-auto flex items-center justify-center border border-blue-500/30">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
        <div className="space-y-1">
          <h3 className="text-lg font-bold text-white">Loading Interview Report</h3>
          <p className="text-xs text-slate-400">
            Retrieving 4-dimension evaluation rubric from the FastAPI backend...
          </p>
        </div>
      </div>
    );
  }

  // Clean Empty State when no session or report exists
  if (!interviewReport) {
    return (
      <div className="card-clean p-10 text-center space-y-6 max-w-lg mx-auto my-12 bg-[#0d1527] border border-blue-500/20 shadow-xl">
        <div className="w-14 h-14 rounded-2xl bg-blue-600/10 border border-blue-500/30 text-blue-400 mx-auto flex items-center justify-center">
          <FileQuestion className="w-7 h-7" />
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-bold text-white tracking-tight">
            No Interview Report Available
          </h2>
          <p className="text-xs text-slate-400 leading-relaxed max-w-md mx-auto">
            You haven&apos;t completed an interview session yet. Conduct a Technical or HR mock interview to receive detailed 4-dimension scoring, speech analysis, and AI recommendations.
          </p>
        </div>

        {errorMsg && (
          <div className="p-3.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 flex items-start justify-between gap-3 text-left">
            <span>{errorMsg}</span>
            {interviewSessionId && (
              <button
                onClick={() => void fetchReport(interviewSessionId)}
                className="text-red-300 underline font-mono text-[11px] shrink-0 hover:text-white"
              >
                Retry
              </button>
            )}
          </div>
        )}

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          {interviewSessionId && (
            <button
              onClick={() => void fetchReport(interviewSessionId)}
              className="w-full sm:w-auto bg-[#131d33] hover:bg-[#1a2745] text-slate-200 text-xs px-4 py-2.5 rounded-lg border border-subtle flex items-center justify-center gap-1.5 transition-colors font-medium"
            >
              <RefreshCw className="w-3.5 h-3.5 text-blue-400" />
              <span>Retry Fetching Report</span>
            </button>
          )}

          <Link
            href="/interview"
            onClick={() => setActiveSection(2)}
            className="w-full sm:w-auto bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-5 py-2.5 rounded-lg flex items-center justify-center gap-2 transition-colors shadow-sm"
          >
            <span>Start Interview</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    );
  }

  // Report Metrics (Normalized 0 - 100%)
  const overall = normalizeScore(interviewReport.overall_score);
  const relevance = normalizeScore(interviewReport.dimension_scores?.relevance);
  const depth = normalizeScore(interviewReport.dimension_scores?.depth);
  const clarity = normalizeScore(interviewReport.dimension_scores?.clarity);
  const examples = normalizeScore(interviewReport.dimension_scores?.examples);

  const strengths = interviewReport.strengths || [];
  const weaknesses =
    interviewReport.areas_for_improvement || interviewReport.weaknesses || [];
  const actionItems =
    interviewReport.action_items || interviewReport.improvement_tips || [];
  const questionBreakdown = interviewReport.question_breakdown || [];

  const handlePrint = () => {
    toast.info("Preparing Export", "Opening print dialogue for formatted report.");
    if (typeof window !== "undefined") {
      window.print();
    }
  };

  return (
    <section className="space-y-6 max-w-5xl mx-auto py-2">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-[#1e293b]">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Interview Evaluation Report
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
              <Sparkles className="w-3 h-3" />
              <span>FastAPI Backend Verified</span>
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            4-Dimension Rubric Scoring · Powered by NVIDIA Nemotron 70B
            {interviewSessionId && (
              <span className="font-mono text-slate-500 ml-2">
                (Session: {interviewSessionId.slice(0, 8)})
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-2 bg-[#121c33] border border-blue-500/20 px-3.5 py-1.5 rounded-lg text-xs font-mono">
            <Award className="w-4 h-4 text-emerald-400" />
            <span className="text-slate-300">Composite Score:</span>
            <strong className="text-emerald-400 text-sm font-bold">{overall}%</strong>
          </div>

          <button
            onClick={handlePrint}
            className="bg-[#1e293b] hover:bg-slate-700 text-xs text-white px-3.5 py-1.5 rounded-lg border border-subtle flex items-center gap-1.5 transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-slate-300" />
            <span>Export PDF</span>
          </button>
        </div>
      </div>

      {/* Hero Composite Score Card */}
      <div className="card-clean p-6 bg-gradient-to-br from-[#0e172a] via-[#111a2e] to-[#0b1120] border border-blue-500/20 rounded-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="text-xs font-mono uppercase tracking-wider text-blue-400">
              Overall Performance Rating
            </div>
            <div className="flex items-baseline gap-3">
              <span className="text-5xl font-extrabold text-white tracking-tight">
                {overall}%
              </span>
              <span className="text-xs font-mono text-slate-400">
                (Raw Scale: {interviewReport.overall_score?.toFixed(1) ?? "0.0"} / 10.0)
              </span>
            </div>
            <p className="text-xs text-slate-300 max-w-xl leading-relaxed">
              {overall >= 85
                ? "Distinguished performance demonstrating deep technical command, structured articulation, and senior-level architectural reasoning."
                : overall >= 70
                ? "Competent and solid responses across core dimensions with clear potential for further refinement."
                : "Foundational performance. Focus on structural frameworks (STAR) and concrete production metrics."}
            </p>
          </div>

          <div className="w-full md:w-64 space-y-2">
            <div className="flex justify-between text-xs font-mono text-slate-400">
              <span>Rubric Benchmark</span>
              <span className="text-emerald-400 font-bold">{overall}% Target</span>
            </div>
            <div className="h-2.5 w-full bg-[#0a0f1d] rounded-full overflow-hidden border border-[#1e293b]">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-emerald-400 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(0, overall))}%` }}
              />
            </div>
            <div className="text-[11px] text-slate-500 text-right">
              {overall >= 70 ? "Meets Hiring Standard" : "Development Recommended"}
            </div>
          </div>
        </div>
      </div>

      {/* Executive Summary Banner if present */}
      {interviewReport.summary && (
        <div className="card-clean p-5 bg-[#0d162a] border border-blue-500/20 rounded-xl flex items-start gap-3.5">
          <Sparkles className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs leading-relaxed text-slate-200">
            <strong className="text-white font-semibold block text-sm">
              Executive Evaluation Summary
            </strong>
            <p>{interviewReport.summary}</p>
          </div>
        </div>
      )}

      {/* 4 Rubric Evaluation Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        {/* 1. Relevance */}
        <div className="card-clean p-5 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-mono uppercase text-slate-400">1. Relevance</div>
            <span className="text-[10px] font-mono text-slate-500">
              {interviewReport.dimension_scores?.relevance?.toFixed(1) ?? "0.0"}/10
            </span>
          </div>
          <div className="text-3xl font-bold text-white">{relevance}%</div>
          <div className="h-1.5 w-full bg-[#080d1a] rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full"
              style={{ width: `${relevance}%` }}
            />
          </div>
          <p className="text-xs text-slate-400 leading-normal">
            Direct answer alignment with the core problem constraints.
          </p>
        </div>

        {/* 2. Technical Depth */}
        <div className="card-clean p-5 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-mono uppercase text-slate-400">2. Technical Depth</div>
            <span className="text-[10px] font-mono text-slate-500">
              {interviewReport.dimension_scores?.depth?.toFixed(1) ?? "0.0"}/10
            </span>
          </div>
          <div className="text-3xl font-bold text-blue-400">{depth}%</div>
          <div className="h-1.5 w-full bg-[#080d1a] rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-400 rounded-full"
              style={{ width: `${depth}%` }}
            />
          </div>
          <p className="text-xs text-slate-400 leading-normal">
            Engineering nuance, architecture tradeoffs, and failure domain handling.
          </p>
        </div>

        {/* 3. Clarity */}
        <div className="card-clean p-5 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-mono uppercase text-slate-400">3. Answer Clarity</div>
            <span className="text-[10px] font-mono text-slate-500">
              {interviewReport.dimension_scores?.clarity?.toFixed(1) ?? "0.0"}/10
            </span>
          </div>
          <div className="text-3xl font-bold text-white">{clarity}%</div>
          <div className="h-1.5 w-full bg-[#080d1a] rounded-full overflow-hidden">
            <div
              className="h-full bg-purple-400 rounded-full"
              style={{ width: `${clarity}%` }}
            />
          </div>
          <p className="text-xs text-slate-400 leading-normal">
            Pacing, structured delivery, and cohesive narrative flow.
          </p>
        </div>

        {/* 4. Examples */}
        <div className="card-clean p-5 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-mono uppercase text-slate-400">4. Structural Examples</div>
            <span className="text-[10px] font-mono text-slate-500">
              {interviewReport.dimension_scores?.examples?.toFixed(1) ?? "0.0"}/10
            </span>
          </div>
          <div className="text-3xl font-bold text-emerald-400">{examples}%</div>
          <div className="h-1.5 w-full bg-[#080d1a] rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-400 rounded-full"
              style={{ width: `${examples}%` }}
            />
          </div>
          <p className="text-xs text-slate-400 leading-normal">
            Quantifiable benchmarks, production metrics, and concrete patterns.
          </p>
        </div>
      </div>

      {/* Coach Recommendation CTA Banner */}
      {interviewReport.coach_recommendation && (
        <div className="card-clean p-5 bg-[#101b33] border border-blue-500/30 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-lg">
          <div className="flex items-start gap-3.5">
            <div className="p-2.5 rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30 shrink-0">
              <Compass className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xs font-mono text-blue-300 uppercase tracking-wider font-semibold">
                AI Coach Recommendation
              </div>
              <p className="text-xs text-slate-200 mt-1 leading-relaxed">
                {interviewReport.coach_recommendation}
              </p>
            </div>
          </div>

          <Link
            href="/coach"
            onClick={() => setActiveSection(3)}
            className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-4 py-2.5 rounded-lg flex items-center justify-center gap-1.5 transition-colors shrink-0 shadow-sm"
          >
            <span>Start Coach Session</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      )}

      {/* Strengths & Weaknesses */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="card-clean p-6 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Key Strengths Identified</span>
          </h3>
          <ul className="space-y-2.5 text-xs text-slate-300">
            {strengths.length > 0 ? (
              strengths.map((strength, idx) => (
                <li key={idx} className="flex items-start gap-2.5">
                  <span className="text-emerald-400 font-bold leading-none mt-1">•</span>
                  <span className="leading-relaxed">{strength}</span>
                </li>
              ))
            ) : (
              <li className="text-slate-500 italic">No specific strengths cataloged.</li>
            )}
          </ul>
        </div>

        <div className="card-clean p-6 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>Targeted Areas for Growth</span>
          </h3>
          <ul className="space-y-2.5 text-xs text-slate-300">
            {weaknesses.length > 0 ? (
              weaknesses.map((weakness, idx) => (
                <li key={idx} className="flex items-start gap-2.5">
                  <span className="text-amber-400 font-bold leading-none mt-1">•</span>
                  <span className="leading-relaxed">{weakness}</span>
                </li>
              ))
            ) : (
              <li className="text-slate-500 italic">No specific growth areas flagged.</li>
            )}
          </ul>
        </div>
      </div>

      {/* Action Items */}
      {actionItems.length > 0 && (
        <div className="card-clean p-6 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <ListOrdered className="w-4 h-4 text-blue-400" />
            <span>Recommended Action Items</span>
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            {actionItems.map((item, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-lg bg-[#0a0f1d] border border-[#1e293b] flex items-start gap-3"
              >
                <span className="w-5 h-5 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center font-mono text-[10px] shrink-0 mt-0.5">
                  {idx + 1}
                </span>
                <span className="text-slate-300 leading-relaxed">{item}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Question Breakdown Table */}
      {questionBreakdown.length > 0 && (
        <div className="card-clean p-6 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Award className="w-4 h-4 text-purple-400" />
              <span>Per-Question Rubric Breakdown</span>
            </h3>
            <span className="text-xs font-mono text-slate-400">
              {questionBreakdown.length} questions evaluated
            </span>
          </div>

          <div className="space-y-3.5">
            {questionBreakdown.map((item, idx) => (
              <div
                key={idx}
                className="p-4 rounded-lg bg-[#0a0f1d] border border-[#1e293b] space-y-3 text-xs"
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
                  <div className="font-semibold text-white text-sm">
                    Q{idx + 1}: &quot;{item.question}&quot;
                  </div>
                  <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400 shrink-0 bg-[#0f172a] px-2.5 py-1 rounded border border-[#1e293b]">
                    <span>Rel: <strong className="text-white">{normalizeScore(item.scores?.relevance)}%</strong></span>
                    <span>Clr: <strong className="text-white">{normalizeScore(item.scores?.clarity)}%</strong></span>
                    <span>Dep: <strong className="text-blue-400">{normalizeScore(item.scores?.depth)}%</strong></span>
                    <span>Ex: <strong className="text-emerald-400">{normalizeScore(item.scores?.examples)}%</strong></span>
                  </div>
                </div>

                {item.answer_summary && (
                  <div className="text-slate-300 text-xs">
                    <strong className="text-slate-400 font-mono">Answer Summary: </strong>
                    <span className="italic">{item.answer_summary}</span>
                  </div>
                )}

                {item.feedback && (
                  <div className="p-3 rounded-lg bg-[#121c33] border border-blue-500/20 text-slate-200">
                    <strong className="text-blue-300 font-mono text-[11px] block mb-0.5">
                      Evaluator Rubric Feedback:
                    </strong>
                    <p className="leading-relaxed">{item.feedback}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
