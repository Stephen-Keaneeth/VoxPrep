"use client";

import React, { useState } from "react";
import Link from "next/link";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Connects to /auth/register in Phase 1 wiring
  };

  return (
    <div className="max-w-md mx-auto my-12 card-clean p-8 space-y-6">
      <div className="text-center space-y-1">
        <h2 className="text-2xl font-bold text-white tracking-tight">Create your account</h2>
        <p className="text-xs text-slate-400">Join VoxPrep to begin AI mock interviews and coaching.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 text-xs">
        <div>
          <label className="block text-slate-300 font-medium mb-1.5 font-mono">Full Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="w-full bg-[#0a101d] border border-subtle rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500"
            placeholder="Jordan Doe"
          />
        </div>

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
          className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2.5 rounded transition-colors text-xs"
        >
          Create Account
        </button>
      </form>

      <div className="text-center text-xs text-slate-400">
        Already have an account?{" "}
        <Link href="/login" className="text-blue-400 hover:underline">
          Sign in
        </Link>
      </div>
    </div>
  );
}

