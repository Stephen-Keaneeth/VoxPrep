"use client";

import React, { useEffect, useRef } from "react";

interface VoiceVisualizerProps {
  stream?: MediaStream | null;
  state?: "idle" | "recording" | "speaking";
  width?: number;
  height?: number;
  className?: string;
}

export default function VoiceVisualizer({
  stream,
  state = "idle",
  width = 640,
  height = 96,
  className = "",
}: VoiceVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let audioCtx: AudioContext | null = null;
    let analyser: AnalyserNode | null = null;
    let source: MediaStreamAudioSourceNode | null = null;
    let dataArray: Uint8Array | null = null;
    let animationFrameId: number;
    let phase = 0;

    // Initialize Web Audio API Analyser if stream has active audio tracks
    if (stream && stream.getAudioTracks().length > 0 && state === "recording") {
      try {
        const AudioCtxClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        audioCtx = new AudioCtxClass();
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        source = audioCtx.createMediaStreamSource(stream);
        source.connect(analyser);
        dataArray = new Uint8Array(analyser.frequencyBinCount);
      } catch (err) {
        console.warn("Could not attach audio analyser node to stream:", err);
      }
    }

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const w = canvas.width;
      const h = canvas.height;
      const centerY = h / 2;

      // Determine color and base dynamics
      let strokeColor = "#3B82F6"; // Cobalt for idle
      let baseAmp = 8;
      let freq = 0.02;
      let speed = 0.03;

      if (state === "recording") {
        strokeColor = "#10B981"; // Emerald for candidate speaking
        baseAmp = 18;
        freq = 0.035;
        speed = 0.07;

        // If real audio analyser is active, calculate actual volume
        if (analyser && dataArray) {
          analyser.getByteFrequencyData(dataArray as any);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
          }
          const avg = sum / dataArray.length;
          baseAmp = Math.max(12, (avg / 255) * 45); // Scale amplitude by microphone volume
        }
      } else if (state === "speaking") {
        strokeColor = "#F59E0B"; // Amber for AI TTS speaking
        baseAmp = 22;
        freq = 0.025;
        speed = 0.06;
      }

      // Draw multi-layered harmonic sine waves
      const layers = [
        { ampMult: 1.0, freqMult: 1.0, alpha: 0.85, lineWidth: 2.2 },
        { ampMult: 0.55, freqMult: 1.8, alpha: 0.45, lineWidth: 1.4 },
        { ampMult: 0.28, freqMult: 2.5, alpha: 0.25, lineWidth: 1.0 },
      ];

      layers.forEach((layer) => {
        ctx.beginPath();
        ctx.strokeStyle = strokeColor;
        ctx.globalAlpha = layer.alpha;
        ctx.lineWidth = layer.lineWidth;
        ctx.lineCap = "round";

        for (let x = 0; x < w; x += 4) {
          // Window envelope so ends taper gracefully to zero at boundaries
          const envelope = Math.sin((x / w) * Math.PI);
          const y = centerY + Math.sin(x * freq * layer.freqMult + phase) * baseAmp * layer.ampMult * envelope;

          if (x === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();
      });

      phase += speed;
      animationFrameId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      cancelAnimationFrame(animationFrameId);
      if (source) source.disconnect();
      if (audioCtx && audioCtx.state !== "closed") {
        audioCtx.close().catch(() => {});
      }
    };
  }, [stream, state]);

  return (
    <div className={`relative flex items-center justify-center w-full overflow-hidden ${className}`}>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        className="w-full h-full block"
      />
    </div>
  );
}
