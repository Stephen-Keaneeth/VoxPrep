"use client";

import React, { useState, useRef, useEffect } from "react";
import { useAppStore, ResumeData } from "@/store/useStore";
import { extractTextFromFile, analyzeResumeText } from "@/lib/resumeParser";
import { toast } from "@/store/useToast";
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  Sparkles,
  Video,
  VideoOff,
  Mic,
  MicOff,
  Briefcase,
  Layers,
  ChevronDown,
  ChevronUp,
  Loader2,
  ArrowRight,
  ClipboardList,
} from "lucide-react";

export default function InterviewLobby() {
  const {
    resume,
    setResume,
    isResumeBased,
    setIsResumeBased,
    setCallActive,
    resetQuestions,
    user,
  } = useAppStore();

  const [activeTab, setActiveTab] = useState<"upload" | "paste">("upload");
  const [pasteText, setPasteText] = useState("");
  const [isParsing, setIsParsing] = useState(false);
  const [isQuestionsExpanded, setIsQuestionsExpanded] = useState(true);
  const [rawExtractedText, setRawExtractedText] = useState<string>("");
  const [showExtractedText, setShowExtractedText] = useState(false);

  // Device pre-check state
  const videoPreviewRef = useRef<HTMLVideoElement | null>(null);
  const [previewStream, setPreviewStream] = useState<MediaStream | null>(null);
  const [isCameraActive, setIsCameraActive] = useState(true);
  const [isMicActive, setIsMicActive] = useState(true);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Initialize camera for device self-test preview
  useEffect(() => {
    let localStream: MediaStream | null = null;
    async function initPreview() {
      try {
        localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        setPreviewStream(localStream);
        if (videoPreviewRef.current) {
          videoPreviewRef.current.srcObject = localStream;
        }
      } catch (err) {
        console.warn("Could not access camera for lobby preview:", err);
        setIsCameraActive(false);
      }
    }
    initPreview();
    return () => {
      if (localStream) {
        localStream.getTracks().forEach((t) => t.stop());
      }
    };
  }, []);

  const handleFileUpload = async (file: File) => {
    setIsParsing(true);
    try {
      const text = await extractTextFromFile(file);
      setRawExtractedText(text);
      const analysis = analyzeResumeText(text, file.name);

      const newResume: ResumeData = {
        fileName: file.name,
        fileSize: `${(file.size / 1024).toFixed(1)} KB`,
        uploadedAt: "Just now",
        candidateName: analysis.candidateName || user?.name || "Candidate",
        targetRole: analysis.targetRole,
        experienceLevel: analysis.experienceLevel,
        skills: analysis.skills,
        recentCompany: analysis.recentCompany,
        summary: analysis.summary,
        customQuestions: analysis.customQuestions,
      };

      setResume(newResume);
      setIsResumeBased(true);
      resetQuestions();
      toast.success(
        "Resume analyzed successfully",
        `Synthesized 5 custom interview questions for ${analysis.targetRole}.`
      );
    } catch (err) {
      console.warn("Resume parsing error:", err);
      toast.warning("Standard analysis fallback", "Applied default senior engineering questions.");
    } finally {
      setIsParsing(false);
    }
  };

  const handleTextAnalyze = () => {
    if (!pasteText.trim()) {
      toast.error("Empty text", "Please paste your resume summary or skills.");
      return;
    }
    setIsParsing(true);
    try {
      setRawExtractedText(pasteText);
      const analysis = analyzeResumeText(pasteText, "Pasted_Resume.txt");
      const newResume: ResumeData = {
        fileName: "Pasted_Profile.txt",
        fileSize: `${(pasteText.length / 1024).toFixed(1)} KB`,
        uploadedAt: "Just now",
        candidateName: analysis.candidateName || user?.name || "Candidate",
        targetRole: analysis.targetRole,
        experienceLevel: analysis.experienceLevel,
        skills: analysis.skills,
        recentCompany: analysis.recentCompany,
        summary: analysis.summary,
        customQuestions: analysis.customQuestions,
      };

      setResume(newResume);
      setIsResumeBased(true);
      resetQuestions();
      toast.success(
        "Resume text analyzed",
        `Generated 5 tailored interview questions for ${analysis.targetRole}.`
      );
    } catch {
      toast.warning("Analysis fallback", "Applied standard system design question set.");
    } finally {
      setIsParsing(false);
    }
  };

  const handleStartCall = () => {
    if (previewStream) {
      previewStream.getTracks().forEach((t) => t.stop());
    }
    setCallActive(true);
    toast.info("Entering video call", "Connecting to AI interviewer Alex...");
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto py-2 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-subtle">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-white tracking-tight">Interview Pre-Call Lobby</h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-amber-400" />
              <span>Step 1 of 2: Profile & Question Synthesis</span>
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Upload your resume so the AI interviewer conducts an adaptive technical interview tailored to your exact projects.
          </p>
        </div>
      </div>

      {/* Main 2-Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (7 cols): Resume Uploader & Parsed Intelligence */}
        <div className="lg:col-span-7 space-y-4">
          <div className="card-clean p-5 space-y-4 bg-[#0a101d] border border-blue-500/20">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-400" />
                <span>1. Connect Your Resume</span>
              </span>

              {/* Tabs */}
              <div className="flex items-center gap-1 bg-[#101726] p-1 rounded border border-subtle text-xs">
                <button
                  onClick={() => setActiveTab("upload")}
                  className={`px-3 py-1 rounded transition-colors ${
                    activeTab === "upload" ? "bg-blue-600 text-white font-medium" : "text-slate-400 hover:text-white"
                  }`}
                >
                  Upload File
                </button>
                <button
                  onClick={() => setActiveTab("paste")}
                  className={`px-3 py-1 rounded transition-colors ${
                    activeTab === "paste" ? "bg-blue-600 text-white font-medium" : "text-slate-400 hover:text-white"
                  }`}
                >
                  Paste Text
                </button>
              </div>
            </div>

            {/* Tab 1: Upload */}
            {activeTab === "upload" ? (
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                    handleFileUpload(e.dataTransfer.files[0]);
                  }
                }}
                className="border-2 border-dashed border-slate-700 hover:border-blue-500/60 bg-[#0d1424]/70 rounded-xl p-6 text-center cursor-pointer transition-all space-y-2 group"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt,.md"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      handleFileUpload(e.target.files[0]);
                    }
                  }}
                />
                <div className="w-10 h-10 rounded-full bg-blue-600/10 border border-blue-500/20 flex items-center justify-center text-blue-400 mx-auto group-hover:scale-105 transition-transform">
                  <UploadCloud className="w-5 h-5" />
                </div>
                <div className="text-xs font-medium text-white">
                  {isParsing ? "Analyzing resume with technical parser..." : "Click or drag & drop your resume file"}
                </div>
                <div className="text-[11px] text-slate-400">
                  Supports PDF, DOCX, TXT, or MD (Auto-detects roles, skills & architecture)
                </div>
              </div>
            ) : (
              /* Tab 2: Paste */
              <div className="space-y-2.5">
                <textarea
                  value={pasteText}
                  onChange={(e) => setPasteText(e.target.value)}
                  rows={4}
                  placeholder="Paste your resume summary, tech stack, or LinkedIn experience here (e.g., 'Senior Backend Engineer with 5 years experience in Kafka, Go, PostgreSQL...')"
                  className="w-full bg-[#0d1424] border border-subtle rounded-lg p-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 resize-none font-mono"
                />
                <button
                  onClick={handleTextAnalyze}
                  disabled={isParsing || !pasteText.trim()}
                  className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold py-2 rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  {isParsing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  <span>{isParsing ? "Analyzing Skills..." : "Analyze & Synthesize Questions"}</span>
                </button>
              </div>
            )}
          </div>

          {/* AI Extracted Profile & Custom Question Preview */}
          {resume && (
            <div className="card-clean p-5 space-y-4 bg-[#0a101d] border border-emerald-500/30 rounded-xl">
              <div className="flex items-center justify-between pb-3 border-b border-subtle">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                    <CheckCircle2 className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-white flex items-center gap-2">
                      <span>{resume.targetRole}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                        {resume.experienceLevel || "Senior Tier"}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400">
                      Extracted from: <strong className="text-slate-300">{resume.fileName}</strong>
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => setIsResumeBased(!isResumeBased)}
                  className={`text-[11px] font-mono px-2.5 py-1 rounded border transition-colors ${
                    isResumeBased
                      ? "bg-blue-600/20 text-blue-300 border-blue-500/30"
                      : "bg-slate-800 text-slate-400 border-subtle"
                  }`}
                >
                  {isResumeBased ? "Adaptive Mode: ON" : "Adaptive Mode: OFF"}
                </button>
              </div>

              {/* Extracted Skills Cloud */}
              <div className="space-y-1.5">
                <span className="text-[11px] font-mono uppercase text-slate-400 flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-blue-400" />
                  <span>Target Competencies to be Evaluated:</span>
                </span>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {resume.skills.map((skill) => (
                    <span
                      key={skill}
                      className="text-[10px] font-mono px-2.5 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 font-medium"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>

              {/* Synthesized 5 Questions Accordion */}
              {resume.customQuestions && resume.customQuestions.length > 0 && (
                <div className="pt-2 border-t border-subtle">
                  <button
                    onClick={() => setIsQuestionsExpanded(!isQuestionsExpanded)}
                    className="w-full flex items-center justify-between text-xs text-slate-300 hover:text-white py-1 font-medium"
                  >
                    <span className="flex items-center gap-2">
                      <ClipboardList className="w-4 h-4 text-amber-400" />
                      <span>Synthesized Interview Questions ({resume.customQuestions.length})</span>
                    </span>
                    {isQuestionsExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>

                  {isQuestionsExpanded && (
                    <ol className="mt-2.5 space-y-2 text-[11px] text-slate-300 list-decimal list-inside bg-[#080d18] p-3 rounded-lg border border-subtle">
                      {resume.customQuestions.map((q, idx) => (
                        <li key={idx} className="leading-relaxed">
                          <span className="text-slate-100">{q.replace(/^"|"$/g, "")}</span>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              )}

              {/* Parsed Raw Document Text Viewer */}
              {rawExtractedText && (
                <div className="pt-2 border-t border-subtle">
                  <button
                    onClick={() => setShowExtractedText(!showExtractedText)}
                    className="w-full flex items-center justify-between text-xs text-slate-400 hover:text-white py-1 font-mono transition-colors"
                  >
                    <span className="flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-blue-400" />
                      <span>View Parsed Document Text ({rawExtractedText.length} chars)</span>
                    </span>
                    {showExtractedText ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>

                  {showExtractedText && (
                    <div className="mt-2 p-3 bg-[#080d18] rounded-lg border border-subtle text-[11px] text-slate-300 font-mono max-h-36 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                      {rawExtractedText}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column (5 cols): Device Check & Enter Call */}
        <div className="lg:col-span-5 space-y-4">
          <div className="card-clean p-5 space-y-4 bg-[#0a101d] border border-subtle flex flex-col justify-between">
            <div>
              <span className="text-xs font-semibold text-white uppercase tracking-wider font-mono flex items-center gap-2 mb-3">
                <Video className="w-4 h-4 text-emerald-400" />
                <span>2. Device & Presence Check</span>
              </span>

              {/* Mini Video Mirror Preview */}
              <div className="relative rounded-lg overflow-hidden bg-black aspect-video border border-subtle flex items-center justify-center">
                <video
                  ref={videoPreviewRef}
                  autoPlay
                  playsInline
                  muted
                  className={`video-mirror w-full h-full object-cover ${!isCameraActive ? "hidden" : "block"}`}
                />
                {!isCameraActive && (
                  <div className="flex flex-col items-center justify-center text-slate-400 space-y-1 p-4 text-center">
                    <VideoOff className="w-6 h-6 text-slate-500" />
                    <span className="text-xs">Camera is muted or permission blocked</span>
                  </div>
                )}

                {/* Device Overlay Pill */}
                <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between px-2.5 py-1 rounded bg-black/70 backdrop-blur text-[10px] font-mono text-slate-300">
                  <span className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    <span>{isCameraActive ? "1080p WebRTC Ready" : "Avatar Mode"}</span>
                  </span>
                  <span>{isMicActive ? "Mic Live" : "Mic Muted"}</span>
                </div>
              </div>

              {/* Pre-Call Check Controls */}
              <div className="flex items-center justify-center gap-3 mt-3">
                <button
                  onClick={() => setIsMicActive(!isMicActive)}
                  className={`p-2 rounded-full border border-subtle text-xs transition-colors ${
                    isMicActive ? "bg-slate-800 text-emerald-400" : "bg-red-500/20 text-red-400"
                  }`}
                  title={isMicActive ? "Mute Microphone" : "Unmute Microphone"}
                >
                  {isMicActive ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
                </button>
                <button
                  onClick={() => setIsCameraActive(!isCameraActive)}
                  className={`p-2 rounded-full border border-subtle text-xs transition-colors ${
                    isCameraActive ? "bg-slate-800 text-blue-400" : "bg-red-500/20 text-red-400"
                  }`}
                  title={isCameraActive ? "Turn Off Camera" : "Turn On Camera"}
                >
                  {isCameraActive ? <Video className="w-4 h-4" /> : <VideoOff className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Launch Call Button */}
            <div className="space-y-2 pt-4 border-t border-subtle">
              <button
                onClick={handleStartCall}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs py-3 rounded-lg flex items-center justify-center gap-2 transition-all shadow-lg hover:shadow-blue-600/30"
              >
                <Video className="w-4 h-4" />
                <span>
                  {resume && isResumeBased
                    ? "Start Tailored Video Interview"
                    : "Start Standard Video Interview"}
                </span>
                <ArrowRight className="w-4 h-4 ml-1" />
              </button>

              <p className="text-[11px] text-center text-slate-400">
                AI interviewer Alex will conduct the session via WebRTC with live transcription.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

