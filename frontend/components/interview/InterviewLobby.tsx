"use client";

import React, { useState, useRef, useEffect } from "react";
import { useStore } from "@/store/useStore";
import type { InterviewStartRequest } from "@/lib/api";
import {
  Video,
  VideoOff,
  Mic,
  MicOff,
  ArrowRight,
  Sparkles,
  ShieldCheck,
  Code2,
  Users,
  Briefcase,
  Award,
  Loader2,
} from "lucide-react";

interface InterviewLobbyProps {
  onStartInterview?: (params: InterviewStartRequest) => Promise<void>;
  isStarting?: boolean;
}

export default function InterviewLobby({
  onStartInterview,
  isStarting = false,
}: InterviewLobbyProps) {
  const { user, guestUserId } = useStore();

  // Device pre-check state
  const videoPreviewRef = useRef<HTMLVideoElement | null>(null);
  const [previewStream, setPreviewStream] = useState<MediaStream | null>(null);
  const [isCameraActive, setIsCameraActive] = useState(true);
  const [isMicActive, setIsMicActive] = useState(true);
  const [deviceError, setDeviceError] = useState<string | null>(null);

  // Form State for Interview Configuration
  const [candidateName, setCandidateName] = useState(user?.name || "Candidate");
  const [targetRole, setTargetRole] = useState("Senior Backend Engineer");
  const [experienceLevel, setExperienceLevel] = useState("Senior");
  const [interviewType, setInterviewType] = useState<"technical" | "hr">("technical");

  // Keep candidate name in sync if user logs in
  useEffect(() => {
    if (user?.name) {
      setCandidateName(user.name);
    }
  }, [user?.name]);

  // Initialize camera for device self-test preview
  useEffect(() => {
    let localStream: MediaStream | null = null;
    let isCancelled = false;

    async function initPreview() {
      try {
        localStream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
          audio: { echoCancellation: true, noiseSuppression: true },
        });

        if (isCancelled) {
          localStream.getTracks().forEach((track) => track.stop());
          return;
        }

        setPreviewStream(localStream);
        if (videoPreviewRef.current) {
          videoPreviewRef.current.srcObject = localStream;
        }
        setDeviceError(null);
      } catch (err) {
        console.warn("Could not access camera/mic for lobby preview:", err);
        setDeviceError("Camera or microphone access unavailable. You can still proceed in avatar mode.");
        setIsCameraActive(false);
      }
    }

    initPreview();

    return () => {
      isCancelled = true;
      if (localStream) {
        localStream.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const toggleCamera = () => {
    if (previewStream) {
      const videoTrack = previewStream.getVideoTracks()[0];
      if (videoTrack) {
        videoTrack.enabled = !videoTrack.enabled;
        setIsCameraActive(videoTrack.enabled);
        return;
      }
    }
    setIsCameraActive(!isCameraActive);
  };

  const toggleMic = () => {
    if (previewStream) {
      const audioTrack = previewStream.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        setIsMicActive(audioTrack.enabled);
        return;
      }
    }
    setIsMicActive(!isMicActive);
  };

  const handleLaunch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (previewStream) {
      previewStream.getTracks().forEach((track) => track.stop());
      setPreviewStream(null);
    }

    if (onStartInterview) {
      await onStartInterview({
        candidate_name: candidateName.trim() || "Candidate",
        role: targetRole.trim() || "Software Engineer",
        experience_level: experienceLevel,
        interview_type: interviewType,
        user_id: user?.id || null,
      });
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto py-2">
      <div className="bg-[#111A2E] border border-subtle rounded-xl p-6 shadow-2xl">
        {/* Lobby Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-5 border-b border-subtle">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight">
                AI Interview Readiness & Setup
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Configure your interview session and verify camera & microphone inputs.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono px-2.5 py-1 rounded bg-[#0B1120] border border-subtle text-slate-300 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
              <span>{user ? `Signed in as ${user.name || user.email}` : `Guest Candidate (${guestUserId.slice(0, 8)})`}</span>
            </span>
          </div>
        </div>

        <form onSubmit={handleLaunch} className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Left Column: Device Self-Test Preview */}
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs font-medium text-slate-300">
              <span>Candidate Preview</span>
              <span className="text-[10px] font-mono text-slate-400">WebRTC 720p</span>
            </div>

            <div className="relative aspect-video rounded-lg overflow-hidden bg-[#0B1120] border border-subtle flex items-center justify-center">
              {isCameraActive ? (
                <video
                  ref={videoPreviewRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-full object-cover video-mirror"
                />
              ) : (
                <div className="flex flex-col items-center gap-2 text-slate-500 p-4 text-center">
                  <VideoOff className="w-10 h-10 text-slate-600" />
                  <span className="text-xs font-medium text-slate-400">Camera preview is off</span>
                  <span className="text-[11px] text-slate-500">Audio input will remain active during the interview.</span>
                </div>
              )}

              {/* Status Overlay */}
              <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between px-2.5 py-1.5 rounded bg-black/75 backdrop-blur text-[10px] font-mono text-slate-300 border border-white/5">
                <span className="flex items-center gap-1.5">
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      isCameraActive ? "bg-emerald-400 animate-pulse" : "bg-slate-500"
                    }`}
                  />
                  <span>{isCameraActive ? "Camera Ready" : "Camera Off"}</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      isMicActive ? "bg-emerald-400" : "bg-red-400"
                    }`}
                  />
                  <span>{isMicActive ? "Mic Ready" : "Mic Muted"}</span>
                </span>
              </div>
            </div>

            {deviceError && (
              <p className="text-[11px] text-amber-400/90 font-mono bg-amber-500/10 border border-amber-500/20 px-2.5 py-1.5 rounded">
                {deviceError}
              </p>
            )}

            {/* Device Toggle Controls */}
            <div className="flex items-center justify-center gap-3 pt-1">
              <button
                type="button"
                onClick={toggleMic}
                className={`px-3 py-1.5 rounded-lg border text-xs font-medium flex items-center gap-1.5 transition-colors ${
                  isMicActive
                    ? "bg-[#0B1120] border-subtle text-slate-200 hover:bg-[#131f38]"
                    : "bg-red-500/20 border-red-500/30 text-red-400 hover:bg-red-500/30"
                }`}
              >
                {isMicActive ? <Mic className="w-3.5 h-3.5 text-emerald-400" /> : <MicOff className="w-3.5 h-3.5 text-red-400" />}
                <span>{isMicActive ? "Mute Mic" : "Unmute Mic"}</span>
              </button>

              <button
                type="button"
                onClick={toggleCamera}
                className={`px-3 py-1.5 rounded-lg border text-xs font-medium flex items-center gap-1.5 transition-colors ${
                  isCameraActive
                    ? "bg-[#0B1120] border-subtle text-slate-200 hover:bg-[#131f38]"
                    : "bg-red-500/20 border-red-500/30 text-red-400 hover:bg-red-500/30"
                }`}
              >
                {isCameraActive ? <Video className="w-3.5 h-3.5 text-blue-400" /> : <VideoOff className="w-3.5 h-3.5 text-red-400" />}
                <span>{isCameraActive ? "Disable Camera" : "Enable Camera"}</span>
              </button>
            </div>
          </div>

          {/* Right Column: Interview Session Configuration Form */}
          <div className="flex flex-col justify-between space-y-4">
            <div className="space-y-3.5">
              <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-300">
                <Briefcase className="w-3.5 h-3.5 text-blue-400" />
                <span>Session Configuration</span>
              </div>

              {/* Track Selector: Technical vs HR */}
              <div className="space-y-1.5">
                <label className="text-xs text-slate-300 font-medium block">
                  Interview Track
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setInterviewType("technical")}
                    className={`p-2.5 rounded-lg border text-xs text-left transition-all flex items-center gap-2 ${
                      interviewType === "technical"
                        ? "bg-[#2563EB]/20 border-[#2563EB] text-white font-semibold shadow-sm"
                        : "bg-[#0B1120] border-subtle text-slate-400 hover:text-white"
                    }`}
                  >
                    <Code2 className="w-4 h-4 text-blue-400 shrink-0" />
                    <div>
                      <div className="text-white font-medium">Technical Track</div>
                      <div className="text-[10px] text-slate-400 font-normal">Architecture & coding reasoning</div>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => setInterviewType("hr")}
                    className={`p-2.5 rounded-lg border text-xs text-left transition-all flex items-center gap-2 ${
                      interviewType === "hr"
                        ? "bg-[#2563EB]/20 border-[#2563EB] text-white font-semibold shadow-sm"
                        : "bg-[#0B1120] border-subtle text-slate-400 hover:text-white"
                    }`}
                  >
                    <Users className="w-4 h-4 text-emerald-400 shrink-0" />
                    <div>
                      <div className="text-white font-medium">HR / Behavioral</div>
                      <div className="text-[10px] text-slate-400 font-normal">Leadership, collaboration & culture</div>
                    </div>
                  </button>
                </div>
              </div>

              {/* Candidate Name Input */}
              <div className="space-y-1">
                <label htmlFor="candidate-name" className="text-xs text-slate-300 font-medium">
                  Candidate Name
                </label>
                <input
                  id="candidate-name"
                  type="text"
                  required
                  value={candidateName}
                  onChange={(e) => setCandidateName(e.target.value)}
                  placeholder="e.g. Alex Candidate"
                  className="w-full bg-[#0B1120] border border-subtle rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#2563EB] transition-colors"
                />
              </div>

              {/* Target Role Input */}
              <div className="space-y-1">
                <label htmlFor="target-role" className="text-xs text-slate-300 font-medium">
                  Target Role / Job Title
                </label>
                <input
                  id="target-role"
                  type="text"
                  required
                  value={targetRole}
                  onChange={(e) => setTargetRole(e.target.value)}
                  placeholder="e.g. Senior Backend Engineer"
                  className="w-full bg-[#0B1120] border border-subtle rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#2563EB] transition-colors"
                />
              </div>

              {/* Experience Level */}
              <div className="space-y-1">
                <label htmlFor="experience-level" className="text-xs text-slate-300 font-medium flex items-center gap-1">
                  <Award className="w-3.5 h-3.5 text-amber-400" />
                  <span>Seniority Level</span>
                </label>
                <select
                  id="experience-level"
                  value={experienceLevel}
                  onChange={(e) => setExperienceLevel(e.target.value)}
                  className="w-full bg-[#0B1120] border border-subtle rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[#2563EB] transition-colors"
                >
                  <option value="Junior">Junior (0-2 years)</option>
                  <option value="Mid-level">Mid-level (3-5 years)</option>
                  <option value="Senior">Senior (5-8 years)</option>
                  <option value="Lead">Lead / Principal (8+ years)</option>
                </select>
              </div>
            </div>

            {/* Launch CTA */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={isStarting}
                className="w-full bg-[#2563EB] hover:bg-blue-600 disabled:opacity-50 text-white font-semibold text-xs py-3 rounded-lg flex items-center justify-center gap-2 transition-all shadow-lg shadow-blue-900/30 hover:shadow-blue-600/40"
              >
                {isStarting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Initializing Interview with Alex...</span>
                  </>
                ) : (
                  <>
                    <Video className="w-4 h-4" />
                    <span>Start Mock Interview</span>
                    <ArrowRight className="w-4 h-4 ml-1" />
                  </>
                )}
              </button>

              <p className="text-[11px] text-slate-400 text-center mt-2">
                Up to 5 questions evaluated across 4 rubric dimensions.
              </p>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
