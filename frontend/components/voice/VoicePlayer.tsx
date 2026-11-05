"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { Play, Pause, Volume2, VolumeX, RotateCcw } from "lucide-react";
import { speakText, stopSpeaking } from "@/lib/voice";

interface VoicePlayerProps {
  src?: string;
  audioBase64?: string;
  textFallback?: string;
  autoPlay?: boolean;
  onPlaybackStart?: () => void;
  onPlaybackEnd?: () => void;
  label?: string;
  className?: string;
}

export default function VoicePlayer({
  src,
  audioBase64,
  textFallback,
  autoPlay = false,
  onPlaybackStart,
  onPlaybackEnd,
  label = "AI Audio Response",
  className = "",
}: VoicePlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const [useWebSpeech, setUseWebSpeech] = useState(false);

  // Determine effective audio source
  const effectiveSrc = React.useMemo(() => {
    if (audioBase64) {
      if (audioBase64.startsWith("data:")) return audioBase64;
      return `data:audio/wav;base64,${audioBase64}`;
    }
    return src || "";
  }, [src, audioBase64]);

  const handlePlay = useCallback(() => {
    if (effectiveSrc && audioRef.current) {
      audioRef.current
        .play()
        .then(() => {
          setIsPlaying(true);
          onPlaybackStart?.();
        })
        .catch((err) => {
          console.warn("Audio element play rejected, trying Web Speech fallback:", err);
          if (textFallback) {
            setUseWebSpeech(true);
            setIsPlaying(true);
            onPlaybackStart?.();
            speakText(textFallback, {
              onEnd: () => {
                setIsPlaying(false);
                onPlaybackEnd?.();
              },
            });
          }
        });
    } else if (textFallback) {
      setUseWebSpeech(true);
      setIsPlaying(true);
      onPlaybackStart?.();
      speakText(textFallback, {
        onEnd: () => {
          setIsPlaying(false);
          onPlaybackEnd?.();
        },
      });
    }
  }, [effectiveSrc, textFallback, onPlaybackStart, onPlaybackEnd]);

  const handlePause = useCallback(() => {
    if (useWebSpeech) {
      stopSpeaking();
    } else if (audioRef.current) {
      audioRef.current.pause();
    }
    setIsPlaying(false);
  }, [useWebSpeech]);

  // Handle Autoplay
  useEffect(() => {
    if (autoPlay) {
      handlePlay();
    }
    const currentAudio = audioRef.current;
    return () => {
      stopSpeaking();
      if (currentAudio) {
        currentAudio.pause();
      }
    };
  }, [autoPlay, handlePlay]);

  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remaining = Math.floor(secs % 60);
    return `${mins}:${remaining < 10 ? "0" : ""}${remaining}`;
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    setCurrentTime(time);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
    }
  };

  return (
    <div
      className={`card-clean p-3 bg-[#0d1527] border border-subtle flex items-center justify-between gap-3 text-xs ${className}`}
    >
      {effectiveSrc && (
        <audio
          ref={audioRef}
          src={effectiveSrc}
          onTimeUpdate={() => {
            if (audioRef.current) setCurrentTime(audioRef.current.currentTime);
          }}
          onLoadedMetadata={() => {
            if (audioRef.current) setDuration(audioRef.current.duration);
          }}
          onEnded={() => {
            setIsPlaying(false);
            onPlaybackEnd?.();
          }}
        />
      )}

      {/* Play / Pause Toggle Button */}
      <button
        onClick={isPlaying ? handlePause : handlePlay}
        className="w-8 h-8 rounded-full bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center shrink-0 transition-colors shadow"
        title={isPlaying ? "Pause Audio" : "Play Audio"}
      >
        {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
      </button>

      {/* Progress & Title */}
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center justify-between text-[11px] text-slate-300">
          <span className="truncate font-medium text-white">{label}</span>
          <span className="font-mono text-slate-400 text-[10px]">
            {useWebSpeech ? "Web Speech TTS" : `${formatTime(currentTime)} / ${formatTime(duration || 0)}`}
          </span>
        </div>

        {!useWebSpeech && duration > 0 ? (
          <input
            type="range"
            min={0}
            max={duration || 1}
            step={0.1}
            value={currentTime}
            onChange={handleSeek}
            className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
          />
        ) : (
          <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full bg-blue-500 rounded-full ${
                isPlaying ? "animate-pulse w-full" : "w-0"
              }`}
            />
          </div>
        )}
      </div>

      {/* Mute Toggle */}
      <button
        onClick={() => {
          if (audioRef.current) {
            audioRef.current.muted = !isMuted;
          }
          setIsMuted(!isMuted);
        }}
        className="text-slate-400 hover:text-white p-1"
        title={isMuted ? "Unmute" : "Mute"}
      >
        {isMuted ? <VolumeX className="w-4 h-4 text-red-400" /> : <Volume2 className="w-4 h-4" />}
      </button>
    </div>
  );
}

