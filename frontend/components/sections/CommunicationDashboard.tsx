"use client";

import React from "react";
import Link from "next/link";
import { useStore } from "@/store/useStore";
import { normalizeScore } from "@/lib/normalization";
import { toast } from "@/store/useToast";
import type { CoachCorrection } from "@/lib/api";
import {
  Download,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  ArrowRight,
  MessageSquare,
  BookOpen,
  Award,
  Lightbulb,
  Headphones,
  Flame,
} from "lucide-react";

export default function CommunicationDashboard() {
  const { coachReport, coachSessionId, setActiveSection } = useStore();

  const handlePrint = () => {
    toast.info("Preparing Export", "Opening print dialogue for formatted report.");
    if (typeof window !== "undefined") {
      window.print();
    }
  };

  // Clean Empty State when no coach report exists
  if (!coachReport) {
    return (
      <div className="card-clean p-10 text-center space-y-6 max-w-lg mx-auto my-12 bg-[#0d1527] border border-blue-500/20 shadow-xl">
        <div className="w-14 h-14 rounded-2xl bg-blue-600/10 border border-blue-500/30 text-blue-400 mx-auto flex items-center justify-center">
          <Headphones className="w-7 h-7" />
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-bold text-white tracking-tight">
            No Coach Session Report Available
          </h2>
          <p className="text-xs text-slate-400 leading-relaxed max-w-md mx-auto">
            You haven&apos;t completed a communication coaching session yet. Practice with the AI coach in Everyday Fluency, Answer Structuring (STAR), or English Improvement mode to analyze your vocal cadence, filler words, and grammar.
          </p>
        </div>

        <div className="pt-2">
          <Link
            href="/coach"
            onClick={() => setActiveSection(3)}
            className="inline-flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-5 py-2.5 rounded-lg transition-colors shadow-sm"
          >
            <span>Practice with Coach</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    );
  }

  // Derive Session Summary Metrics
  const summary = coachReport.summary || {};
  const profile = coachReport.profile_updated || coachReport.updated_profile || {};

  const rawWpm = (summary.avg_wpm ?? summary.wpm) as number | undefined;
  const currentWpm = rawWpm !== undefined ? Math.round(rawWpm) : 140;

  const rawFillers = (summary.total_fillers ??
    summary.filler_words_count ??
    summary.corrections_count) as number | undefined;
  const currentFillers = rawFillers !== undefined ? rawFillers : 0;

  const rawGrammar = summary.grammar_score as number | undefined;
  const currentGrammar =
    rawGrammar !== undefined
      ? normalizeScore(rawGrammar)
      : summary.corrections_count === 0
      ? 100
      : Math.max(65, 100 - (Number(summary.corrections_count) * 8));

  const fluencyTier = (summary.fluency_tier ||
    profile.skill_level ||
    "Intermediate") as string;
  const capitalizedTier =
    fluencyTier.charAt(0).toUpperCase() + fluencyTier.slice(1);

  const encouragement = summary.encouragement as string | undefined;
  const keyLearnings = (summary.key_learnings || []) as string[];

  // Corrections list extracted from summary or root
  const corrections = ((summary.corrections ||
    (coachReport as unknown as { corrections?: CoachCorrection[] }).corrections ||
    []) as CoachCorrection[]);

  const modeTitle =
    summary.mode === "answer_training"
      ? "Answer Structuring (STAR Framework)"
      : summary.mode === "conversation"
      ? "Everyday Conversational Fluency"
      : summary.mode === "english_improvement"
      ? "English Grammar & Vocabulary Refinement"
      : "Adaptive Communication Coaching";

  const strongAreas = (profile.strong_areas || []) as string[];
  const weakAreas = (profile.weak_areas || []) as string[];
  const sessionsCount = profile.sessions_count ?? 1;

  return (
    <section className="space-y-6 max-w-5xl mx-auto py-2">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-[#1e293b]">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Communication Performance Dashboard
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-amber-400" />
              <span>FastAPI Coach Completed</span>
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Mode: <strong className="text-white">{modeTitle}</strong> · Vocal cadence, filler words, and linguistic precision
            {coachSessionId && (
              <span className="font-mono text-slate-500 ml-2">
                (Session: {coachSessionId.slice(0, 8)})
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <span className="text-xs font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1.5 rounded-lg inline-flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Fluency Tier: {capitalizedTier}</span>
          </span>

          <button
            onClick={handlePrint}
            className="bg-[#1e293b] hover:bg-slate-700 text-xs text-white px-3.5 py-1.5 rounded-lg border border-subtle flex items-center gap-1.5 transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-slate-300" />
            <span>Export</span>
          </button>

          <Link
            href="/coach"
            onClick={() => setActiveSection(3)}
            className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-3.5 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors shadow-sm"
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>Practice Again</span>
          </Link>
        </div>
      </div>

      {/* Encouragement / Coach Insight Banner */}
      {encouragement && (
        <div className="card-clean p-5 bg-[#0d162a] border border-blue-500/20 rounded-xl flex items-start gap-3.5">
          <Lightbulb className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs leading-relaxed text-slate-200">
            <strong className="text-white font-semibold block text-sm">
              Coach Pedagogical Insight
            </strong>
            <p>{encouragement}</p>
          </div>
        </div>
      )}

      {/* 4 Communication Vitals */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        {/* 1. Speaking Pace */}
        <div className="card-clean p-5 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-3">
          <div className="text-xs font-mono uppercase text-slate-400">Speaking Pace</div>
          <div className="text-3xl font-bold text-white">
            {currentWpm} <span className="text-xs font-normal text-slate-400 font-mono">WPM</span>
          </div>
          <div className="h-1.5 w-full bg-[#080d1a] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${
                currentWpm >= 125 && currentWpm <= 165 ? "bg-emerald-400" : "bg-blue-500"
              }`}
              style={{
                width: `${Math.min(100, Math.max(10, Math.round((currentWpm / 180) * 100)))}%`,
              }}
            />
          </div>
          <div className="text-xs text-slate-400">
            {currentWpm >= 130 && currentWpm <= 160
              ? "Target: 130–150 WPM (Ideal Cadence)"
              : "Aim for a relaxed 130–150 WPM"}
          </div>
        </div>

        {/* 2. Filler Word Rate */}
        <div className="card-clean p-5 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-3">
          <div className="text-xs font-mono uppercase text-slate-400">Filler Words</div>
          <div className="text-3xl font-bold text-emerald-400">
            {currentFillers} <span className="text-xs font-normal text-slate-400 font-mono">logged</span>
          </div>
          <div className="h-1.5 w-full bg-[#080d1a] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${
                currentFillers <= 2 ? "bg-emerald-400" : "bg-amber-400"
              }`}
              style={{
                width: `${Math.min(100, Math.max(10, 100 - currentFillers * 15))}%`,
              }}
            />
          </div>
          <div className="text-xs text-slate-400">
            {currentFillers === 0
              ? "Flawless: Zero filler words detected"
              : "Target: Less than 3 per minute"}
          </div>
        </div>

        {/* 3. Grammar Score */}
        <div className="card-clean p-5 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-3">
          <div className="text-xs font-mono uppercase text-slate-400">Grammar Score</div>
          <div className="text-3xl font-bold text-blue-400">{currentGrammar}%</div>
          <div className="h-1.5 w-full bg-[#080d1a] rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full"
              style={{ width: `${currentGrammar}%` }}
            />
          </div>
          <div className="text-xs text-slate-400">
            Past tense agreement &amp; syntax consistency
          </div>
        </div>

        {/* 4. Fluency Tier */}
        <div className="card-clean p-5 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-3">
          <div className="text-xs font-mono uppercase text-slate-400">Fluency Tier</div>
          <div className="text-3xl font-bold text-white">{capitalizedTier}</div>
          <div className="h-1.5 w-full bg-[#080d1a] rounded-full overflow-hidden">
            <div
              className="h-full bg-purple-400 rounded-full"
              style={{
                width:
                  fluencyTier === "advanced"
                    ? "100%"
                    : fluencyTier === "intermediate"
                    ? "70%"
                    : "40%",
              }}
            />
          </div>
          <div className="text-xs text-slate-400">
            Total completed sessions: <strong className="text-white font-mono">{sessionsCount}</strong>
          </div>
        </div>
      </div>

      {/* Adaptive Profile Progression Tags (from Supabase communication_profile) */}
      {(strongAreas.length > 0 || weakAreas.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="card-clean p-6 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Flame className="w-4 h-4 text-emerald-400" />
              <span>Demonstrated Communication Strengths</span>
            </h3>
            <div className="flex flex-wrap gap-2 pt-1">
              {strongAreas.length > 0 ? (
                strongAreas.map((tag, idx) => (
                  <span
                    key={idx}
                    className="text-xs font-medium px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5"
                  >
                    <CheckCircle2 className="w-3 h-3" />
                    <span>{tag}</span>
                  </span>
                ))
              ) : (
                <span className="text-xs text-slate-500 italic">
                  Continue practicing to build strength milestones.
                </span>
              )}
            </div>
          </div>

          <div className="card-clean p-6 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-3">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <span>Targeted Areas for Focus</span>
            </h3>
            <div className="flex flex-wrap gap-2 pt-1">
              {weakAreas.length > 0 ? (
                weakAreas.map((tag, idx) => (
                  <span
                    key={idx}
                    className="text-xs font-medium px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-1.5"
                  >
                    <span>{tag}</span>
                  </span>
                ))
              ) : (
                <span className="text-xs text-emerald-400 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>No high-priority weak areas currently flagged!</span>
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Key Learnings from Practice Session */}
      {keyLearnings.length > 0 && (
        <div className="card-clean p-6 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-blue-400" />
            <span>Key Learnings &amp; Techniques Practiced</span>
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            {keyLearnings.map((learning, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-lg bg-[#0a0f1d] border border-[#1e293b] flex items-start gap-2.5"
              >
                <span className="text-blue-400 font-bold leading-none mt-1">•</span>
                <span className="text-slate-200 leading-relaxed">{learning}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Structured Linguistic Corrections History */}
      <div className="card-clean p-6 bg-[#0f172a] border border-[#1e293b] rounded-xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Award className="w-4 h-4 text-amber-400" />
            <span>Logged Linguistic Corrections</span>
          </h3>
          <span className="text-xs font-mono text-slate-400">
            {corrections.length} corrections logged
          </span>
        </div>

        {corrections.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 text-xs">
            {corrections.map((corr, idx) => (
              <div
                key={idx}
                className="p-4 rounded-lg bg-[#0a0f1d] border border-[#1e293b] space-y-2"
              >
                <div className="line-through text-slate-500 font-mono text-[11px]">
                  &quot;{corr.original}&quot;
                </div>
                <div className="text-emerald-400 font-semibold text-sm">
                  → &quot;{corr.improved}&quot;
                </div>
                {corr.reason && (
                  <div className="text-slate-300 text-xs italic bg-[#101726] p-2.5 rounded border border-[#1e293b]">
                    <strong className="text-blue-300 font-mono not-italic text-[10px] block mb-0.5">
                      Grammar Rationale:
                    </strong>
                    {corr.reason}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-400 flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>
              Clear expression: No linguistic corrections needed in this session.
            </span>
          </div>
        )}
      </div>
    </section>
  );
}
