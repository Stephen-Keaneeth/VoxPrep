/**
 * VOXPREP Voice Helpers & Web Speech API Utilities
 */

// Retain active utterance reference to avoid Chrome/Chromium premature garbage collection bug
let activeUtterance: SpeechSynthesisUtterance | null = null;
let cachedVoices: SpeechSynthesisVoice[] = [];

if (typeof window !== "undefined" && "speechSynthesis" in window) {
  cachedVoices = window.speechSynthesis.getVoices();
  window.speechSynthesis.onvoiceschanged = () => {
    cachedVoices = window.speechSynthesis.getVoices();
  };
}

/**
 * Synthesizes speech using the browser's native Web Speech API (speechSynthesis).
 * Serves as the zero-latency, zero-cost fallback when remote TTS credits are low or offline.
 */
export function speakText(
  text: string,
  options?: {
    rate?: number;
    pitch?: number;
    volume?: number;
    voiceName?: string;
    onEnd?: () => void;
    onError?: (err: unknown) => void;
  }
): SpeechSynthesisUtterance | null {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    console.warn("Web Speech API is not supported in this browser environment.");
    options?.onEnd?.();
    return null;
  }

  // Cancel any ongoing speech
  window.speechSynthesis.cancel();

  // Strip leading/trailing quotes and markdown bolding for clean pronunciation
  const clean = text.replace(/^["'\s]+|["'\s]+$/g, "").replace(/\*\*/g, "").trim();
  if (!clean) {
    options?.onEnd?.();
    return null;
  }

  const utterance = new SpeechSynthesisUtterance(clean);
  activeUtterance = utterance;

  utterance.rate = options?.rate ?? 0.95;
  utterance.pitch = options?.pitch ?? 1.0;
  utterance.volume = options?.volume ?? 1.0;

  // Attempt to select an English professional natural voice
  const voices = cachedVoices.length > 0 ? cachedVoices : window.speechSynthesis.getVoices();
  const selectedVoice =
    (options?.voiceName ? voices.find((v) => v.name.includes(options.voiceName!)) : null) ||
    voices.find((v) => v.lang.startsWith("en") && (v.name.includes("Natural") || v.name.includes("Neural") || v.name.includes("Online"))) ||
    voices.find((v) => v.lang.startsWith("en") && (v.name.includes("Google") || v.name.includes("Samantha") || v.name.includes("Guy") || v.name.includes("David") || v.name.includes("Mark"))) ||
    voices.find((v) => v.lang.startsWith("en-US")) ||
    voices.find((v) => v.lang.startsWith("en")) ||
    voices[0];

  if (selectedVoice) {
    utterance.voice = selectedVoice;
  }

  utterance.onend = () => {
    activeUtterance = null;
    options?.onEnd?.();
  };

  utterance.onerror = (e) => {
    activeUtterance = null;
    console.warn("Speech synthesis encountered an event:", e);
    options?.onError?.(e);
  };

  window.speechSynthesis.resume();
  window.speechSynthesis.speak(utterance);
  return utterance;
}

/**
 * Stops any active speech synthesis playback.
 */
export function stopSpeaking(): void {
  activeUtterance = null;
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

/**
 * Estimates speaking rate in words per minute (WPM).
 */
export function calculateWPM(text: string, durationSeconds: number): number {
  if (!text || durationSeconds <= 0) return 0;
  const wordCount = text.trim().split(/\s+/).length;
  const minutes = durationSeconds / 60;
  return Math.round(wordCount / minutes);
}

/**
 * Detects frequent filler words in spoken transcript text.
 */
export function detectFillerWords(text: string): { word: string; count: number }[] {
  const fillers = ["like", "um", "uh", "basically", "actually", "you know", "sort of", "kind of"];
  const lower = text.toLowerCase();
  const results: { word: string; count: number }[] = [];

  for (const filler of fillers) {
    const regex = new RegExp(`\\b${filler}\\b`, "gi");
    const matches = lower.match(regex);
    if (matches && matches.length > 0) {
      results.push({ word: filler, count: matches.length });
    }
  }

  return results;
}

