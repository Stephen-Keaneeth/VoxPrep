"use client";

import React from "react";
import { useAppStore } from "@/store/useStore";
import { toast } from "@/store/useToast";
import { Download, CheckCircle2, AlertTriangle, Sparkles } from "lucide-react";

export default function InterviewDashboard() {
  const { latestEvaluation } = useAppStore();

  const evalData = latestEvaluation || {
    candidate_name: "Anish",
    role_applied: "Senior Backend / Distributed Systems Engineer",
    scores: {
      overall_score: 88,
      relevance: 92,
      technical_depth: 86,
      clarity: 88,
      examples: 80,
    },
    report: {
      strengths: [
        "Video Presence & Composure: Maintained eye contact with the camera and steady pacing while answering.",
        "Concise Delivery: Stayed within the 90–120 second recommended window per question without drifting.",
        "System Resilience: Accurately isolated consumer failure domains with circuit breakers.",
      ],
      weaknesses: [
        "Quantitative Metrics: State expected QPS and storage costs explicitly before choosing database tier.",
        "Error Handling: Explicitly mention Dead Letter Queues (DLQ) during consumer poison-pill scenarios.",
      ],
    },
  };

  return (
    <section className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-white tracking-tight">Interview Performance Dashboard</h2>
            {latestEvaluation && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                <span>Latest Session Evaluated</span>
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Role: <strong className="text-white">{evalData.role_applied}</strong> · Evaluated by NVIDIA Nemotron & Rubric
          </p>
        </div>

        <button
          onClick={() => {
            toast.info("Generating report", "Preparing formatted interview evaluation...");
            setTimeout(() => {
              if (typeof window !== "undefined") window.print();
            }, 300);
          }}
          className="bg-[#1e293b] hover:bg-slate-700 text-xs text-white px-3.5 py-1.5 rounded border border-subtle flex items-center gap-1.5 transition-colors w-fit"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Export PDF Report</span>
        </button>
      </div>

      {/* 4 Rubric Evaluation Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">1. Relevance</div>
          <div className="text-3xl font-bold text-white mt-2">{evalData.scores?.relevance ?? 92}%</div>
          <p className="text-xs text-slate-400 mt-2">Direct response to the architectural scenario.</p>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">2. Technical Depth</div>
          <div className="text-3xl font-bold text-blue-400 mt-2">{evalData.scores?.technical_depth ?? 86}%</div>
          <p className="text-xs text-slate-400 mt-2">Proper trade-off analysis between distributed components.</p>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">3. Answer Clarity</div>
          <div className="text-3xl font-bold text-white mt-2">{evalData.scores?.clarity ?? 88}%</div>
          <p className="text-xs text-slate-400 mt-2">Structured delivery with clear step boundaries.</p>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">4. Structural Examples</div>
          <div className="text-3xl font-bold text-emerald-400 mt-2">{evalData.scores?.examples ?? 80}%</div>
          <p className="text-xs text-slate-400 mt-2">Concrete mention of production patterns and keys.</p>
        </div>
      </div>

      {/* Strengths & Weaknesses */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="card-clean p-6">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Key Strengths Identified</span>
          </h3>
          <ul className="space-y-2.5 text-xs text-slate-300">
            {evalData.report?.strengths?.map((strength, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-emerald-400 font-bold">•</span>
                <span>{strength}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="card-clean p-6">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>Targeted Areas for Growth</span>
          </h3>
          <ul className="space-y-2.5 text-xs text-slate-300">
            {evalData.report?.weaknesses?.map((weakness, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-amber-400 font-bold">•</span>
                <span>{weakness}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
