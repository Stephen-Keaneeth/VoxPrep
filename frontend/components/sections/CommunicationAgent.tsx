"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useStore } from "@/store/useStore";
import VoiceVisualizer from "@/components/voice/VoiceVisualizer";
import VoicePlayer from "@/components/voice/VoicePlayer";
import VoiceRecorder from "@/components/voice/VoiceRecorder";
import {
  sendVoiceAudio,
  startCoachSession,
  submitCoachResponse,
  endCoachSession,
  VoiceProcessResponse,
  CoachCorrection,
} from "@/lib/api";
import { calculateWPM, detectFillerWords, speakText, stopSpeaking } from "@/lib/voice";
import { toast } from "@/store/useToast";
import {
  ArrowRight,
  Lightbulb,
  Activity,
  Loader2,
  Sparkles,
  CheckCircle2,
  MessageSquare,
  Send,
  Volume2,
  AlertTriangle,
  RotateCcw,
  BookOpen,
} from "lucide-react";

type CoachMode = "conversation" | "answer_training" | "english_improvement";

const MODE_CONFIG: Record<
  CoachMode,
  { label: string; badge: string; description: string; focus: string }
> = {
  conversation: {
    label: "Everyday Fluency",
    badge: "Conversation",
    description: "Practice spontaneous conversational momentum, casual flow, and relaxed pacing.",
    focus: "Momentum & natural dialogue",
  },
  answer_training: {
    label: "Answer Structuring (STAR)",
    badge: "STAR Method",
    description: "Structure professional responses with Situation, Task, Action, and Result with quantifiable impact.",
    focus: "STAR framework & metric conciseness",
  },
  english_improvement: {
    label: "English & Grammar",
    badge: "Grammar & Vocab",
    description: "Refine tense consistency, syntax, professional vocabulary, and eliminate filler words.",
    focus: "Syntax, vocabulary & gentle corrections",
  },
};

