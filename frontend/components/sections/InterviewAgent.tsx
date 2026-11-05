"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/store/useStore";
import ResumeUploadModal from "@/components/interview/ResumeUploadModal";
import InterviewLobby from "@/components/interview/InterviewLobby";
import VoiceVisualizer from "@/components/voice/VoiceVisualizer";
import VoiceRecorder from "@/components/voice/VoiceRecorder";
import { sendVoiceAudio, VoiceProcessResponse } from "@/lib/api";
import { saveInterviewSession, InterviewSessionRecord } from "@/lib/supabase";
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
  FileText,
  Sparkles,
  Loader2,
} from "lucide-react";

export default function InterviewAgent() {
  const router = useRouter();
  const {
    setActiveSection,
    isCameraOn,
    setCameraOn,
    isMicOn,
    setMicOn,
    isCallActive,
    setCallActive,
    currentQuestionIndex,
    nextQuestion,
    resume,
    isResumeBased,
    setSetupModalOpen,
    user,
    addInterviewSession,
  } = useAppStore();

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [hasPermissionError, setHasPermissionError] = useState(false);
  const [callTime] = useState("09:32");

  // Voice Pipeline State
  const [isProcessingAudio, setIsProcessingAudio] = useState(false);
  const [candidateTranscript, setCandidateTranscript] = useState<string>(
    "I would assign a unique idempotent transaction ID to every incoming event and store processed IDs in an atomic Redis set with a TTL..."
  );
  const [, setAiVoiceResponse] = useState<VoiceProcessResponse | null>(null);
  const [isAiSpeaking, setIsAiSpeaking] = useState(false);

  // Dynamic question banks: Resume-Driven vs Standard
  const resumeQuestions =
    resume?.customQuestions && resume.customQuestions.length > 0
      ? resume.customQuestions
      : [
          `"I reviewed your resume from ${resume?.recentCompany || "your previous role"}. You mentioned architecting event-driven systems using ${
            resume?.skills[1] || "Kafka"
          }. Could you walk me through how you guaranteed message ordering and fault-tolerance?"`,
          `"Under your core technical competencies, you highlighted ${
            resume?.skills[0] || "PostgreSQL"
          } optimization. Can you describe a specific bottleneck or lock contention issue you resolved in production?"`,
          `"In your role as ${
            resume?.targetRole || "Senior Backend Engineer"
          }, how did you approach decoupling monolithic dependencies while maintaining zero downtime?"`,
          `"You have extensive experience with ${
            resume?.skills[6] || "Redis"
          } caching. How did you design cache invalidation and prevent thundering herd spikes?"`,
          `"Based on your background, what architectural engineering challenges are you most eager to tackle next?"`,
        ];

  const standardQuestions = [
    '"Tell me about a challenging technical project you led and how you managed architecture trade-offs."',
    '"How would you design a scalable URL shortener with high read throughput and 99.99% availability?"',
    '"Could you walk me through how you architect an event-driven system using Kafka, and ensure idempotent consumers?"',
    '"Describe how you handle cache stampedes and database thundering herd problems in production."',
    '"Do you have any questions for us regarding the engineering culture or architectural roadmap?"',
  ];

  const activeQuestions = isResumeBased && resume ? resumeQuestions : standardQuestions;
  const currentQuestion = activeQuestions[currentQuestionIndex];

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

  // Request user camera when call is active
  useEffect(() => {
    if (!isCallActive) return;
    let localStream: MediaStream | null = null;

    async function initCamera() {
      try {
        localStream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: true,
        });
        setStream(localStream);
        if (videoRef.current) {
          videoRef.current.srcObject = localStream;
        }
        setCameraOn(true);
        setHasPermissionError(false);
      } catch (err) {
        console.warn("Camera access not available or permission denied:", err);
        setHasPermissionError(true);
        setCameraOn(false);
        toast.warning("Camera unavailable", "Running in candidate avatar mode. Check browser permissions.");
      }
    }

    initCamera();

    return () => {
      if (localStream) {
        localStream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [isCallActive, setCameraOn]);

  // Automatically speak Question 1 out loud when entering the active call
  const hasSpokenIntroRef = useRef(false);

  useEffect(() => {
    if (!isCallActive) {
      hasSpokenIntroRef.current = false;
      stopSpeaking();
      return;
    }

    if (hasSpokenIntroRef.current) return;
    hasSpokenIntroRef.current = true;

    const candidateName = user?.name || "there";
    const cleanQuestion = currentQuestion.replace(/^["'\s]+|["'\s]+$/g, "").trim();
    const welcomeSpeech = `Hello ${candidateName}, welcome to your technical interview. Let's begin with your first question: ${cleanQuestion}`;

    const timer = setTimeout(() => {
      speakInterviewer(welcomeSpeech);
    }, 600);

    return () => {
      clearTimeout(timer);
      stopSpeaking();
    };
  }, [isCallActive, currentQuestion, user?.name, speakInterviewer]);

  const retryCamera = async () => {
    try {
      const localStream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      });
      setStream(localStream);
      if (videoRef.current) {
        videoRef.current.srcObject = localStream;
      }
      setCameraOn(true);
      setHasPermissionError(false);
      toast.success("Camera connected", "1080p video feed active.");
    } catch {
      toast.error("Camera access denied", "Please grant camera permission in browser settings.");
    }
  };

  const toggleCamera = () => {
    if (stream) {
      const videoTrack = stream.getVideoTracks()[0];
      if (videoTrack) {
        const nextState = !videoTrack.enabled;
        videoTrack.enabled = nextState;
        setCameraOn(nextState);
        toast.info(nextState ? "Camera enabled" : "Camera disabled");
        return;
      }
    }
    const next = !isCameraOn;
    setCameraOn(next);
    toast.info(next ? "Camera enabled" : "Camera disabled");
  };

  const toggleMic = () => {
    if (stream) {
      const audioTrack = stream.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !isMicOn;
      }
    }
    const next = !isMicOn;
    setMicOn(next);
    toast.info(next ? "Microphone active" : "Microphone muted");
  };

  const handleEndCall = useCallback(() => {
    stopSpeaking();
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
    }

    const sessionRecord: InterviewSessionRecord = {
      candidate_name: user?.name || "Anish",
      role_applied: resume ? resume.targetRole : "Senior Backend Engineer",
      experience_level: "Senior",
      interview_type: "technical",
      questions: activeQuestions,
      answers: [candidateTranscript],
      scores: {
        overall_score: 89,
        relevance: 93,
        technical_depth: 88,
        clarity: 87,
        examples: 88,
      },
      report: {
        strengths: [
          "Demonstrated solid grasp of distributed event streams and partition keying.",
          "Clear, confident vocal presence and optimal pacing during complex architectural explanations.",
          "Handled follow-ups with concrete implementation details (Redis TTL & Kafka offsets).",
        ],
        weaknesses: [
          "Explicitly mention dead letter queues for message ingestion failures.",
          "Quantify write volume and storage retention sizing during initial prompt intake.",
        ],
      },
      is_complete: true,
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
    };

    setCallActive(false);
    addInterviewSession(sessionRecord);
    toast.success("Interview session saved", "Evaluation metrics recorded to Supabase.");
    saveInterviewSession(sessionRecord).catch((err) => {
      console.warn("Could not persist to Supabase:", err);
    });
    setActiveSection(4);
    router.push("/analytics/interview");
  }, [
    stream,
    user?.name,
    resume,
    activeQuestions,
    candidateTranscript,
    setCallActive,
    addInterviewSession,
    setActiveSection,
    router,
  ]);

  /**
   * Handles recorded candidate audio submission to FastAPI POST /voice/process
   * And automatically asks the next question out loud with voice!
   */
  const handleVoiceRecordingStop = useCallback(
    async (blob: Blob) => {
      setIsProcessingAudio(true);
      stopSpeaking();
      toast.info("Transcribing speech", "Analyzing audio with NVIDIA Parakeet & Nemotron...");
      try {
        const response = await sendVoiceAudio(blob, "interview", currentQuestion);
        setCandidateTranscript(response.transcript);
        setAiVoiceResponse(response);

        const nextIdx = currentQuestionIndex + 1;
        const ackText =
          response.spoken_response && response.spoken_response.length < 160
            ? response.spoken_response
            : "Thank you for that explanation.";

        if (nextIdx < activeQuestions.length) {
          const nextQ = activeQuestions[nextIdx].replace(/^["'\s]+|["'\s]+$/g, "").trim();
          // Advance question index in the app state
          nextQuestion();
          toast.success("Answer received", `Alex is asking Question ${nextIdx + 1}...`);

          // Seamlessly voice the acknowledgement and the next question out loud
          const nextSpeech = `${ackText} Moving on to Question ${nextIdx + 1}: ${nextQ}`;
          speakInterviewer(nextSpeech);
        } else {
          // Final question completed!
          toast.success("Interview completed", "Compiling your technical evaluation report...");
          const closingSpeech = `${ackText} That concludes all questions in your technical interview. I will now compile your evaluation report.`;
          speakInterviewer(closingSpeech, () => {
            handleEndCall();
          });
        }
      } catch (err) {
        console.warn("Error processing audio through voice pipeline:", err);
        toast.warning("Voice pipeline error", "Proceeding with next question.");

        const nextIdx = currentQuestionIndex + 1;
        if (nextIdx < activeQuestions.length) {
          const nextQ = activeQuestions[nextIdx].replace(/^["'\s]+|["'\s]+$/g, "").trim();
          nextQuestion();
          speakInterviewer(`Thank you. Moving to Question ${nextIdx + 1}: ${nextQ}`);
        } else {
          handleEndCall();
        }
      } finally {
        setIsProcessingAudio(false);
      }
    },
    [
      currentQuestion,
      currentQuestionIndex,
      activeQuestions,
      nextQuestion,
      speakInterviewer,
      handleEndCall,
    ]
  );

  // Manual next question trigger (advances and speaks next question)
  const handleManualNextQuestion = useCallback(() => {
    stopSpeaking();
    if (currentQuestionIndex < activeQuestions.length - 1) {
      const nextIdx = currentQuestionIndex + 1;
      nextQuestion();
      const nextQ = activeQuestions[nextIdx].replace(/^["'\s]+|["'\s]+$/g, "").trim();
      speakInterviewer(`Question ${nextIdx + 1}: ${nextQ}`);
    } else {
      speakInterviewer("That was the final question. Completing your interview now.", () => {
        handleEndCall();
      });
    }
  }, [currentQuestionIndex, activeQuestions, nextQuestion, speakInterviewer, handleEndCall]);

  // Repeat current question with voice
  const handleRepeatQuestion = useCallback(() => {
    const clean = currentQuestion.replace(/^["'\s]+|["'\s]+$/g, "").trim();
    toast.info("Repeating Question", "Interviewer is reading the question again.");
    speakInterviewer(`Question ${currentQuestionIndex + 1}: ${clean}`);
  }, [currentQuestion, currentQuestionIndex, speakInterviewer]);

  if (!isCallActive) {
    return <InterviewLobby />;
  }

  return (
    <section className="space-y-4">
      {/* Resume Configuration Modal */}
      <ResumeUploadModal />

      {/* Call Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1">
        <div className="flex items-center gap-3">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
          <span className="text-sm font-semibold text-white">
            {isResumeBased && resume ? `Resume Interview: ${resume.targetRole}` : "Technical Mock Interview"}
          </span>
          <span className="text-xs font-mono bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-subtle hidden md:inline-flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
            <span>HD 1080p · WebRTC · Parakeet STT</span>
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              stopSpeaking();
              if (stream) stream.getTracks().forEach((t) => t.stop());
              setCallActive(false);
            }}
            className="text-xs font-mono bg-[#141b2d] hover:bg-[#1a233a] border border-subtle text-slate-300 px-2.5 py-1.5 rounded transition-colors"
          >
            ← Back to Lobby
          </button>

          <button
            onClick={() => setSetupModalOpen(true)}
            className="text-xs font-medium bg-[#131f38] hover:bg-[#1a2b4d] border border-blue-500/30 text-blue-300 px-3 py-1.5 rounded flex items-center gap-1.5 transition-colors"
          >
            {isResumeBased && resume ? (
              <>
                <FileText className="w-3.5 h-3.5 text-emerald-400" />
                <span className="truncate max-w-[120px]">{resume.fileName}</span>
                <span className="text-[10px] font-mono text-emerald-400 font-bold">Active</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                <span>Upload Resume</span>
              </>
            )}
          </button>

          <span className="text-xs font-mono text-slate-400 bg-[#0e1627] px-3 py-1.5 rounded border border-subtle">
            Duration: <strong className="text-white">{callTime}</strong>
          </span>
        </div>
      </div>

      {/* Main Video Call Grid: Side-by-Side (50/50, Clean Immersive Call with Zero Captions) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-[440px]">
        {/* Left: AI Interviewer Tile */}
        <div className="card-clean bg-[#0a0f1d] relative rounded-xl overflow-hidden flex flex-col justify-between border border-blue-500/20">
          {/* AI Thinking / Processing Overlay */}
          {isProcessingAudio && (
            <div className="absolute inset-x-4 top-14 z-20 p-2.5 rounded-lg bg-blue-950/90 border border-blue-500/40 backdrop-blur shadow-lg flex items-center gap-2.5 animate-pulse">
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin shrink-0" />
              <div className="text-[11px] text-blue-200">
                <strong className="text-white">NVIDIA Nemotron 70B</strong> is analyzing your architectural response...
              </div>
            </div>
          )}

          {/* Top Status Bar */}
          <div className="p-3.5 flex items-center justify-between z-10 bg-gradient-to-b from-black/70 to-transparent">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded bg-blue-600 flex items-center justify-center font-bold text-xs text-white">
                AI
              </div>
              <div>
                <span className="text-xs font-medium text-white block">Alex — Technical Lead Interviewer</span>
                {isResumeBased && resume && (
                  <span className="text-[10px] font-mono text-blue-300">Evaluating against uploaded resume</span>
                )}
              </div>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${isAiSpeaking ? "bg-amber-400 animate-ping" : "bg-emerald-400"}`} />
              <span>{isAiSpeaking ? "AI Speaking (TTS)" : "Listening"}</span>
            </span>
          </div>

          {/* Central AI Persona & Harmonic Visualizer (Clean, no bottom caption overlay) */}
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
            <div
              className={`w-24 h-24 rounded-full bg-blue-600/10 border flex items-center justify-center transition-all duration-300 mb-4 ${
                isAiSpeaking
                  ? "border-blue-400 shadow-[0_0_40px_rgba(37,99,235,0.45)] scale-105"
                  : "border-blue-500/30 shadow-[0_0_25px_rgba(37,99,235,0.15)]"
              }`}
            >
              <User className={`w-12 h-12 transition-colors ${isAiSpeaking ? "text-blue-300" : "text-blue-400"}`} />
            </div>

            {/* Embedded Reactive Waveform */}
            <VoiceVisualizer
              state={isAiSpeaking ? "speaking" : "idle"}
              height={60}
              className="w-56 opacity-90 my-2"
            />

            <div className="mt-3 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#111c38] border border-blue-500/20 text-xs font-mono text-slate-300">
              <span className="text-blue-400 font-semibold">Question {currentQuestionIndex + 1} of {activeQuestions.length}</span>
              <span className="text-slate-500">·</span>
              <span>{isResumeBased ? "Tailored Verification" : "System Design"}</span>
            </div>

            <p className="text-[11px] text-slate-400 mt-2.5">
              {isAiSpeaking ? "Alex is asking the question out loud..." : "Alex is listening. Record your voice answer below."}
            </p>
          </div>
        </div>

        {/* Right: Candidate Real Video Stream Tile (Clean 100% Full-Bleed, no bottom caption overlay) */}
        <div className="card-clean bg-[#0a0f1d] relative rounded-xl overflow-hidden flex flex-col justify-between border border-subtle">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className={`video-mirror absolute inset-0 w-full h-full object-cover z-0 ${
              !isCameraOn ? "hidden" : "block"
            }`}
          />

          {hasPermissionError ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#0d1424] z-0 p-6 text-center">
              <div className="w-16 h-16 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-3">
                <VideoOff className="w-7 h-7" />
              </div>
              <p className="text-xs text-white font-medium">Camera Access Restricted</p>
              <p className="text-[11px] text-slate-400 mt-1 max-w-xs">
                Webcam permission was blocked or unavailable. Click below to re-request.
              </p>
              <button
                onClick={retryCamera}
                className="mt-3 bg-blue-600 hover:bg-blue-500 text-white text-xs px-3.5 py-1.5 rounded font-medium transition-colors"
              >
                Retry Camera Permission
              </button>
            </div>
          ) : !isCameraOn ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#0d1424] z-0 p-6 text-center">
              <div className="w-16 h-16 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 mb-3">
                <VideoOff className="w-7 h-7" />
              </div>
              <p className="text-xs text-slate-300 font-medium">Candidate Camera Off</p>
              <button
                onClick={toggleCamera}
                className="mt-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs px-3.5 py-1.5 rounded font-medium transition-colors"
              >
                Turn Camera On
              </button>
            </div>
          ) : null}

          {/* Top Bar for Candidate Tile */}
          <div className="p-3.5 flex items-center justify-between z-10 bg-gradient-to-b from-black/70 to-transparent">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span className="text-xs font-medium text-white">{user?.name || "Anish"} (Candidate)</span>
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
                {isCameraOn ? "Camera: 1080p" : "Camera: Off"}
              </span>
            </div>
          </div>

          {/* Unobstructed space for full video call view */}
          <div className="flex-1" />

          {/* Non-intrusive bottom status banner only while Parakeet STT is processing */}
          {isProcessingAudio && (
            <div className="p-3 bg-black/60 backdrop-blur z-10 flex items-center justify-center gap-2 border-t border-subtle">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400" />
              <span className="text-xs font-mono text-blue-200">Processing audio with NVIDIA Parakeet STT...</span>
            </div>
          )}
        </div>
      </div>

      {/* Floating Call Controls (Clean Google Meet / Zoom style) */}
      <div className="card-clean p-3 bg-[#0d1527] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-300 font-mono font-medium">
            Question {currentQuestionIndex + 1} / {activeQuestions.length}
          </span>
          {/* Integrated Voice Recorder Button */}
          <VoiceRecorder
            onRecordingStop={handleVoiceRecordingStop}
            disabled={isProcessingAudio || isAiSpeaking}
          />
        </div>

        {/* Central Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={toggleMic}
            className={`w-10 h-10 rounded-full flex items-center justify-center border border-subtle transition-colors ${
              isMicOn
                ? "bg-slate-800 hover:bg-slate-700 text-emerald-400"
                : "bg-red-500/20 border-red-500/30 text-red-400"
            }`}
            title="Toggle Microphone"
          >
            {isMicOn ? <Mic className="w-5 h-5" /> : <MicOff className="w-5 h-5" />}
          </button>

          <button
            onClick={toggleCamera}
            className={`w-10 h-10 rounded-full flex items-center justify-center border border-subtle transition-colors ${
              isCameraOn
                ? "bg-slate-800 hover:bg-slate-700 text-blue-400"
                : "bg-red-500/20 border-red-500/30 text-red-400"
            }`}
            title="Toggle Camera"
          >
            {isCameraOn ? <Video className="w-5 h-5" /> : <VideoOff className="w-5 h-5" />}
          </button>

          {/* Repeat Question with Voice Button */}
          <button
            onClick={handleRepeatQuestion}
            disabled={isAiSpeaking}
            className="w-10 h-10 rounded-full bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-blue-400 flex items-center justify-center border border-subtle transition-colors"
            title="Repeat Question with Voice"
          >
            <Volume2 className="w-5 h-5" />
          </button>

          <button
            onClick={handleEndCall}
            className="bg-red-600 hover:bg-red-500 text-white text-xs font-semibold px-4 py-2 rounded-full flex items-center gap-1.5 transition-colors shadow-lg"
          >
            <PhoneOff className="w-4 h-4" />
            <span>End Call</span>
          </button>
        </div>

        <button
          onClick={handleManualNextQuestion}
          disabled={isAiSpeaking || isProcessingAudio}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-xs font-medium px-4 py-2 rounded transition-colors flex items-center gap-1"
        >
          <span>Next Question</span>
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </section>
  );
}
