"use client";

import React from "react";
import { Download, CheckCircle2, AlertTriangle } from "lucide-react";

export default function InterviewDashboard() {
  return (
    <section className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between pb-1">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Interview Performance Dashboard</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Evaluation report generated from your recent video call interview session.
          </p>
        </div>

        <button className="bg-[#1e293b] hover:bg-slate-700 text-xs text-white px-3 py-1.5 rounded border border-subtle flex items-center gap-1.5 transition-colors">
          <Download className="w-3.5 h-3.5" />
          <span>Export PDF Report</span>
        </button>
      </div>

      {/* 4 Rubric Evaluation Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">1. Relevance</div>
          <div className="text-3xl font-bold text-white mt-2">92%</div>
          <p className="text-xs text-slate-400 mt-2">Direct response to the architectural scenario.</p>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">2. Technical Depth</div>
          <div className="text-3xl font-bold text-blue-400 mt-2">86%</div>
          <p className="text-xs text-slate-400 mt-2">Proper trade-off analysis between Kafka vs RabbitMQ.</p>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">3. Answer Clarity</div>
          <div className="text-3xl font-bold text-white mt-2">88%</div>
          <p className="text-xs text-slate-400 mt-2">Structured delivery with clear step boundaries.</p>
        </div>

        <div className="card-clean p-5">
          <div className="text-xs font-mono uppercase text-slate-400">4. Structural Examples</div>
          <div className="text-3xl font-bold text-emerald-400 mt-2">80%</div>
          <p className="text-xs text-slate-400 mt-2">Good mention of idempotency keys in Redis.</p>
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
            <li className="flex items-start gap-2">
              <span className="text-emerald-400 font-bold">•</span>
              <span>
                <strong>Video Presence & Composure:</strong> Maintained eye contact with the camera and steady pacing
                while answering.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-emerald-400 font-bold">•</span>
              <span>
                <strong>Concise Delivery:</strong> Stayed within the 90–120 second recommended window per question
                without drifting.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-emerald-400 font-bold">•</span>
              <span>
                <strong>System Resilience:</strong> Accurately isolated consumer failure domains with circuit breakers.
              </span>
            </li>
          </ul>
        </div>

        <div className="card-clean p-6">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>Targeted Areas for Growth</span>
          </h3>
          <ul className="space-y-2.5 text-xs text-slate-300">
            <li className="flex items-start gap-2">
              <span className="text-amber-400 font-bold">•</span>
              <span>
                <strong>Quantitative Metrics:</strong> State expected QPS and storage costs explicitly before choosing
                database tier.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-amber-400 font-bold">•</span>
              <span>
                <strong>Error Handling:</strong> Explicitly mention Dead Letter Queues (DLQ) during consumer poison-pill
                scenarios.
              </span>
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}

