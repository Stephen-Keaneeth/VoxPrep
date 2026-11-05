/**
 * VOXPREP Frontend API Client
 * Connects to Member A's FastAPI backend (http://localhost:8000)
 */

export interface VoiceProcessResponse {
  status: "success" | "fallback" | "error";
  transcript: string;
  ai_response: string;
  audio_base64?: string;
  audio_url?: string;
  duration_seconds?: number;
  mode?: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Checks if the FastAPI backend server is reachable and healthy.
 */
export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/health`, {
      method: "GET",
      signal: AbortSignal.timeout(2500),
    });
    if (res.ok) {
      const data = await res.json();
      return data.status === "ok";
    }
    return false;
  } catch {
    return false;
  }
}

/**
 * Sends recorded audio bytes to the backend voice pipeline.
 * Endpoint: POST /voice/process (multipart/form-data)
 * Fallback: If backend is offline or returns error, returns a realistic graceful simulation.
 */
export async function sendVoiceAudio(
  audioBlob: Blob,
  mode: "interview" | "coach" = "interview",
  contextText: string = ""
): Promise<VoiceProcessResponse> {
  const formData = new FormData();
  formData.append("file", audioBlob, "user_recording.webm");
  formData.append("mode", mode);
  formData.append("context", contextText);

  try {
    const res = await fetch(`${API_BASE_URL}/voice/process`, {
      method: "POST",
      body: formData,
      signal: AbortSignal.timeout(15000),
    });

    if (res.ok) {
      const data = await res.json();
      return {
        status: "success",
        transcript: data.transcript || "Audio successfully processed.",
        ai_response: data.ai_response || data.response || "I heard your response.",
        audio_base64: data.audio_base64,
        audio_url: data.audio_url,
        duration_seconds: data.duration_seconds,
        mode,
      };
    }
  } catch (err) {
    console.warn("Backend /voice/process endpoint unavailable, using graceful fallback:", err);
  }

  // Graceful fallback simulation (ensures candidate never gets blocked)
  return getSimulatedVoiceResponse(mode, contextText);
}

/**
 * Realistic fallback response generator when testing offline or before backend is deployed
 */
function getSimulatedVoiceResponse(
  mode: "interview" | "coach",
  contextText: string
): VoiceProcessResponse {
  if (mode === "coach") {
    return {
      status: "fallback",
      transcript:
        "When the API was delayed, we quickly built a mock stub so our frontend team was not blocked.",
      ai_response:
        "Excellent delivery. Your pacing was 134 words per minute, and you articulated the solution clearly without relying on filler words.",
      duration_seconds: 4.5,
      mode: "coach",
    };
  }

  return {
    status: "fallback",
    transcript:
      "I would design the URL shortener with a distributed hashing key-value store, using base62 encoding and pre-generating keys with ZooKeeper or Snowflake ID.",
    ai_response:
      "Good architectural direction. How would you handle hot URLs that receive millions of reads per second without degrading latency?",
    duration_seconds: 6.2,
    mode: "interview",
  };
}

