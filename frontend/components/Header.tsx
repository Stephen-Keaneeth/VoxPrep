"use client";

import React from "react";
import { useAppStore } from "@/store/useStore";
import { Video } from "lucide-react";

const sectionTitles: Record<number, string> = {
  1: "Home Dashboard",
  2: "AI Interview Agent (Video Call)",
  3: "AI Communication Coach",
  4: "Interview Performance Dashboard",
  5: "Communication Performance Dashboard",
};

export default function Header() {
  const { activeSection, setActiveSection } = useAppStore();

  return (
    <header className="h-16 px-8 border-b border-subtle flex items-center justify-between bg-[#0e1627] sticky top-0 z-20">
      <div className="flex items-center gap-3">
        <span className="text-xs font-mono text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 rounded">
          SECTION {activeSection} OF 5
        </span>
        <h1 className="text-base font-semibold text-white tracking-tight">
          {sectionTitles[activeSection]}
        </h1>
      </div>

      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-1.5 text-slate-400">
          <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
          <span>WebRTC & FastAPI Connected</span>
        </div>
        {activeSection !== 2 && (
          <button
            onClick={() => setActiveSection(2)}
            className="bg-blue-600 hover:bg-blue-500 text-white font-medium px-3.5 py-1.5 rounded text-xs transition-colors flex items-center gap-1.5"
          >
            <Video className="w-3.5 h-3.5" />
            <span>Join Video Interview Call</span>
          </button>
        )}
      </div>
    </header>
  );
}

