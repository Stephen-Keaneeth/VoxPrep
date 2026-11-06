"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useStore } from "@/store/useStore";
import { apiClient, ApiError } from "@/lib/api";
import { toast } from "@/store/useToast";
import { Loader2, AlertCircle, ArrowRight, UserPlus } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const { setUser, setActiveSection } = useStore();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);

    try {
      const res = await apiClient.register({
        name: name.trim() || undefined,
        email: email.trim(),
        password,
      });
      setUser(res.user, res.access_token);
      toast.success(
        "Account created!",
        `Welcome ${res.user.name || "Candidate"}. Profile initialized.`
      );
      setActiveSection(2);
      router.push("/interview");
    } catch (err: unknown) {
      let msg = "Registration failed. Please check your inputs.";
      if (err instanceof ApiError) {
        msg = err.message;
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setErrorMsg(msg);
      toast.error("Registration Failed", msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleContinueAsGuest = (destination: "/interview" | "/coach") => {
    setActiveSection(destination === "/interview" ? 2 : 3);
    router.push(destination);
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md bg-[#0d1527] border border-blue-500/20 rounded-xl p-8 shadow-2xl space-y-6">
        <div className="text-center space-y-1.5">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded-lg bg-blue-600/20 border border-blue-500/30 text-blue-400 mb-2">
            <UserPlus className="w-5 h-5" />
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Create your account</h2>
          <p className="text-xs text-slate-400">
            FastAPI &amp; Supabase Auth verified. Initializes your communication profile.
          </p>
        </div>

        {errorMsg && (
          <div className="p-3.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span className="leading-relaxed">{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block text-slate-300 font-medium mb-1.5 font-mono">Full Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-[#080d1a] border border-[#1e293b] rounded-lg px-3.5 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
              placeholder="Candidate Name"
            />
          </div>

          <div>
            <label className="block text-slate-300 font-medium mb-1.5 font-mono">Email Address</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full bg-[#080d1a] border border-[#1e293b] rounded-lg px-3.5 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-slate-300 font-medium mb-1.5 font-mono">
              Password <span className="text-slate-500 text-[10px]">(min 6 characters)</span>
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="w-full bg-[#080d1a] border border-[#1e293b] rounded-lg px-3.5 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg transition-colors text-xs flex items-center justify-center gap-2 shadow-sm"
          >
            {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>{isLoading ? "Creating account..." : "Create Account"}</span>
          </button>
        </form>

        <div className="relative my-4">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-[#1e293b]"></div>
          </div>
          <div className="relative flex justify-center text-[11px] uppercase">
            <span className="bg-[#0d1527] px-2 text-slate-500 font-mono">Or</span>
          </div>
        </div>

        {/* Guest Access Options */}
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => handleContinueAsGuest("/interview")}
            className="w-full bg-[#111c33] hover:bg-[#162442] text-slate-200 hover:text-white border border-blue-500/20 py-2.5 px-4 rounded-lg text-xs font-medium transition-colors flex items-center justify-between"
          >
            <span>Continue as Guest to Interview</span>
            <ArrowRight className="w-3.5 h-3.5 text-blue-400" />
          </button>

          <button
            type="button"
            onClick={() => handleContinueAsGuest("/coach")}
            className="w-full bg-[#0e1627] hover:bg-[#131f38] text-slate-300 hover:text-white border border-[#1e293b] py-2.5 px-4 rounded-lg text-xs font-medium transition-colors flex items-center justify-between"
          >
            <span>Continue as Guest to Coach Room</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
          </button>
        </div>

        <div className="text-center text-xs text-slate-400 pt-2 border-t border-[#1e293b]">
          Already have an account?{" "}
          <Link href="/login" className="text-blue-400 hover:text-blue-300 font-medium">
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
