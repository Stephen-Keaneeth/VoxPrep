"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useStore } from "@/store/useStore";
import InterviewLobby from "@/components/interview/InterviewLobby";
import VoiceVisualizer from "@/components/voice/VoiceVisualizer";
import VoiceRecorder from "@/components/voice/VoiceRecorder";
import {
  sendVoiceAudio,
  startInterviewSession,
  submitInterviewAnswer,
  endInterviewSession,
  InterviewStartRequest,
  InterviewReport,
} from "@/lib/api";
import { speakText, stopSpeaking } from "@/lib/voice";
import { toast } from "@/store/useToast";
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  PhoneOff,
  Volume2,
  ChevronRight,
  ShieldCheck,
  User,
  Loader2,
  CheckCircle2,
  MessageSquare,
  Sparkles,
  Send,
  HelpCircle,
} from "lucide-react";

export default function InterviewAgent() {
  const router = useRouter();
  const {
    user,
    interviewSessionId,
    setInterviewSessionId,
    setInterviewReport,
    setLatestEvaluation,
    isCallActive,
    setCallActive,
    setActiveSection,
  } = useStore();

  // WebRTC Stream & Video references
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [isCameraOn, setIsCameraOn] = useState(true);
  const [isMicOn, setIsMicOn] = useState(true);
  const [hasCameraError, setHasCameraError] = useState(false);

  // Active Session State
  const [activeSessionId, setActiveSessionId] = useState<string | null>(interviewSessionId);
  const [sessionParams, setSessionParams] = useState<InterviewStartRequest | null>(null);
  const [isStartingSession, setIsStartingSession] = useState(false);
  const [isEndingSession, setIsEndingSession] = useState(false);

  // Turn-Taking Dialog State
  const [currentPrompt, setCurrentPrompt] = useState<string>("");
  const [candidateTranscript, setCandidateTranscript] = useState<string>("");
  const [questionIndex, setQuestionIndex] = useState(0);
  const [totalQuestions, setTotalQuestions] = useState(5);
  const [followUpStatus, setFollowUpStatus] = useState<"initial" | "follow_up" | "next">("initial");
  const [isInterviewComplete, setIsInterviewComplete] = useState(false);

  // Voice Pipeline & Playback State
  const [isProcessingAudio, setIsProcessingAudio] = useState(false);
  const [isAiSpeaking, setIsAiSpeaking] = useState(false);

  // Direct Text Fallback State
  const [showTextFallback, setShowTextFallback] = useState(false);
  const [textAnswerInput, setTextAnswerInput] = useState("");
  const [isSubmittingText, setIsSubmittingText] = useState(false);

  // Call Duration Timer
  const [secondsElapsed, setSecondsElapsed] = useState(0);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Timer formatter: MM:SS
  const formattedCallTime = React.useMemo(() => {
    const mins = Math.floor(secondsElapsed / 60);
    const secs = secondsElapsed % 60;
    return `${mins < 10 ? "0" : ""}${mins}:${secs < 10 ? "0" : ""}${secs}`;
  }, [secondsElapsed]);

  // Dedicated helper to voice-speak interviewer statements with natural pacing
  const speakInterviewer = useCallback(
    (textToSpeak: string, onDone?: () => void) => {
      if (!textToSpeak) {
        onDone?.();
        return;
      }
      setIsAiSpeaking(true);
      stopSpeaking();

      // Clean text to avoid speech synthesis reading markdown or quote marks
      const clean = textToSpeak
        .replace(/^["'\s]+|["'\s]+$/g, "")
        .replace(/\*\*/g, "")
        .trim();

      speakText(clean, {
        rate: 0.95,
        onEnd: () => {
          setIsAiSpeaking(false);
          onDone?.();
        },
        onError: () => {
          setIsAiSpeaking(false);
          onDone?.();
        },
      });
    },
    []
  );

  // WebRTC Candidate Preview Stream Handling
  useEffect(() => {
    if (!isCallActive) {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        setStream(null);
      }
      return;
    }

    let localStream: MediaStream | null = null;
    let isCancelled = false;

    async function initCamera() {
      try {
        localStream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
          audio: { echoCancellation: true, noiseSuppression: true },
        });

        if (isCancelled) {
          localStream.getTracks().forEach((track) => track.stop());
          return;
        }

        streamRef.current = localStream;
        setStream(localStream);
        if (videoRef.current) {
          videoRef.current.srcObject = localStream;
        }
        setIsCameraOn(true);
        setHasCameraError(false);
      } catch (err) {
        console.warn("Candidate camera access blocked or unavailable:", err);
        if (!isCancelled) {
          setHasCameraError(true);
          setIsCameraOn(false);
          toast.warning("Camera unavailable", "Running in candidate avatar mode. Audio input is active.");
        }
      }
    }

    initCamera();

    // Start Call Duration Timer
    setSecondsElapsed(0);
    timerIntervalRef.current = setInterval(() => {
      setSecondsElapsed((prev) => prev + 1);
    }, 1000);

    return () => {
      isCancelled = true;
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
      if (localStream) {
        localStream.getTracks().forEach((track) => track.stop());
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      stopSpeaking();
    };
  }, [isCallActive]);

  // Toggle Camera Track
  const toggleCamera = () => {
    if (streamRef.current) {
      const videoTrack = streamRef.current.getVideoTracks()[0];
      if (videoTrack) {
        const nextState = !videoTrack.enabled;
        videoTrack.enabled = nextState;
        setIsCameraOn(nextState);
        toast.info(nextState ? "Camera enabled" : "Camera disabled");
        return;
      }
    }
    const next = !isCameraOn;
    setIsCameraOn(next);
    toast.info(next ? "Camera enabled" : "Camera disabled");
  };

  // Toggle Microphone Track
  const toggleMic = () => {
    if (streamRef.current) {
      const audioTrack = streamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        const nextState = !audioTrack.enabled;
        audioTrack.enabled = nextState;
        setIsMicOn(nextState);
        toast.info(nextState ? "Microphone active" : "Microphone muted");
        return;
      }
    }
    const next = !isMicOn;
    setIsMicOn(next);
    toast.info(next ? "Microphone active" : "Microphone muted");
  };

  // Retry camera access if permission denied initially
  const retryCamera = async () => {
    try {
      const localStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
        audio: true,
      });
      streamRef.current = localStream;
      setStream(localStream);
      if (videoRef.current) {
        videoRef.current.srcObject = localStream;
      }
      setIsCameraOn(true);
      setHasCameraError(false);
      toast.success("Camera connected", "Candidate video feed active.");
    } catch {
      toast.error("Camera access denied", "Please enable camera permissions in your browser.");
    }
  };

  // 1-Click / Configured Interview Start
  const handleStartInterview = async (params: InterviewStartRequest) => {
    setIsStartingSession(true);
    setSessionParams(params);

    try {
      const startResp = await startInterviewSession({
        candidate_name: params.candidate_name,
        role: params.role,
        experience_level: params.experience_level,
        interview_type: params.interview_type,
        user_id: params.user_id || user?.id || null,
      });

      if (startResp?.session_id) {
        setActiveSessionId(startResp.session_id);
        setInterviewSessionId(startResp.session_id);
      }

      const opening = startResp?.opening_message || "Welcome to your interview. Let's begin.";
      setCurrentPrompt(opening);
      setQuestionIndex(0);
      setTotalQuestions(5);
      setFollowUpStatus("initial");
      setIsInterviewComplete(false);
      setCallActive(true);

      // Voice the opening greeting after a brief pause
      setTimeout(() => {
        speakInterviewer(opening);
      }, 400);

      toast.success("Interview started", `Interviewer Alex is ready (${params.interview_type.toUpperCase()} track).`);
    } catch (err) {
      console.error("Failed to start interview session:", err);
      toast.error("Failed to start session", "Could not connect to FastAPI backend. Check backend status.");
    } finally {
      setIsStartingSession(false);
    }
  };

  // End Interview Session Trigger
  const handleEndInterview = useCallback(async () => {
    stopSpeaking();
    setIsEndingSession(true);

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setStream(null);
    }

    const currentSid = activeSessionId || interviewSessionId;
    let finalReport: InterviewReport | null = null;

    if (currentSid) {
      try {
        const endResp = await endInterviewSession(currentSid);
        if (endResp?.report) {
          finalReport = endResp.report;
          setInterviewReport(endResp.report);

          // Save backward-compatible session record
          const sessionRecord = {
            id: currentSid,
            candidate_name: sessionParams?.candidate_name || user?.name || "Candidate",
            role_applied: sessionParams?.role || "Software Engineer",
            experience_level: sessionParams?.experience_level || "Senior",
            interview_type: sessionParams?.interview_type || "technical",
            questions: [currentPrompt],
            answers: [candidateTranscript],
            scores: {
              overall_score: endResp.report.overall_score,
              relevance: endResp.report.dimension_scores.relevance,
              clarity: endResp.report.dimension_scores.clarity,
              depth: endResp.report.dimension_scores.depth,
              technical_depth: endResp.report.dimension_scores.depth,
              examples: endResp.report.dimension_scores.examples,
            },
            report: endResp.report,
            is_complete: true,
            created_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
          };
          setLatestEvaluation(sessionRecord as any);
        }
      } catch (err) {
        console.warn("Could not conclude interview session cleanly on backend:", err);
      }
    }

    setCallActive(false);
    setIsEndingSession(false);
    setActiveSection(4);
    toast.success("Interview concluded", "Redirecting to your comprehensive evaluation report...");
    router.push("/analytics/interview");
  }, [
    activeSessionId,
    interviewSessionId,
    sessionParams,
    user?.name,
    currentPrompt,
    candidateTranscript,
    setCallActive,
    setInterviewReport,
    setLatestEvaluation,
    setActiveSection,
    router,
  ]);

  // Core Turn-Taking progression logic
  const processCandidateAnswer = useCallback(
    async (answerText: string) => {
      const cleanAnswer = answerText.trim();
      if (!cleanAnswer) {
        toast.warning("Empty answer", "Please provide a verbal or typed response.");
        return;
      }

      setCandidateTranscript(cleanAnswer);
      const currentSid = activeSessionId || interviewSessionId;

      if (!currentSid) {
        toast.error("Session error", "No active interview session found.");
        return;
      }

      setIsProcessingAudio(true);
      stopSpeaking();
      toast.info("Analyzing answer", "Evaluating rubric across relevance, clarity, depth, and examples...");

      try {
        const response = await submitInterviewAnswer(currentSid, cleanAnswer);

        if (response) {
          setCurrentPrompt(response.spoken_response);
          setQuestionIndex(response.question_index ?? response.current_question_index ?? 0);
          setTotalQuestions(response.total_questions || 5);
          setFollowUpStatus(response.follow_up_or_next);

          if (response.is_complete) {
            setIsInterviewComplete(true);
            toast.success("Interview completed", "All questions completed! Generating final report...");
            speakInterviewer(response.spoken_response, () => {
              handleEndInterview();
            });
          } else {
            toast.success(
              response.follow_up_or_next === "follow_up" ? "Follow-up question" : "Next question",
              `Alex is asking Question ${response.question_index + 1}...`
            );
            speakInterviewer(response.spoken_response);
          }
        }
      } catch (err) {
        console.error("Error submitting interview answer to backend:", err);
        toast.error("Answer submission failed", "Could not submit answer to backend. Please retry.");
      } finally {
        setIsProcessingAudio(false);
        setTextAnswerInput("");
      }
    },
    [activeSessionId, interviewSessionId, speakInterviewer, handleEndInterview]
  );

  // Handle Audio Blob from MediaRecorder -> POST /voice/process -> POST /interview/respond
  const handleVoiceRecordingStop = useCallback(
    async (blob: Blob) => {
      setIsProcessingAudio(true);
      stopSpeaking();
      toast.info("Transcribing speech", "Analyzing audio with NVIDIA Parakeet STT...");

      try {
        const currentSid = activeSessionId || interviewSessionId;
        const voiceResp = await sendVoiceAudio(
          blob,
          "interview",
          currentPrompt,
          currentSid || undefined
        );

        const transcript = voiceResp.transcript?.trim();
        if (transcript) {
          await processCandidateAnswer(transcript);
        } else {
          toast.warning("Could not transcribe", "No speech detected. Please speak clearly or use text input.");
        }
      } catch (err) {
        console.error("Voice processing error:", err);
        toast.error("Voice pipeline error", "Could not process audio. You can use the text fallback below.");
      } finally {
        setIsProcessingAudio(false);
      }
    },
    [activeSessionId, interviewSessionId, currentPrompt, processCandidateAnswer]
  );

  // Handle Direct Text Input submission fallback
  const handleTextAnswerSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!textAnswerInput.trim() || isSubmittingText) return;

    setIsSubmittingText(true);
    try {
      await processCandidateAnswer(textAnswerInput);
    } finally {
      setIsSubmittingText(false);
    }
  };

  // Re-read current question with voice
  const handleRepeatQuestion = useCallback(() => {
    if (!currentPrompt) return;
    toast.info("Repeating Question", "Interviewer Alex is reading the question again.");
    speakInterviewer(currentPrompt);
  }, [currentPrompt, speakInterviewer]);

  // If call is not active, render Lobby
  if (!isCallActive) {
    return (
      <InterviewLobby
        onStartInterview={handleStartInterview}
        isStarting={isStartingSession}
      />
    );
  }

  return (
    <section className="space-y-4 max-w-5xl mx-auto">
      {/* Call Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1">
        <div className="flex items-center gap-3">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-sm font-semibold text-white">
            {sessionParams?.interview_type === "hr"
              ? `HR Mock Interview: ${sessionParams?.role || "Role"}`
              : `Technical Mock Interview: ${sessionParams?.role || "Role"}`}
          </span>
          <span className="text-xs font-mono bg-[#0B1120] text-slate-300 px-2.5 py-0.5 rounded border border-subtle hidden md:inline-flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
            <span>WebRTC Preview · Parakeet STT · Nemotron 70B</span>
          </span>
        </div>

        <div className="flex items-center gap-2">
          {followUpStatus === "follow_up" && (
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-1">
              <Sparkles className="w-3 h-3" />
              <span>Follow-Up Probe</span>
            </span>
          )}

          <span className="text-xs font-mono text-slate-400 bg-[#0B1120] px-3 py-1.5 rounded border border-subtle">
            Duration: <strong className="text-white">{formattedCallTime}</strong>
          </span>

          <button
            onClick={handleEndInterview}
            disabled={isEndingSession}
            className="bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white text-xs font-semibold px-3 py-1.5 rounded flex items-center gap-1.5 transition-colors shadow"
          >
            {isEndingSession ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <PhoneOff className="w-3.5 h-3.5" />
            )}
            <span>End Interview</span>
          </button>
        </div>
      </div>

      {/* Main Video Call Grid: Side-by-Side (50/50, Clean Immersive Call with Zero Captions) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-[440px]">
        {/* Left Tile: AI Lead Interviewer (Alex) */}
        <div className="bg-[#111A2E] relative rounded-xl overflow-hidden flex flex-col justify-between border border-blue-500/20 shadow-lg">
          {/* AI Processing Overlay */}
          {isProcessingAudio && (
            <div className="absolute inset-x-4 top-14 z-20 p-2.5 rounded-lg bg-[#0B1120]/95 border border-blue-500/40 backdrop-blur shadow-xl flex items-center gap-2.5 animate-pulse">
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin shrink-0" />
              <div className="text-[11px] text-blue-200">
                <strong className="text-white">NVIDIA Nemotron 70B</strong> is scoring rubric dimensions & formulating response...
              </div>
            </div>
          )}

          {/* Top Status Bar for Alex */}
          <div className="p-3.5 flex items-center justify-between z-10 bg-gradient-to-b from-black/80 to-transparent">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded bg-[#2563EB] flex items-center justify-center font-bold text-xs text-white shadow">
                AI
              </div>
              <div>
                <span className="text-xs font-medium text-white block">
                  Alex — {sessionParams?.interview_type === "hr" ? "HR Talent Lead" : "Technical Lead Interviewer"}
                </span>
                <span className="text-[10px] font-mono text-blue-300">
                  {sessionParams?.role} ({sessionParams?.experience_level})
                </span>
              </div>
            </div>

            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded border flex items-center gap-1.5 ${
                isAiSpeaking
                  ? "bg-amber-500/20 text-amber-300 border-amber-500/30"
                  : "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isAiSpeaking ? "bg-amber-400 animate-ping" : "bg-emerald-400"
                }`}
              />
              <span>{isAiSpeaking ? "Alex Speaking (TTS)" : "Listening"}</span>
            </span>
          </div>

          {/* Center AI Persona & Waveform */}
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
            <div
              className={`w-24 h-24 rounded-full bg-blue-600/10 border flex items-center justify-center transition-all duration-300 mb-3 ${
                isAiSpeaking
                  ? "border-blue-400 shadow-[0_0_40px_rgba(37,99,235,0.45)] scale-105"
                  : "border-blue-500/30 shadow-[0_0_20px_rgba(37,99,235,0.15)]"
              }`}
            >
              <User
                className={`w-12 h-12 transition-colors ${
                  isAiSpeaking ? "text-blue-300" : "text-blue-400"
                }`}
              />
            </div>

            {/* Embedded Harmonic Waveform */}
            <VoiceVisualizer
              state={isAiSpeaking ? "speaking" : "idle"}
              height={56}
              className="w-56 opacity-90 my-1"
            />

            <div className="mt-3 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#0B1120] border border-blue-500/20 text-xs font-mono text-slate-300">
              <span className="text-blue-400 font-semibold">
                Question {questionIndex + 1} of {totalQuestions}
              </span>
              <span className="text-slate-500">·</span>
              <span className="capitalize">{followUpStatus === "follow_up" ? "Deep Dive" : "Core Rubric"}</span>
            </div>

            <p className="text-[11px] text-slate-400 mt-2 max-w-sm">
              {isAiSpeaking
                ? "Alex is speaking the prompt out loud..."
                : isInterviewComplete
                ? "Interview complete! Compiling final evaluation report..."
                : "Alex is listening. Click Record Voice Answer or type your response below."}
            </p>
          </div>
        </div>

        {/* Right Tile: Candidate WebRTC Live Preview Stream */}
        <div className="bg-[#111A2E] relative rounded-xl overflow-hidden flex flex-col justify-between border border-subtle shadow-lg">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className={`video-mirror absolute inset-0 w-full h-full object-cover z-0 ${
              !isCameraOn ? "hidden" : "block"
            }`}
          />

          {hasCameraError ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#0B1120] z-0 p-6 text-center">
              <div className="w-16 h-16 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-3">
                <VideoOff className="w-7 h-7" />
              </div>
              <p className="text-xs text-white font-medium">Camera Access Restricted</p>
              <p className="text-[11px] text-slate-400 mt-1 max-w-xs">
                Microphone audio will continue functioning. You can click below to retry camera permission.
              </p>
              <button
                type="button"
                onClick={retryCamera}
                className="mt-3 bg-[#2563EB] hover:bg-blue-600 text-white text-xs px-3.5 py-1.5 rounded font-medium transition-colors"
              >
                Retry Camera
              </button>
            </div>
          ) : !isCameraOn ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#0B1120] z-0 p-6 text-center">
              <div className="w-16 h-16 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 mb-3">
                <VideoOff className="w-7 h-7" />
              </div>
              <p className="text-xs text-slate-300 font-medium">Candidate Camera Off</p>
              <button
                type="button"
                onClick={toggleCamera}
                className="mt-2.5 bg-[#2563EB] hover:bg-blue-600 text-white text-xs px-3.5 py-1.5 rounded font-medium transition-colors"
              >
                Turn Camera On
              </button>
            </div>
          ) : null}

          {/* Top Bar for Candidate Tile */}
          <div className="p-3.5 flex items-center justify-between z-10 bg-gradient-to-b from-black/80 to-transparent">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              <span className="text-xs font-medium text-white">
                {sessionParams?.candidate_name || user?.name || "Candidate"} (You)
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                  isMicOn
                    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                    : "bg-red-500/20 text-red-400 border-red-500/30"
                }`}
              >
                {isMicOn ? "Mic Active" : "Mic Muted"}
              </span>
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                  isCameraOn
                    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                    : "bg-slate-800 text-slate-400 border-subtle"
                }`}
              >
                {isCameraOn ? "Camera: 720p" : "Camera: Off"}
              </span>
            </div>
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Bottom Audio Pipeline Status Pill */}
          {isProcessingAudio && (
            <div className="p-2.5 bg-black/75 backdrop-blur z-10 flex items-center justify-center gap-2 border-t border-subtle">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400" />
              <span className="text-xs font-mono text-blue-200">
                Processing audio via NVIDIA Parakeet STT...
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Active Question Prompt Display Card (Crisp & Readable) */}
      <div className="card-clean p-4 bg-[#111A2E] border-blue-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex-1">
          <div className="text-[10px] font-mono text-blue-400 uppercase tracking-wider mb-1 flex items-center gap-1.5">
            <HelpCircle className="w-3.5 h-3.5 text-blue-400" />
            <span>
              Current Interview Question (Question {questionIndex + 1} of {totalQuestions})
            </span>
          </div>
          <p className="text-sm font-medium text-white leading-relaxed">
            &quot;{currentPrompt}&quot;
          </p>
        </div>

        <button
          type="button"
          onClick={handleRepeatQuestion}
          disabled={isAiSpeaking}
          className="text-xs font-medium bg-[#0B1120] hover:bg-[#131f38] disabled:opacity-40 text-blue-300 border border-subtle px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors shrink-0"
        >
          <Volume2 className="w-3.5 h-3.5" />
          <span>Repeat Question</span>
        </button>
      </div>

      {/* Floating Call & Answer Controls */}
      <div className="card-clean p-3.5 bg-[#111A2E] flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Left: Integrated Voice Recording Trigger */}
        <div className="flex items-center gap-3 w-full md:w-auto">
          <VoiceRecorder
            onRecordingStop={handleVoiceRecordingStop}
            disabled={isProcessingAudio || isAiSpeaking || isInterviewComplete}
          />

          <button
            type="button"
            onClick={() => setShowTextFallback(!showTextFallback)}
            className="text-xs font-mono text-slate-400 hover:text-white px-2.5 py-1.5 rounded border border-subtle bg-[#0B1120] flex items-center gap-1.5 transition-colors"
          >
            <MessageSquare className="w-3.5 h-3.5 text-blue-400" />
            <span>{showTextFallback ? "Hide Text Fallback" : "Type Answer"}</span>
          </button>
        </div>

        {/* Center: Device Controls (Mute Mic, Camera Toggle) */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={toggleMic}
            className={`w-10 h-10 rounded-full flex items-center justify-center border border-subtle transition-colors ${
              isMicOn
                ? "bg-[#0B1120] hover:bg-[#131f38] text-emerald-400"
                : "bg-red-500/20 border-red-500/30 text-red-400"
            }`}
            title="Toggle Microphone"
          >
            {isMicOn ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
          </button>

          <button
            type="button"
            onClick={toggleCamera}
            className={`w-10 h-10 rounded-full flex items-center justify-center border border-subtle transition-colors ${
              isCameraOn
                ? "bg-[#0B1120] hover:bg-[#131f38] text-blue-400"
                : "bg-red-500/20 border-red-500/30 text-red-400"
            }`}
            title="Toggle Camera"
          >
            {isCameraOn ? <Video className="w-4 h-4" /> : <VideoOff className="w-4 h-4" />}
          </button>

          <button
            type="button"
            onClick={handleEndInterview}
            disabled={isEndingSession}
            className="bg-red-600 hover:bg-red-500 text-white text-xs font-semibold px-4 py-2 rounded-full flex items-center gap-1.5 transition-colors shadow-lg"
          >
            {isEndingSession ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <PhoneOff className="w-4 h-4" />
            )}
            <span>End Interview</span>
          </button>
        </div>

        {/* Right: Progression Indicator */}
        <div className="text-xs font-mono text-slate-400 flex items-center gap-2">
          <span>Question {questionIndex + 1} / {totalQuestions}</span>
          {isInterviewComplete && (
            <span className="text-emerald-400 font-semibold flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Complete</span>
            </span>
          )}
        </div>
      </div>

      {/* Direct Text Fallback Drawer */}
      {showTextFallback && (
        <form
          onSubmit={handleTextAnswerSubmit}
          className="card-clean p-4 bg-[#0B1120] border-blue-500/30 space-y-3 animate-in fade-in duration-200"
        >
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-white flex items-center gap-1.5">
              <MessageSquare className="w-3.5 h-3.5 text-blue-400" />
              <span>Direct Text Answer Fallback</span>
            </span>
            <span className="text-[10px] font-mono text-slate-400">
              Evaluated against identical 4-dimension rubric
            </span>
          </div>

          <textarea
            rows={3}
            value={textAnswerInput}
            onChange={(e) => setTextAnswerInput(e.target.value)}
            disabled={isProcessingAudio || isSubmittingText || isInterviewComplete}
            placeholder="Type your response here if your microphone is unavailable or if you prefer typed input..."
            className="w-full bg-[#111A2E] border border-subtle rounded-lg p-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#2563EB] transition-colors resize-none"
          />

          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-400">
              {textAnswerInput.trim().split(/\s+/).filter(Boolean).length} words
            </span>

            <button
              type="submit"
              disabled={!textAnswerInput.trim() || isSubmittingText || isProcessingAudio || isInterviewComplete}
              className="bg-[#2563EB] hover:bg-blue-600 disabled:opacity-40 text-white text-xs font-medium px-4 py-2 rounded-lg flex items-center gap-1.5 transition-colors shadow"
            >
              {isSubmittingText ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Submitting Answer...</span>
                </>
              ) : (
                <>
                  <Send className="w-3.5 h-3.5" />
                  <span>Submit Answer</span>
                </>
              )}
            </button>
          </div>
        </form>
      )}

      {/* Candidate Transcript Display */}
      {candidateTranscript && (
        <div className="card-clean p-3.5 bg-[#0B1120] border-subtle text-xs flex items-start gap-2.5">
          <div className="w-5 h-5 rounded bg-slate-800 flex items-center justify-center text-[10px] font-bold text-slate-300 shrink-0 mt-0.5">
            You
          </div>
          <div className="space-y-0.5 flex-1">
            <div className="text-[10px] font-mono text-slate-400">Last Submitted Answer:</div>
            <p className="text-slate-200 leading-relaxed">&quot;{candidateTranscript}&quot;</p>
          </div>
        </div>
      )}
    </section>
  );
}
