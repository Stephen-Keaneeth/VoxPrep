/**
 * VOXPREP Voice Helpers & Web Speech API Utilities
 */

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

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = options?.rate ?? 1.0;
  utterance.pitch = options?.pitch ?? 1.0;
  utterance.volume = options?.volume ?? 1.0;

  // Attempt to select an English professional natural voice
  const voices = window.speechSynthesis.getVoices();
  const selectedVoice =
    voices.find((v) => v.lang.startsWith("en") && (v.name.includes("Natural") || v.name.includes("Google") || v.name.includes("English"))) ||
    voices.find((v) => v.lang.startsWith("en")) ||
    voices[0];

  if (selectedVoice) {
    utterance.voice = selectedVoice;
  }

  utterance.onend = () => {
    options?.onEnd?.();
  };

  utterance.onerror = (e) => {
    console.warn("Speech synthesis encountered an event:", e);
    options?.onError?.(e);
  };

  window.speechSynthesis.speak(utterance);
  return utterance;
}

/**
 * Stops any active speech synthesis playback.
 */
export function stopSpeaking(): void {
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

