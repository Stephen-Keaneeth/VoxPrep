"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { useAppStore } from "@/store/useStore";
import ResumeUploadModal from "@/components/interview/ResumeUploadModal";
import VoiceVisualizer from "@/components/voice/VoiceVisualizer";
import VoicePlayer from "@/components/voice/VoicePlayer";
import VoiceRecorder from "@/components/voice/VoiceRecorder";
import { sendVoiceAudio, VoiceProcessResponse } from "@/lib/api";
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  PhoneOff,
  Subtitles,
  ChevronRight,
  ShieldCheck,
  User,
  FileText,
  Sparkles,
  Loader2,
} from "lucide-react";

export default function InterviewAgent() {
  const {
    setActiveSection,
    isCameraOn,
    setCameraOn,
    isMicOn,
    setMicOn,
    currentQuestionIndex,
    nextQuestion,
    resume,
    isResumeBased,
    setSetupModalOpen,
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
  const [aiVoiceResponse, setAiVoiceResponse] = useState<VoiceProcessResponse | null>(null);
  const [isAiSpeaking, setIsAiSpeaking] = useState(false);

  // Dynamic question banks: Resume-Driven vs Standard
  const resumeQuestions = [
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

  // Request user camera on mount
  useEffect(() => {
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
      }
    }

    initCamera();

    return () => {
      if (localStream) {
        localStream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [setCameraOn]);

  const toggleCamera = () => {
    if (stream) {
      const videoTrack = stream.getVideoTracks()[0];
      if (videoTrack) {
        const nextState = !videoTrack.enabled;
        videoTrack.enabled = nextState;
        setCameraOn(nextState);
        return;
      }
    }
    setCameraOn(!isCameraOn);
  };

  const toggleMic = () => {
    if (stream) {
      const audioTrack = stream.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !isMicOn;
      }
    }
    setMicOn(!isMicOn);
  };

  const handleEndCall = () => {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
    }
    setActiveSection(4);
  };

  /**
   * Handles recorded candidate audio submission to FastAPI POST /voice/process
   */
  const handleVoiceRecordingStop = useCallback(
    async (blob: Blob) => {
      setIsProcessingAudio(true);
      try {
        const response = await sendVoiceAudio(blob, "interview", currentQuestion);
        setCandidateTranscript(response.transcript);
        setAiVoiceResponse(response);
      } catch (err) {
        console.warn("Error processing audio through voice pipeline:", err);
      } finally {
        setIsProcessingAudio(false);
      }
    },
    [currentQuestion]
  );

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

      {/* Main Video Call Grid: Side-by-Side (50/50) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-[440px]">
        {/* Left: AI Interviewer Tile */}
        <div className="card-clean bg-[#0a0f1d] relative rounded-xl overflow-hidden flex flex-col justify-between border border-blue-500/20">
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

          {/* Central AI Persona & Harmonic Visualizer */}
          <div className="flex-1 flex flex-col items-center justify-center p-4">
            <div className="w-20 h-20 rounded-full bg-blue-600/10 border border-blue-500/30 flex items-center justify-center shadow-[0_0_30px_rgba(37,99,235,0.2)] mb-3">
              <User className="w-9 h-9 text-blue-400" />
            </div>

            {/* Embedded Reactive Waveform */}
            <VoiceVisualizer
              state={isAiSpeaking ? "speaking" : "idle"}
              height={56}
              className="w-48 opacity-80"
            />

            <div className="text-xs font-mono text-slate-400 mt-2">
              Question {currentQuestionIndex + 1} of {activeQuestions.length} ·{" "}
              {isResumeBased ? "Project & Experience Verification" : "System Design"}
            </div>
          </div>

          {/* Subtitles Overlay */}
          <div className="p-4 bg-black/80 backdrop-blur border-t border-subtle z-10 space-y-2">
            <div className="text-[10px] font-mono text-blue-400 uppercase flex items-center justify-between">
              <span>Live Question Caption:</span>
              {isResumeBased && (
                <span className="text-emerald-400 font-mono text-[10px]">Resume-Personalized</span>
              )}
            </div>
            <p className="text-xs text-slate-100 leading-relaxed font-normal">
              {currentQuestion}
            </p>

            {/* Voice Audio Playback component if response ready */}
            {aiVoiceResponse && (
              <VoicePlayer
                src={aiVoiceResponse.audio_url}
                audioBase64={aiVoiceResponse.audio_base64}
                textFallback={aiVoiceResponse.ai_response}
                autoPlay={true}
                onPlaybackStart={() => setIsAiSpeaking(true)}
                onPlaybackEnd={() => setIsAiSpeaking(false)}
                label="Interviewer Voice Follow-Up"
                className="mt-2"
              />
            )}
          </div>
        </div>

        {/* Right: Candidate Real Video Stream Tile */}
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

          {(!isCameraOn || hasPermissionError) && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#0d1424] z-0 p-6 text-center">
              <div className="w-20 h-20 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 mb-3">
                <VideoOff className="w-8 h-8" />
              </div>
              <p className="text-xs text-slate-300 font-medium">Candidate Camera Off</p>
              <button
                onClick={toggleCamera}
                className="mt-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs px-3.5 py-1.5 rounded font-medium transition-colors"
              >
                Turn Camera On
              </button>
            </div>
          )}

          <div className="p-3.5 flex items-center justify-between z-10 bg-gradient-to-b from-black/70 to-transparent">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span className="text-xs font-medium text-white">Anish (Candidate)</span>
            </div>
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                isCameraOn
                  ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                  : "bg-slate-800 text-slate-400 border-subtle"
              }`}
            >
              Camera: {isCameraOn ? "Active (1080p)" : "Muted"}
            </span>
          </div>

          {/* Candidate Waveform & Live Subtitle */}
          <div className="p-4 bg-black/80 backdrop-blur border-t border-subtle z-10 space-y-2">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase">
              <span className="text-emerald-400 flex items-center gap-1.5">
                {isProcessingAudio ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin text-blue-400" />
                    <span>Processing with Parakeet STT...</span>
                  </>
                ) : (
                  <span>Your Voice (Parakeet STT):</span>
                )}
              </span>
              <span className={isMicOn ? "text-emerald-400" : "text-red-400"}>
                {isMicOn ? "Mic Active" : "Mic Muted"}
              </span>
            </div>

            <p className="text-xs text-slate-200 leading-relaxed font-normal">
              &quot;{candidateTranscript}&quot;
            </p>
          </div>
        </div>
      </div>

      {/* Floating Call Controls (Google Meet / Zoom style) */}
      <div className="card-clean p-3 bg-[#0d1527] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400 font-mono">
            Question {currentQuestionIndex + 1} / {activeQuestions.length}
          </span>
          {/* Integrated Voice Recorder Button */}
          <VoiceRecorder
            onRecordingStop={handleVoiceRecordingStop}
            disabled={isProcessingAudio}
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

          <button
            className="w-10 h-10 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center justify-center border border-subtle"
            title="Captions CC"
          >
            <Subtitles className="w-5 h-5" />
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
          onClick={nextQuestion}
          className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium px-4 py-2 rounded transition-colors flex items-center gap-1"
        >
          <span>Next Question</span>
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </section>
  );
}
