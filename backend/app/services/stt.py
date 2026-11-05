"""NVIDIA Parakeet ASR STT Service Wrapper for VOXPREP Backend.
Milestone 1: Phase 1 AI Services, Voice Pipeline, and Authentication.

Integrates with NVIDIA Parakeet CTC 1.1B ASR REST endpoint (multipart/form-data).
Implements fail-safe error handling (returns None on failure) and offline mock mode.
"""

import logging
import os
from typing import Optional
from dotenv import load_dotenv
import httpx

load_dotenv()
logger = logging.getLogger("voxprep.services.stt")

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/parakeet-ctc-1.1b-asr"


def is_mock_mode() -> bool:
    """Returns True if live NVIDIA API key is missing or dummy/placeholder."""
    if os.getenv("MOCK_AI_SERVICES", "").lower() in ("true", "1", "yes"):
        return True
    key = os.getenv("NVIDIA_API_KEY", "").strip()
    if not key:
        return True
    lower_key = key.lower()
    return any(
        token in lower_key
        for token in ["placeholder", "dummy", "test", "your-", "your_", "mock", "example"]
    )


async def transcribe(audio_bytes: bytes) -> Optional[str]:
    """Transcribes audio bytes to text using NVIDIA Parakeet ASR REST API.

    Args:
        audio_bytes: Binary audio data.

    Returns:
        Transcribed string or None on failure or empty/corrupt audio.
    """
    if not audio_bytes or len(audio_bytes) < 10:
        logger.warning("STT transcribe called with empty or insufficient audio bytes.")
        return None

    # Offline mock fallback
    if is_mock_mode():
        # Check for corrupt audio boundary testing
        if audio_bytes.startswith(b"NOT_A_VALID") or b"CORRUPTED" in audio_bytes:
            logger.warning("Mock STT received corrupt audio stream; returning None.")
            return None
        logger.debug("Executing Parakeet STT in mock fallback mode.")
        return "I have extensive experience designing microservices using FastAPI, Celery, and PostgreSQL."

    base_url = os.getenv("NVIDIA_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    stt_url = f"{base_url}/audio/transcriptions"
    model = os.getenv("NVIDIA_STT_MODEL", DEFAULT_MODEL).strip()
    api_key = os.getenv("NVIDIA_API_KEY", "").strip()

    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        data = {"model": model, "response_format": "json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(stt_url, headers=headers, files=files, data=data)

        if response.status_code == 200:
            result = response.json()
            transcript = result.get("text") or result.get("transcription")
            if transcript:
                return str(transcript).strip()
            logger.warning("Parakeet STT returned HTTP 200 with empty transcription field.")
            return None
        else:
            logger.error(
                f"Parakeet STT API returned error status {response.status_code}: {response.text}"
            )
            return None

    except Exception as exc:
        logger.error(f"Unhandled exception during Parakeet STT transcription: {exc}")
        return None
