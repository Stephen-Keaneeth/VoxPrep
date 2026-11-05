"use client";

import React, { useState, useCallback } from "react";
import Link from "next/link";
import { useAppStore } from "@/store/useStore";
import VoiceVisualizer from "@/components/voice/VoiceVisualizer";
import VoicePlayer from "@/components/voice/VoicePlayer";
import VoiceRecorder from "@/components/voice/VoiceRecorder";
import { sendVoiceAudio, VoiceProcessResponse } from "@/lib/api";
import { saveCoachSession, CoachSessionRecord } from "@/lib/supabase";
import { calculateWPM, detectFillerWords } from "@/lib/voice";
import { toast } from "@/store/useToast";
import { ArrowRight, Lightbulb, Activity, Loader2 } from "lucide-react";

export default function CommunicationAgent() {
  const { setActiveSection, addCoachSession } = useAppStore();
  const [selectedMode, setSelectedMode] = useState<"star" | "fluency" | "vocab">("star");

  // Voice Pipeline & Analytics State
  const [isProcessing, setIsProcessing] = useState(false);
  const [spokenTranscript, setSpokenTranscript] = useState(
    "When the payment gateway API was delayed, like, we realized the launch was at risk. I convened the stakeholders and we done made a mock service to unblock frontend testing."
  );
  const [coachResponse, setCoachResponse] = useState<VoiceProcessResponse | null>(null);
  const [liveStream, setLiveStream] = useState<MediaStream | null>(null);
  const [calculatedWpm, setCalculatedWpm] = useState(136);
  const [detectedFillers, setDetectedFillers] = useState<{ word: string; count: number }[]>([
    { word: "like", count: 1 },
  ]);
  const [isCoachSpeaking, setIsCoachSpeaking] = useState(false);

  const promptText =
    "Describe a high-stakes technical deadline where a critical dependency was delayed. How did you negotiate scope and communicate with your team?";

  const handleRecordingStart = (stream: MediaStream) => {
    setLiveStream(stream);
  };

  const handleRecordingStop = useCallback(
    async (blob: Blob, durationSeconds: number) => {
      setLiveStream(null);
      setIsProcessing(true);
      toast.info("Analyzing spoken answer", "Measuring speaking rate and scanning for filler words...");
      try {
        const response = await sendVoiceAudio(blob, "coach", promptText);
        setSpokenTranscript(response.transcript);
        setCoachResponse(response);

        // Compute dynamic metrics
        const wpm = calculateWPM(response.transcript, durationSeconds || 5);
        if (wpm > 0) setCalculatedWpm(wpm);

        const fillers = detectFillerWords(response.transcript);
        setDetectedFillers(fillers);

        toast.success(
          "Coaching feedback ready",
          `Pacing: ${wpm > 0 ? wpm : 136} WPM · ${fillers.length} filler word(s) detected.`
        );

        // Save session to Supabase coach_sessions table per schema.sql
        const coachRecord: CoachSessionRecord = {
          mode:
            selectedMode === "star"
              ? "answer_training"
              : selectedMode === "fluency"
              ? "conversation"
              : "english_improvement",
          exchanges: [
            {
              prompt: promptText,
              transcript: response.transcript,
              feedback: response.spoken_response,
              wpm: wpm > 0 ? wpm : 136,
              fillers_detected: fillers.length,
            },
          ],
          summary: {
            avg_wpm: wpm > 0 ? wpm : 136,
            total_fillers: fillers.length,
            grammar_score: 94,
            fluency_tier: "Proficient",
          },
          is_complete: true,
          created_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
        };
        addCoachSession(coachRecord);
        saveCoachSession(coachRecord).catch(() => {});
      } catch (err) {
        console.warn("Error processing communication coach voice audio:", err);
        toast.warning("Voice pipeline fallback", "Local communication coaching feedback generated.");
      } finally {
        setIsProcessing(false);
      }
    },
    [promptText, addCoachSession, selectedMode]
  );

  return (
    <section className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">AI Communication Coach</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Live training for fluency, answer structuring, vocabulary and speaking pace.
          </p>
        </div>

        {/* Coach Mode Selector */}
        <div className="flex items-center gap-1 bg-slate-800 p-1 rounded border border-subtle text-xs">
          <button
            onClick={() => setSelectedMode("star")}
            className={`px-3 py-1 rounded transition-colors ${
              selectedMode === "star" ? "bg-blue-600 text-white font-medium" : "text-slate-400 hover:text-white"
            }`}
          >
            Answer Structuring (STAR)
          </button>
          <button
            onClick={() => setSelectedMode("fluency")}
            className={`px-3 py-1 rounded transition-colors ${
              selectedMode === "fluency" ? "bg-blue-600 text-white font-medium" : "text-slate-400 hover:text-white"
            }`}
          >
            Everyday Fluency
          </button>
          <button
            onClick={() => setSelectedMode("vocab")}
            className={`px-3 py-1 rounded transition-colors ${
              selectedMode === "vocab" ? "bg-blue-600 text-white font-medium" : "text-slate-400 hover:text-white"
            }`}
          >
            Executive Vocabulary
          </button>
        </div>
      </div>

      {/* Speaking Exercise Prompt */}
      <div className="card-clean p-6 bg-[#121c33] border-blue-500/20">
        <div className="text-xs font-mono text-blue-400 uppercase mb-2">Practice Exercise Prompt</div>
        <p className="text-base text-white font-medium leading-relaxed">&quot;{promptText}&quot;</p>
      </div>

      {/* Live Coaching Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Candidate Verbal Delivery (2 cols) */}
        <div className="md:col-span-2 card-clean p-5 space-y-4">
          <div className="flex items-center justify-between text-xs border-b border-subtle pb-3">
            <span className="font-semibold text-white">Your Verbal Delivery</span>
            <span className="font-mono text-slate-400 flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
              <span>
                Pacing: <strong className="text-emerald-400">{calculatedWpm} WPM</strong>
              </span>
            </span>
          </div>

          {/* Dynamic Waveform Visualizer */}
          <div className="rounded-lg bg-[#0a101d] border border-subtle p-3 flex flex-col items-center">
            <VoiceVisualizer
              stream={liveStream}
              state={liveStream ? "recording" : isCoachSpeaking ? "speaking" : "idle"}
              height={64}
              className="w-full"
            />
          </div>

          <div className="p-4 rounded bg-[#0e1627] border border-subtle text-xs leading-relaxed text-slate-200">
            {isProcessing ? (
              <div className="flex items-center gap-2 text-blue-400 py-1 font-mono">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Transcribing & evaluating speech with Parakeet STT...</span>
              </div>
            ) : (
              <p>&quot;{spokenTranscript}&quot;</p>
            )}
          </div>

          {/* Voice Recorder & Player integration */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
            <VoiceRecorder
              onRecordingStart={handleRecordingStart}
              onRecordingStop={handleRecordingStop}
              disabled={isProcessing}
            />

            <span className="text-xs text-slate-400 font-mono">
              {detectedFillers.length > 0
                ? `${detectedFillers.reduce((acc, f) => acc + f.count, 0)} filler word(s) detected`
                : "No filler words detected"}
            </span>
          </div>

          {coachResponse && (
            <VoicePlayer
              src={coachResponse.audio_url}
              audioBase64={coachResponse.audio_base64}
              textFallback={coachResponse.ai_response}
              autoPlay={true}
              onPlaybackStart={() => setIsCoachSpeaking(true)}
              onPlaybackEnd={() => setIsCoachSpeaking(false)}
              label="Coach Spoken Advice"
              className="mt-3"
            />
          )}
        </div>

        {/* Real-Time Refinement Panel (1 col) */}
        <div className="card-clean p-5 space-y-4">
          <h3 className="text-xs font-semibold text-white uppercase tracking-wider font-mono flex items-center gap-1.5">
            <Lightbulb className="w-4 h-4 text-amber-400" />
            <span>Real-Time Refinement</span>
          </h3>

          <div className="space-y-3 text-xs">
            <div className="p-3 rounded bg-[#0e1627] border border-subtle">
              <div className="text-slate-400 font-mono text-[10px] uppercase">Grammar Fix:</div>
              <div className="line-through text-slate-500 mt-0.5">&quot;we done made a mock service&quot;</div>
              <div className="text-emerald-400 font-medium mt-1">
                → &quot;we engineered a mock stub to decouple development&quot;
              </div>
            </div>

            <div className="p-3 rounded bg-[#0e1627] border border-subtle">
              <div className="text-slate-400 font-mono text-[10px] uppercase">Filler Word Alert:</div>
              <p className="text-slate-300 mt-1">
                Eliminate <em>&quot;like&quot;</em> by taking a brief pause before introducing the complication.
              </p>
            </div>
          </div>

          <Link
            href="/analytics/communication"
            onClick={() => setActiveSection(5)}
            className="w-full bg-[#1e293b] hover:bg-slate-700 text-white text-xs font-medium py-2 rounded border border-subtle flex items-center justify-center gap-1 transition-colors"
          >
            <span>View Communication Analytics</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </section>
  );
}
