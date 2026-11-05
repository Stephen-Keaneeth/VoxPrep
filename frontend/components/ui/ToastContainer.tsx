"use client";

import React from "react";
import { useToastStore, ToastType } from "@/store/useToast";
import { CheckCircle2, AlertCircle, AlertTriangle, Sparkles, X } from "lucide-react";

const toastIcons: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />,
  error: <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />,
  warning: <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />,
  info: <Sparkles className="w-4 h-4 text-blue-400 shrink-0" />,
};

const toastBorders: Record<ToastType, string> = {
  success: "border-emerald-500/30 bg-[#0c1824]",
  error: "border-rose-500/30 bg-[#1c1218]",
  warning: "border-amber-500/30 bg-[#1e1912]",
  info: "border-blue-500/30 bg-[#0e1628]",
};

export default function ToastContainer() {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      className="fixed bottom-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none"
    >
      {toasts.map((item) => (
        <div
          key={item.id}
          className={`pointer-events-auto p-3.5 rounded-lg border shadow-xl flex items-start gap-3 transition-all animate-fade-in ${
            toastBorders[item.type]
          }`}
        >
          <div className="mt-0.5">{toastIcons[item.type]}</div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-white tracking-tight">{item.message}</p>
            {item.description && (
              <p className="text-[11px] text-slate-300 mt-0.5 leading-relaxed">{item.description}</p>
            )}
          </div>
          <button
            onClick={() => removeToast(item.id)}
            className="text-slate-400 hover:text-white p-0.5 rounded transition-colors"
            title="Dismiss notification"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}