export default function CommunicationAgent() {
  const router = useRouter();
  const {
    user,
    guestUserId,
    coachSessionId,
    setCoachSessionId,
    setCoachReport,
    addCoachSession,
    setActiveSection,
  } = useStore();

  // Mode Selection: exact 3 backend modes
  const [selectedMode, setSelectedMode] = useState<CoachMode>("answer_training");

  // Backend Session State
  const [activeSessionId, setActiveSessionId] = useState<string | null>(coachSessionId);
  const [isInitializing, setIsInitializing] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isEndingSession, setIsEndingSession] = useState(false);

  // Turn-Taking Dialog State
  const [promptText, setPromptText] = useState<string>(
    "Loading your personalized communication exercise..."
  );
  const [spokenTranscript, setSpokenTranscript] = useState<string>("");
  const [coachMessage, setCoachMessage] = useState<string>("");
  const [coachVoiceResponse, setCoachVoiceResponse] = useState<VoiceProcessResponse | null>(null);
  const [activeCorrection, setActiveCorrection] = useState<CoachCorrection | null>(null);
  const [exchangesCount, setExchangesCount] = useState<number>(0);

  // Vocal Pacing & Filler Word Metrics
  const [liveStream, setLiveStream] = useState<MediaStream | null>(null);
  const [calculatedWpm, setCalculatedWpm] = useState<number>(135);
  const [detectedFillers, setDetectedFillers] = useState<{ word: string; count: number }[]>([]);
  const [isCoachSpeaking, setIsCoachSpeaking] = useState(false);

  // Direct Text Fallback
  const [showTextFallback, setShowTextFallback] = useState(false);
  const [textAnswerInput, setTextAnswerInput] = useState("");
  const [isSubmittingText, setIsSubmittingText] = useState(false);

  // Web Speech Recognition for Live Metrics Tracking
  const recognitionRef = useRef<any>(null);
  const recordingStartTimeRef = useRef<number>(0);

  // Helper to voice-speak coach messages
  const speakCoach = useCallback(
    (textToSpeak: string, onDone?: () => void) => {
      if (!textToSpeak) {
        onDone?.();
        return;
      }
      setIsCoachSpeaking(true);
      stopSpeaking();

      const clean = textToSpeak
        .replace(/^["'\s]+|["'\s]+$/g, "")
        .replace(/\*\*/g, "")
        .trim();

      speakText(clean, {
        rate: 0.95,
        onEnd: () => {
          setIsCoachSpeaking(false);
          onDone?.();
        },
        onError: () => {
          setIsCoachSpeaking(false);
          onDone?.();
        },
      });
    },
    []
  );

  // Start or restart a coach session for the given mode
  const initSessionForMode = useCallback(
    async (mode: CoachMode) => {
      stopSpeaking();
      setIsInitializing(true);
      setActiveCorrection(null);
      setSpokenTranscript("");
      setCoachMessage("");
      setCoachVoiceResponse(null);
      setDetectedFillers([]);

      const targetUserId = user?.id || guestUserId;

      try {
        const startData = await startCoachSession(targetUserId, mode);
        if (startData?.session_id) {
          setActiveSessionId(startData.session_id);
          setCoachSessionId(startData.session_id);
          if (startData.opening_message) {
            setPromptText(startData.opening_message);
            // Speak opening message out loud
            setTimeout(() => {
              speakCoach(startData.opening_message);
            }, 300);
          }
          toast.success(
            "Coach ready",
            `Started ${MODE_CONFIG[mode].label} practice session.`
          );
        }
      } catch (err) {
        console.error("Failed to start coach session on backend:", err);
        toast.error(
          "Connection issue",
          "Could not initialize coach session. Ensure FastAPI backend is online."
        );
      } finally {
        setIsInitializing(false);
      }
    },
    [user?.id, guestUserId, setCoachSessionId, speakCoach]
  );

  // Initialize coach session on component mount
  useEffect(() => {
    initSessionForMode(selectedMode);

    return () => {
      stopSpeaking();
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore
        }
      }
    };
  }, [initSessionForMode, selectedMode]);

  // Handle Mode Change by user
  const handleModeChange = (newMode: CoachMode) => {
    if (newMode === selectedMode) return;
    setSelectedMode(newMode);
  };

  // Start Voice Recording with Live Speech Recognition
  const handleRecordingStart = (stream: MediaStream) => {
    setLiveStream(stream);
    recordingStartTimeRef.current = Date.now();

    // Check for Web Speech Recognition API
    if (typeof window !== "undefined") {
      const SpeechRecognitionClass =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

      if (SpeechRecognitionClass) {
        try {
          const recognition = new SpeechRecognitionClass();
          recognitionRef.current = recognition;
          recognition.continuous = true;
          recognition.interimResults = true;
          recognition.lang = "en-US";

          recognition.onresult = (event: any) => {
            const interimText = Array.from(event.results)
              .map((r: any) => r[0].transcript)
              .join(" ");

            const elapsedMinutes = (Date.now() - recordingStartTimeRef.current) / 60000;
            const words = interimText.trim().split(/\s+/).filter(Boolean);
            if (elapsedMinutes > 0 && words.length > 0) {
              const liveWpm = Math.round(words.length / elapsedMinutes);
              setCalculatedWpm(liveWpm);
            }

            const liveFillers = detectFillerWords(interimText);
            setDetectedFillers(liveFillers);
          };

          recognition.onerror = () => {
            // Safe fallback to duration-based calculation
          };

          recognition.start();
        } catch (err) {
          console.warn("Could not start live speech recognition:", err);
        }
      }
    }
  };

  // Process User Speech or Text Answer
  const processCoachTurn = useCallback(
    async (userInputText: string, durationSecs?: number) => {
      const cleanText = userInputText.trim();
      if (!cleanText) {
        toast.warning("Empty response", "Please provide a verbal or typed response.");
        return;
      }

      setSpokenTranscript(cleanText);
      const currentSid = activeSessionId || coachSessionId;

      if (!currentSid) {
        toast.error("Session error", "No active coach session found.");
        return;
      }

      setIsProcessing(true);
      stopSpeaking();
      toast.info("Analyzing speech", "Evaluating communication clarity & scanning for refinement...");

      try {
        // Calculate final authoritative vocal metrics
        const secs = durationSecs || 6;
        const wpm = calculateWPM(cleanText, secs);
        if (wpm > 0) setCalculatedWpm(wpm);

        const fillers = detectFillerWords(cleanText);
        setDetectedFillers(fillers);

        // Submit to POST /coach/respond
        const respondData = await submitCoachResponse(currentSid, cleanText);

        if (respondData) {
          setExchangesCount((prev) => prev + 1);

          if (respondData.coach_message) {
            setCoachMessage(respondData.coach_message);
          }

          if (respondData.correction) {
            setActiveCorrection(respondData.correction);
            toast.info(
              "Linguistic Refinement",
              `Refinement suggested: "${respondData.correction.improved}"`
            );
          } else {
            setActiveCorrection(null);
            toast.success("Clear Delivery", "Articulate phrasing — zero correction needed!");
          }

          if (respondData.next_prompt) {
            setPromptText(respondData.next_prompt);
          }

          // Voice the coach feedback message or next prompt
          const textToSpeak = respondData.coach_message || respondData.next_prompt;
          speakCoach(textToSpeak);

          // Save exchange to Zustand store for backward compatibility
          addCoachSession({
            id: currentSid,
            user_id: user?.id || guestUserId,
            mode: selectedMode,
            exchanges: [
              {
                prompt: promptText,
                transcript: cleanText,
                feedback: respondData.coach_message,
                wpm: wpm > 0 ? wpm : 135,
                fillers_detected: fillers.length,
                correction: respondData.correction,
              },
            ],
            summary: {
              avg_wpm: wpm > 0 ? wpm : 135,
              total_fillers: fillers.length,
              grammar_score: respondData.correction ? 88 : 96,
              fluency_tier: "Proficient",
            },
            is_complete: false,
            created_at: new Date().toISOString(),
          } as any);
        }
      } catch (err) {
        console.error("Error submitting response to coach:", err);
        toast.error("Coach response error", "Could not submit to coach. Please retry.");
      } finally {
        setIsProcessing(false);
        setTextAnswerInput("");
      }
    },
    [
      activeSessionId,
      coachSessionId,
      selectedMode,
      promptText,
      user?.id,
      guestUserId,
      addCoachSession,
      speakCoach,
    ]
  );

  // Stop Voice Recording -> POST /voice/process -> processCoachTurn
  const handleRecordingStop = useCallback(
    async (blob: Blob, durationSeconds: number) => {
      setLiveStream(null);
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore
        }
      }

      setIsProcessing(true);
      stopSpeaking();
      toast.info("Transcribing speech", "Analyzing audio with NVIDIA Parakeet STT...");

      try {
        const currentSid = activeSessionId || coachSessionId;
        const response = await sendVoiceAudio(
          blob,
          "coach",
          promptText,
          currentSid || undefined
        );

        setCoachVoiceResponse(response);
        const transcript = response.transcript?.trim();

        if (transcript) {
          await processCoachTurn(transcript, durationSeconds);
        } else {
          toast.warning("No speech detected", "Please speak clearly or use direct text input.");
        }
      } catch (err) {
        console.error("Error processing voice audio with Parakeet STT:", err);
        toast.error("Audio pipeline error", "Could not transcribe audio. You can type your answer below.");
      } finally {
        setIsProcessing(false);
      }
    },
    [activeSessionId, coachSessionId, promptText, processCoachTurn]
  );

  // Direct Text Fallback Submission
  const handleTextSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!textAnswerInput.trim() || isSubmittingText) return;

    setIsSubmittingText(true);
    try {
      await processCoachTurn(textAnswerInput);
    } finally {
      setIsSubmittingText(false);
    }
  };

  // Conclude Coach Session Trigger
  const handleFinishSession = async () => {
    setIsEndingSession(true);
    stopSpeaking();
    const currentSid = activeSessionId || coachSessionId;

    try {
      if (currentSid) {
        const endResp = await endCoachSession(currentSid);
        if (endResp) {
          setCoachReport(endResp);
          toast.success(
            "Session concluded",
            endResp.summary?.encouragement || "Communication profile successfully updated!"
          );
        }
      }
      setActiveSection(5);
      router.push("/analytics/communication");
    } catch (err) {
      console.warn("Error concluding coach session on backend:", err);
      setActiveSection(5);
      router.push("/analytics/communication");
    } finally {
      setIsEndingSession(false);
    }
  };

  const currentModeInfo = MODE_CONFIG[selectedMode];

  return (
    <section className="space-y-5 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-white tracking-tight">
              AI Communication Coach
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-amber-400" />
              <span>NVIDIA Nemotron 70B</span>
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time vocal fluency, speaking pace, answer structuring, and structured linguistic refinement.
          </p>
        </div>

        {/* Coach Mode Selector: Exact 3 backend modes */}
        <div className="flex items-center gap-1 bg-[#111A2E] p-1 rounded-lg border border-subtle text-xs">
          <button
            type="button"
            onClick={() => handleModeChange("answer_training")}
            disabled={isInitializing}
            className={`px-3 py-1.5 rounded-md transition-all font-medium flex items-center gap-1.5 ${
              selectedMode === "answer_training"
                ? "bg-[#2563EB] text-white shadow"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>STAR Answer Training</span>
          </button>

          <button
            type="button"
            onClick={() => handleModeChange("conversation")}
            disabled={isInitializing}
            className={`px-3 py-1.5 rounded-md transition-all font-medium flex items-center gap-1.5 ${
              selectedMode === "conversation"
                ? "bg-[#2563EB] text-white shadow"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>Everyday Fluency</span>
          </button>

          <button
            type="button"
            onClick={() => handleModeChange("english_improvement")}
            disabled={isInitializing}
            className={`px-3 py-1.5 rounded-md transition-all font-medium flex items-center gap-1.5 ${
              selectedMode === "english_improvement"
                ? "bg-[#2563EB] text-white shadow"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <span>English & Grammar</span>
          </button>
        </div>
      </div>

      {/* Mode Description & Active Focus Card */}
      <div className="card-clean p-4 bg-[#111A2E] border-blue-500/20 flex items-center justify-between gap-4 text-xs">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 shrink-0">
            <BookOpen className="w-4 h-4" />
          </div>
          <div>
            <div className="font-semibold text-white">
              {currentModeInfo.label} · <span className="text-blue-400 font-normal">{currentModeInfo.focus}</span>
            </div>
            <div className="text-[11px] text-slate-400">{currentModeInfo.description}</div>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <span className="text-[11px] font-mono text-slate-400 bg-[#0B1120] px-2.5 py-1 rounded border border-subtle">
            Exchanges: <strong className="text-white">{exchangesCount}</strong>
          </span>

          <button
            type="button"
            onClick={() => initSessionForMode(selectedMode)}
            disabled={isInitializing}
            className="text-[11px] font-mono text-slate-300 hover:text-white bg-[#0B1120] hover:bg-[#131f38] px-2.5 py-1 rounded border border-subtle flex items-center gap-1 transition-colors"
            title="Reset and start fresh session in this mode"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Restart Mode</span>
          </button>
        </div>
      </div>

      {/* Practice Exercise Prompt Card */}
      <div className="card-clean p-5 bg-[#0B1120] border-blue-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-lg">
        <div className="flex-1">
          <div className="text-xs font-mono text-blue-400 uppercase mb-1.5 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>Active Coach Prompt ({currentModeInfo.badge})</span>
          </div>

          {isInitializing ? (
            <div className="flex items-center gap-2 text-slate-400 text-sm py-1">
              <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
              <span>Initializing practice prompt from backend...</span>
            </div>
          ) : (
            <p className="text-base text-white font-medium leading-relaxed">
              &quot;{promptText}&quot;
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => speakCoach(promptText)}
            disabled={isCoachSpeaking || isInitializing}
            className="text-xs font-medium bg-[#111A2E] hover:bg-[#1a2947] disabled:opacity-40 text-blue-300 border border-subtle px-3 py-2 rounded-lg flex items-center gap-1.5 transition-colors"
            title="Listen to the coach prompt out loud"
          >
            <Volume2 className="w-3.5 h-3.5" />
            <span>Read Prompt</span>
          </button>

          <button
            type="button"
            onClick={handleFinishSession}
            disabled={isEndingSession || isInitializing}
            className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-4 py-2 rounded-lg border border-emerald-500/30 flex items-center gap-1.5 transition-colors shadow-md disabled:opacity-50"
          >
            {isEndingSession ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Finalizing...</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Conclude Session</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Practice & Feedback Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Left Column: Candidate Verbal Delivery & Audio Pipeline (2 cols) */}
        <div className="md:col-span-2 card-clean p-5 bg-[#111A2E] space-y-4">
          <div className="flex items-center justify-between text-xs border-b border-subtle pb-3">
            <span className="font-semibold text-white">Your Verbal Delivery</span>
            <div className="flex items-center gap-3">
              <span className="font-mono text-slate-300 flex items-center gap-1.5 text-[11px]">
                <Activity className="w-3.5 h-3.5 text-emerald-400" />
                <span>
                  Pacing: <strong className="text-emerald-400">{calculatedWpm} WPM</strong>
                </span>
              </span>

              <span className="font-mono text-slate-400 text-[11px]">
                {detectedFillers.length > 0
                  ? `${detectedFillers.reduce((acc, f) => acc + f.count, 0)} filler word(s)`
                  : "0 fillers"}
              </span>
            </div>
          </div>

          {/* Dynamic Waveform Visualizer */}
          <div className="rounded-lg bg-[#0B1120] border border-subtle p-3 flex flex-col items-center">
            <VoiceVisualizer
              stream={liveStream}
              state={liveStream ? "recording" : isCoachSpeaking ? "speaking" : "idle"}
              height={64}
              className="w-full"
            />
          </div>

          {/* Last Spoken/Transcribed Answer */}
          <div className="p-4 rounded-lg bg-[#0B1120] border border-subtle text-xs leading-relaxed text-slate-200">
            {isProcessing ? (
              <div className="flex items-center gap-2 text-blue-400 py-1 font-mono">
                <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                <span>Transcribing & scoring speech with Parakeet STT...</span>
              </div>
            ) : spokenTranscript ? (
              <p>&quot;{spokenTranscript}&quot;</p>
            ) : (
              <p className="text-slate-400 italic">
                Your transcribed speech will appear here. Click Record Voice Answer to respond.
              </p>
            )}
          </div>

          {/* Recording & Input Controls */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-3">
              <VoiceRecorder
                onRecordingStart={handleRecordingStart}
                onRecordingStop={handleRecordingStop}
                disabled={isProcessing || isInitializing}
              />

              <button
                type="button"
                onClick={() => setShowTextFallback(!showTextFallback)}
                className="text-xs font-mono text-slate-400 hover:text-white px-2.5 py-2 rounded-lg border border-subtle bg-[#0B1120] flex items-center gap-1.5 transition-colors"
              >
                <MessageSquare className="w-3.5 h-3.5 text-blue-400" />
                <span>{showTextFallback ? "Hide Text Fallback" : "Type Response"}</span>
              </button>
            </div>

            <div className="text-[11px] font-mono text-slate-400">
              Target: 130–150 WPM · &lt; 2 fillers/min
            </div>
          </div>

          {/* Direct Text Fallback Drawer */}
          {showTextFallback && (
            <form
              onSubmit={handleTextSubmit}
              className="p-3.5 rounded-lg bg-[#0B1120] border border-blue-500/20 space-y-2.5 animate-in fade-in"
            >
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-white flex items-center gap-1.5">
                  <MessageSquare className="w-3.5 h-3.5 text-blue-400" />
                  <span>Type Practice Response</span>
                </span>
                <span className="text-[10px] font-mono text-slate-400">Text Fallback</span>
              </div>

              <textarea
                rows={3}
                value={textAnswerInput}
                onChange={(e) => setTextAnswerInput(e.target.value)}
                disabled={isProcessing || isSubmittingText}
                placeholder="Type your practice response here if your microphone is unavailable..."
                className="w-full bg-[#111A2E] border border-subtle rounded-lg p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#2563EB] transition-colors resize-none"
              />

              <div className="flex items-center justify-between">
                <span className="text-[10px] text-slate-400">
                  {textAnswerInput.trim().split(/\s+/).filter(Boolean).length} words
                </span>

                <button
                  type="submit"
                  disabled={!textAnswerInput.trim() || isSubmittingText || isProcessing}
                  className="bg-[#2563EB] hover:bg-blue-600 disabled:opacity-40 text-white text-xs font-medium px-3.5 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors shadow"
                >
                  {isSubmittingText ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      <span>Submitting...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-3 h-3" />
                      <span>Submit Practice Speech</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}

          {/* Spoken Advice Player */}
          {coachVoiceResponse && (
            <VoicePlayer
              src={coachVoiceResponse.audio_url}
              audioBase64={coachVoiceResponse.audio_base64}
              textFallback={coachMessage || coachVoiceResponse.spoken_response}
              autoPlay={false}
              onPlaybackStart={() => setIsCoachSpeaking(true)}
              onPlaybackEnd={() => setIsCoachSpeaking(false)}
              label="Coach Feedback Audio"
              className="mt-2"
            />
          )}

          {/* Coach Conversational Message */}
          {coachMessage && (
            <div className="p-3.5 rounded-lg bg-[#0B1120] border border-blue-500/20 text-xs text-slate-200 flex items-start gap-2.5">
              <div className="w-6 h-6 rounded bg-blue-600 flex items-center justify-center font-bold text-[10px] text-white shrink-0 mt-0.5">
                AI
              </div>
              <div className="space-y-0.5">
                <div className="text-[10px] font-mono text-blue-400">Coach Guidance:</div>
                <p className="leading-relaxed">{coachMessage}</p>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Real-Time Refinement Panel (1 col) */}
        <div className="card-clean p-5 bg-[#111A2E] space-y-4 flex flex-col justify-between">
          <div className="space-y-4">
            <h2 className="text-xs font-semibold text-white uppercase tracking-wider font-mono flex items-center gap-1.5">
              <Lightbulb className="w-4 h-4 text-amber-400" />
              <span>Real-Time Refinement</span>
            </h2>

            {/* Linguistic Refinement Card */}
            <div className="space-y-3 text-xs">
              {activeCorrection ? (
                <div className="p-3.5 rounded-lg bg-[#0B1120] border border-amber-500/30 space-y-2">
                  <div className="text-amber-400 font-mono text-[10px] uppercase flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-amber-400" />
                    <span>Linguistic Refinement</span>
                  </div>

                  <div>
                    <div className="text-[10px] font-mono text-slate-400">Original utterance:</div>
                    <div className="line-through text-slate-400 text-xs font-mono mt-0.5">
                      &quot;{activeCorrection.original}&quot;
                    </div>
                  </div>

                  <div>
                    <div className="text-[10px] font-mono text-emerald-400">Recommended phrasing:</div>
                    <div className="text-emerald-400 font-semibold text-xs mt-0.5">
                      → &quot;{activeCorrection.improved}&quot;
                    </div>
                  </div>

                  {activeCorrection.reason && (
                    <div className="text-slate-300 italic text-[11px] pt-1 border-t border-subtle">
                      <strong>Why:</strong> {activeCorrection.reason}
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-3.5 rounded-lg bg-[#0B1120] border border-emerald-500/20 text-slate-300 space-y-1.5">
                  <div className="text-emerald-400 font-mono text-[10px] uppercase flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Clear & Articulate</span>
                  </div>
                  <p className="text-[11px] text-slate-300 leading-relaxed">
                    Clear expression — no correction needed. You expressed your idea articulately.
                  </p>
                </div>
              )}

              {/* Filler Word Diagnostic */}
              <div className="p-3.5 rounded-lg bg-[#0B1120] border border-subtle space-y-1.5">
                <div className="text-slate-400 font-mono text-[10px] uppercase flex items-center gap-1">
                  <Activity className="w-3 h-3 text-blue-400" />
                  <span>Filler Word Diagnostic</span>
                </div>
                {detectedFillers.length > 0 ? (
                  <div className="space-y-1">
                    <p className="text-[11px] text-slate-300">
                      Detected fillers in your speech:
                    </p>
                    <div className="flex flex-wrap gap-1.5 pt-0.5">
                      {detectedFillers.map((f, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-300 font-mono text-[10px]"
                        >
                          &quot;{f.word}&quot; ({f.count}x)
                        </span>
                      ))}
                    </div>
                    <p className="text-[10px] text-slate-400 italic mt-1">
                      Tip: Replace frequent fillers with a deliberate 1-second pause.
                    </p>
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-300">
                    Zero filler words detected. Optimal vocal delivery maintained.
                  </p>
                )}
              </div>
            </div>
          </div>

          <div className="pt-2">
            <Link
              href="/analytics/communication"
              onClick={() => setActiveSection(5)}
              className="w-full bg-[#0B1120] hover:bg-[#131f38] text-white text-xs font-medium py-2.5 rounded-lg border border-subtle flex items-center justify-center gap-1.5 transition-colors"
            >
              <span>View Communication Analytics</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
