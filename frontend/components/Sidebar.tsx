"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppStore, SectionId } from "@/store/useStore";
import {
  LayoutDashboard,
  Video,
  MessageSquare,
  BarChart3,
  Activity,
  CheckCircle2,
} from "lucide-react";

export default function Sidebar() {
  const { activeSection, setActiveSection, user } = useAppStore();
  const pathname = usePathname();

  const userInitials = user?.name
    ? user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "AN";

  const navItems: { id: SectionId; label: string; icon: React.ReactNode; badge?: string; href: string }[] = [
    {
      id: 1,
      label: "Home Dashboard",
      icon: <LayoutDashboard className="w-4 h-4 text-blue-400 shrink-0" />,
      href: "/",
    },
    {
      id: 2,
      label: "Interview Agent",
      icon: <Video className="w-4 h-4 text-slate-400 shrink-0" />,
      badge: "Video Call",
      href: "/interview",
    },
    {
      id: 3,
      label: "Communication Agent",
      icon: <MessageSquare className="w-4 h-4 text-slate-400 shrink-0" />,
      href: "/coach",
    },
    {
      id: 4,
      label: "Interview Dashboard",
      icon: <BarChart3 className="w-4 h-4 text-slate-400 shrink-0" />,
      href: "/analytics/interview",
    },
    {
      id: 5,
      label: "Communication Dashboard",
      icon: <Activity className="w-4 h-4 text-slate-400 shrink-0" />,
      href: "/analytics/communication",
    },
  ];

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

  const isItemActive = (item: (typeof navItems)[0]) => {
    if (item.id === 1) {
      return pathname === "/" || pathname === "/dashboard" || activeSection === 1;
    }
    return pathname === item.href || activeSection === item.id;
  };

  return (
    <aside className="w-64 bg-[#0a101d] border-r border-subtle flex flex-col justify-between shrink-0 h-screen sticky top-0 select-none">
      <div>
        {/* Brand Header */}
        <Link
          href="/"
          onClick={() => setActiveSection(1)}
          className="px-6 py-5 border-b border-subtle flex items-center justify-between hover:bg-slate-800/30 transition-colors block"
        >
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded bg-blue-600 flex items-center justify-center font-bold text-white text-sm shadow-md">
              V
            </div>
            <span className="font-bold tracking-tight text-base text-white">VOXPREP</span>
          </div>
          <span className="text-[11px] font-mono uppercase bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded">
            Pro
          </span>
        </Link>

        {/* Section Navigation */}
        <nav className="p-3 space-y-1 text-sm font-medium">
          {navItems.slice(0, 3).map((item) => {
            const active = isItemActive(item);
            return (
              <Link
                key={item.id}
                href={item.href}
                onClick={() => setActiveSection(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-left transition-colors ${
                  active
                    ? "bg-[#1E293B] text-white font-medium shadow-sm"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                }`}
              >
                {item.icon}
                <span className="flex items-center justify-between flex-1">
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="text-[10px] font-mono bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded">
                      {item.badge}
                    </span>
                  )}
                </span>
              </Link>
            );
          })}

          <div className="pt-4 pb-1 px-3">
            <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
              Analytics & Reports
            </span>
          </div>

          {navItems.slice(3).map((item) => {
            const active = isItemActive(item);
            return (
              <Link
                key={item.id}
                href={item.href}
                onClick={() => setActiveSection(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-left transition-colors ${
                  active
                    ? "bg-[#1E293B] text-white font-medium shadow-sm"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                }`}
              >
                {item.icon}
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Candidate Footer */}
      <div className="p-4 border-t border-subtle bg-[#080d18]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-xs font-semibold text-white">
            {userInitials}
          </div>
          <div className="text-xs overflow-hidden">
            <div className="font-medium text-white truncate">{user?.name || "Candidate"}</div>
            <div className="text-slate-400 truncate text-[11px] flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-emerald-400 inline" />
              <span>{user?.email || "candidate@voxprep.internal"}</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
