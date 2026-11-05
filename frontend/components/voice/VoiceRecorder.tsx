"use client";

import React, { useState, useRef, useEffect } from "react";
import { Mic, Square, AlertCircle } from "lucide-react";

interface VoiceRecorderProps {
  onRecordingStart?: (stream: MediaStream) => void;
  onRecordingStop?: (blob: Blob, durationSeconds: number) => void;
  onError?: (err: unknown) => void;
  disabled?: boolean;
  className?: string;
}

export default function VoiceRecorder({
  onRecordingStart,
  onRecordingStop,
  onError,
  disabled = false,
  className = "",
}: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const startTimeRef = useRef<number>(0);

  // Clear timers on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const startRecording = async () => {
    setErrorMsg(null);
    audioChunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Select supported mimeType
      let mimeType = "audio/webm;codecs=opus";
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = "audio/webm";
        if (!MediaRecorder.isTypeSupported(mimeType)) {
          mimeType = ""; // Browser default
        }
      }

      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        const duration = Math.round((Date.now() - startTimeRef.current) / 1000);
        onRecordingStop?.(audioBlob, duration);
      };

      recorder.start(250); // Emit chunk every 250ms
      startTimeRef.current = Date.now();
      setIsRecording(true);
      setRecordingSeconds(0);
      onRecordingStart?.(stream);

      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.warn("Could not access microphone for VoiceRecorder:", err);
      setErrorMsg("Microphone access blocked or unavailable.");
      onError?.(err);
    }
  };

  const stopRecording = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    setIsRecording(false);
  };

  const formatTimer = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remaining = secs % 60;
    return `${mins < 10 ? "0" : ""}${mins}:${remaining < 10 ? "0" : ""}${remaining}`;
  };

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {isRecording ? (
        <button
          onClick={stopRecording}
          disabled={disabled}
          className="bg-red-600 hover:bg-red-500 text-white font-medium text-xs px-4 py-2 rounded-lg flex items-center gap-2 transition-all shadow-md animate-pulse"
        >
          <Square className="w-4 h-4 fill-current" />
          <span>Stop & Process ({formatTimer(recordingSeconds)})</span>
        </button>
      ) : (
        <button
          onClick={startRecording}
          disabled={disabled}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium text-xs px-4 py-2 rounded-lg flex items-center gap-2 transition-all shadow"
        >
          <Mic className="w-4 h-4" />
          <span>Record Voice Answer</span>
        </button>
      )}

      {errorMsg && (
        <span className="text-[11px] font-mono text-red-400 flex items-center gap-1">
          <AlertCircle className="w-3.5 h-3.5" />
          <span>{errorMsg}</span>
        </span>
      )}
    </div>
  );
}

