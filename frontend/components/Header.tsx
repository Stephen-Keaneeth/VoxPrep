"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAppStore, SectionId } from "@/store/useStore";
import { Video, RefreshCw, LogIn, UserPlus, LogOut } from "lucide-react";
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
  const { activeSection, setActiveSection, user, setUser, clearSession } = useAppStore();
  const pathname = usePathname();
  const router = useRouter();
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
      toast.warning("Backend offline", "Ensure backend is running on port 8000 (uvicorn app.main:app).");
    }
  };

  const handleSignOut = () => {
    setUser(null, null);
    clearSession();
    toast.info("Signed out", "Candidate session cleared.");
    router.push("/login");
  };

  const headerTitle =
    pathname === "/login"
      ? "Candidate Sign In"
      : pathname === "/register"
      ? "Create Candidate Account"
      : sectionTitles[activeSection] || "VOXPREP";

  return (
    <header className="h-16 px-8 border-b border-subtle flex items-center justify-between bg-[#0e1627] sticky top-0 z-20">
      <div className="flex items-center gap-3">
        {pathname !== "/login" && pathname !== "/register" && (
          <span className="text-xs font-mono text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 rounded">
            SECTION {activeSection} OF 5
          </span>
        )}
        <h1 className="text-base font-semibold text-white tracking-tight">
          {headerTitle}
        </h1>
      </div>

      <div className="flex items-center gap-3 text-xs">
        {/* Backend Health Probe Pill */}
        <button
          onClick={handleTestConnection}
          className="flex items-center gap-1.5 text-slate-400 hover:text-slate-200 px-2.5 py-1 rounded bg-[#0a101d] border border-subtle transition-colors group"
          title="Click to re-check FastAPI backend status"
        >
          <span
            className={`w-2 h-2 rounded-full ${
              isBackendOnline ? "bg-emerald-500" : isBackendOnline === false ? "bg-red-400" : "bg-blue-400 animate-pulse"
            }`}
          />
          <span className="hidden sm:inline font-mono text-[11px]">
            {isBackendOnline
              ? "FastAPI Connected (127.0.0.1:8000)"
              : isBackendOnline === false
              ? "FastAPI Offline (127.0.0.1:8000)"
              : "Checking FastAPI..."}
          </span>
          <RefreshCw className="w-3 h-3 text-slate-500 group-hover:text-slate-300 ml-0.5 transition-transform group-hover:rotate-180" />
        </button>

        {/* User Auth Controls */}
        {user ? (
          <div className="flex items-center gap-2">
            <span className="font-mono text-slate-300 text-[11px] bg-[#111A2E] px-2 py-1 rounded border border-subtle hidden sm:inline">
              {user.name}
            </span>
            <button
              onClick={handleSignOut}
              className="text-slate-400 hover:text-red-300 p-1.5 rounded hover:bg-red-500/10 transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          pathname !== "/login" &&
          pathname !== "/register" && (
            <div className="hidden md:flex items-center gap-2">
              <Link
                href="/login"
                className="text-slate-300 hover:text-white px-2.5 py-1 rounded transition-colors flex items-center gap-1"
              >
                <LogIn className="w-3 h-3 text-slate-400" />
                <span>Sign In</span>
              </Link>
              <Link
                href="/register"
                className="bg-[#1e293b] hover:bg-slate-700 text-slate-200 px-2.5 py-1 rounded border border-subtle transition-colors flex items-center gap-1"
              >
                <UserPlus className="w-3 h-3 text-blue-400" />
                <span>Register</span>
              </Link>
            </div>
          )
        )}

        {/* Action Button: Jump into Interview Agent */}
        {activeSection !== 2 && pathname !== "/interview" && (
          <Link
            href="/interview"
            onClick={() => setActiveSection(2)}
            className="bg-blue-600 hover:bg-blue-500 text-white font-medium px-3.5 py-1.5 rounded text-xs transition-colors flex items-center gap-1.5 shadow-sm"
          >
            <Video className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Join Video Interview</span>
            <span className="sm:hidden">Interview</span>
          </Link>
        )}
      </div>
    </header>
  );
}
