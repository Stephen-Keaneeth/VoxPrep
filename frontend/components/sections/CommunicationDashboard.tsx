"use client";

import React from "react";
import { useAppStore } from "@/store/useStore";
import { CheckCircle2, Sparkles } from "lucide-react";

export default function CommunicationDashboard() {
  const { coachHistory } = useAppStore();

  const latestSession = coachHistory.length > 0 ? coachHistory[0] : null;
  const currentWpm = latestSession?.summary?.avg_wpm ?? 138;
  const currentFillers = latestSession?.summary?.total_fillers ?? 1.2;
  const currentGrammar = latestSession?.summary?.grammar_score ?? 94;
  const currentFluencyTier = latestSession?.summary?.fluency_tier ?? "Proficient";

  return (
    <section className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-white tracking-tight">Communication Performance Dashboard</h2>
            {latestSession && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-amber-400" />
                <span>Live Session Synced</span>
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Vocal fluency, grammar accuracy, speaking pace and filler word analytics.
          </p>
        </div>

        <span className="text-xs font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1 rounded inline-flex items-center gap-1.5 w-fit">
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>Overall Fluency: {currentFluencyTier}</span>
        </span>
      </div>

      {/* 4 Communication Vitals */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">Speaking Pace</div>
          <div className="text-3xl font-bold text-white mt-2">
            {currentWpm} <span className="text-xs font-normal text-slate-400">WPM</span>
          </div>
          <div className="mt-2 text-xs text-emerald-400">
            {currentWpm >= 130 && currentWpm <= 160 ? "Target: 130–150 WPM (Ideal)" : "Aim for steady 130–150 WPM"}
          </div>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">Filler Word Rate</div>
          <div className="text-3xl font-bold text-emerald-400 mt-2">
            {currentFillers} <span className="text-xs font-normal text-slate-400">/ session</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">Target: Less than 3 per minute</div>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">Grammar Accuracy</div>
          <div className="text-3xl font-bold text-blue-400 mt-2">{currentGrammar}%</div>
          <div className="mt-2 text-xs text-slate-400">Accurate verb tenses and agreement</div>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">Vocabulary Variety</div>
          <div className="text-3xl font-bold text-white mt-2">82%</div>
          <div className="mt-2 text-xs text-slate-400">Strong technical lexical diversity</div>
        </div>
      </div>

      {/* Filler Analysis & Weekly Trajectory */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="card-clean p-6">
          <h3 className="text-sm font-semibold text-white mb-4">Filler Word Reduction Trend</h3>
          <div className="space-y-4 text-xs">
            <div>
              <div className="flex justify-between text-slate-300 mb-1">
                <span>&quot;Like&quot;</span>
                <span className="font-mono text-slate-400">1.8 occurrences/session</span>
              </div>
              <div className="h-2 bg-[#0e1627] rounded-full overflow-hidden border border-subtle">
                <div className="h-full bg-blue-500 rounded-full" style={{ width: "35%" }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-slate-300 mb-1">
                <span>&quot;Um / Uh&quot;</span>
                <span className="font-mono text-slate-400">1.1 occurrences/session</span>
              </div>
              <div className="h-2 bg-[#0e1627] rounded-full overflow-hidden border border-subtle">
                <div className="h-full bg-blue-600 rounded-full" style={{ width: "22%" }}></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-slate-300 mb-1">
                <span>&quot;Basically&quot;</span>
                <span className="font-mono text-slate-400">0.4 occurrences/session</span>
              </div>
              <div className="h-2 bg-[#0e1627] rounded-full overflow-hidden border border-subtle">
                <div className="h-full bg-emerald-500 rounded-full" style={{ width: "8%" }}></div>
              </div>
            </div>
          </div>
        </div>

        <div className="card-clean p-6">
          <h3 className="text-sm font-semibold text-white mb-4">Weekly Speaking Progress (5-Week Trajectory)</h3>
          <div className="h-32 flex items-end justify-between gap-3 pt-4 px-2">
            <div className="flex-1 flex flex-col items-center gap-2">
              <div className="w-full bg-blue-900/40 border border-blue-500/20 rounded-t h-14 flex items-center justify-center text-[10px] text-blue-300 font-mono">
                68%
              </div>
              <span className="text-[10px] text-slate-400 font-mono">W1</span>
            </div>
            <div className="flex-1 flex flex-col items-center gap-2">
              <div className="w-full bg-blue-900/50 border border-blue-500/30 rounded-t h-18 flex items-center justify-center text-[10px] text-blue-300 font-mono">
                74%
              </div>
              <span className="text-[10px] text-slate-400 font-mono">W2</span>
            </div>
            <div className="flex-1 flex flex-col items-center gap-2">
              <div className="w-full bg-blue-900/60 border border-blue-500/40 rounded-t h-22 flex items-center justify-center text-[10px] text-blue-200 font-mono">
                79%
              </div>
              <span className="text-[10px] text-slate-400 font-mono">W3</span>
            </div>
            <div className="flex-1 flex flex-col items-center gap-2">
              <div className="w-full bg-blue-800/80 border border-blue-500/60 rounded-t h-24 flex items-center justify-center text-[10px] text-white font-mono">
                81%
              </div>
              <span className="text-[10px] text-slate-400 font-mono">W4</span>
            </div>
            <div className="flex-1 flex flex-col items-center gap-2">
              <div className="w-full bg-blue-600 rounded-t h-28 flex items-center justify-center text-[10px] text-white font-mono font-bold">
                85%
              </div>
              <span className="text-[10px] text-blue-400 font-mono font-bold">W5</span>
            </div>
          </div>
          <div className="text-[11px] text-slate-400 text-center mt-3">
            Steady 17% overall communication fluency increase over 5 weeks.
          </div>
        </div>
      </div>
    </section>
  );
}

