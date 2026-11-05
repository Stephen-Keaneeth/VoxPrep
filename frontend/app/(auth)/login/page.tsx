"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/store/useStore";
import { loginUser } from "@/lib/api";
import { toast } from "@/store/useToast";
import { Loader2, AlertCircle } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { setUser, setActiveSection } = useAppStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);

    try {
      const data = await loginUser(email, password);
      setUser({
        id: data.user.id,
        email: data.user.email,
        name: data.user.name || "Candidate",
        token: data.access_token,
      });
      toast.success("Welcome back!", `Signed in as ${data.user.name || "Candidate"}`);
      setActiveSection(1);
      router.push("/dashboard");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to authenticate. Please check your credentials.";
      setErrorMsg(msg);
      toast.error("Authentication failed", msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto my-12 card-clean p-8 space-y-6">
      <div className="text-center space-y-1">
        <h2 className="text-2xl font-bold text-white tracking-tight">Sign in to VoxPrep</h2>
        <p className="text-xs text-slate-400">
          FastAPI & Supabase Auth connected. Enter your credentials below.
        </p>
      </div>

      {errorMsg && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4 text-xs">
        <div>
          <label className="block text-slate-300 font-medium mb-1.5 font-mono">Email Address</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full bg-[#0a101d] border border-subtle rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label className="block text-slate-300 font-medium mb-1.5 font-mono">Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full bg-[#0a101d] border border-subtle rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500"
            placeholder="••••••••"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold py-2.5 rounded transition-colors text-xs flex items-center justify-center gap-2"
        >
          {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
          <span>{isLoading ? "Authenticating with Supabase..." : "Sign In"}</span>
        </button>
      </form>

      <div className="text-center text-xs text-slate-400">
        Don&apos;t have an account?{" "}
        <Link href="/register" className="text-blue-400 hover:underline">
          Create one
        </Link>
      </div>
    </div>
  );
}
