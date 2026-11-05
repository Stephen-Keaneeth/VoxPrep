"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppStore, SectionId } from "@/store/useStore";
import { Video, RefreshCw } from "lucide-react";
import { checkBackendHealth } from "@/lib/api";
import { toast } from "@/store/useToast";

const sectionTitles: Record<number, string> = {
  1: "Home Dashboard",
  2: "AI Interview Agent (Video Call)",
  3: "AI Communication Coach",
  4: "Interview Performance Dashboard",
  5: "Communication Performance Dashboard",
};

export default function Header() {
  const { activeSection, setActiveSection } = useAppStore();
  const pathname = usePathname();
  const [isBackendOnline, setIsBackendOnline] = useState<boolean | null>(null);

  // Synchronize activeSection with current URL pathname
  useEffect(() => {
    let section: SectionId = 1;
    if (pathname === "/interview") section = 2;
    else if (pathname === "/coach") section = 3;
    else if (pathname === "/analytics/interview") section = 4;
    else if (pathname === "/analytics/communication") section = 5;
    else if (pathname === "/" || pathname === "/dashboard") section = 1;

    if (activeSection !== section) {
      setActiveSection(section);
    }
  }, [pathname, activeSection, setActiveSection]);

  useEffect(() => {
    let mounted = true;
    checkBackendHealth()
      .then((healthy) => {
        if (mounted) setIsBackendOnline(healthy);
      })
      .catch(() => {
        if (mounted) setIsBackendOnline(false);
      });

    const interval = setInterval(() => {
      checkBackendHealth()
        .then((healthy) => {
          if (mounted) setIsBackendOnline(healthy);
        })
        .catch(() => {
          if (mounted) setIsBackendOnline(false);
        });
    }, 30000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleTestConnection = async () => {
    setIsBackendOnline(null);
    const healthy = await checkBackendHealth();
    setIsBackendOnline(healthy);
    if (healthy) {
      toast.success("FastAPI connected", "Backend server online on port 8000.");
    } else {
      toast.warning("Backend offline", "Voice fallback mode active. Ensure backend is running on port 8000.");
    }
  };

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
        <button
          onClick={handleTestConnection}
          className="flex items-center gap-1.5 text-slate-400 hover:text-slate-200 p-1 rounded transition-colors group"
          title="Click to re-check FastAPI backend status"
        >
          <span
            className={`w-2 h-2 rounded-full ${
              isBackendOnline ? "bg-emerald-500" : isBackendOnline === false ? "bg-amber-400" : "bg-blue-400 animate-pulse"
            }`}
          ></span>
          <span>
            {isBackendOnline
              ? "FastAPI & Supabase Connected"
              : isBackendOnline === false
              ? "Local Voice & State Fallback"
              : "Checking Services..."}
          </span>
          <RefreshCw className="w-3 h-3 text-slate-500 group-hover:text-slate-300 ml-0.5 transition-transform group-hover:rotate-180" />
        </button>
        {activeSection !== 2 && pathname !== "/interview" && (
          <Link
            href="/interview"
            onClick={() => setActiveSection(2)}
            className="bg-blue-600 hover:bg-blue-500 text-white font-medium px-3.5 py-1.5 rounded text-xs transition-colors flex items-center gap-1.5 shadow-sm"
          >
            <Video className="w-3.5 h-3.5" />
            <span>Join Video Interview Call</span>
          </Link>
        )}
      </div>
    </header>
  );
}
