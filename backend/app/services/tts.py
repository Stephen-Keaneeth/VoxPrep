"""NVIDIA Magpie TTS Service Wrapper for VOXPREP Backend.
Milestone 1: Phase 1 AI Services, Voice Pipeline, and Authentication.

Integrates with NVIDIA Magpie Multilingual TTS REST endpoint (audio/speech).
Implements fail-safe error handling (returns None on failure) and pure-Python WAV mock generation.
"""

import logging
import os
import struct
from typing import Optional
from dotenv import load_dotenv
import httpx

load_dotenv()
logger = logging.getLogger("voxprep.services.tts")

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/magpie-tts-multilingual"


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


def generate_mock_wav(duration_ms: int = 300, sample_rate: int = 16000) -> bytes:
    """Generates valid 16kHz mono 16-bit PCM WAV audio bytes without C-build dependencies."""
    num_samples = int(sample_rate * (duration_ms / 1000.0))
    data_size = num_samples * 2
    riff_header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE"
    fmt_chunk = b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    data_chunk = b"data" + struct.pack("<I", data_size) + (b"\x00\x00" * num_samples)
    return riff_header + fmt_chunk + data_chunk


async def synthesize(text: str) -> Optional[bytes]:
    """Synthesizes speech audio from text using NVIDIA Magpie TTS REST API.

    Args:
        text: Input string to synthesize.

    Returns:
        Binary WAV audio bytes or None on failure or empty input.
    """
    if not text or not text.strip():
        logger.warning("TTS synthesize called with empty or whitespace-only text.")
        return None

    # Offline mock fallback
    if is_mock_mode():
        logger.debug("Executing Magpie TTS in mock fallback mode.")
        return generate_mock_wav()

    base_url = os.getenv("NVIDIA_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    tts_url = f"{base_url}/audio/speech"
    model = os.getenv("NVIDIA_TTS_MODEL", DEFAULT_MODEL).strip()
    api_key = os.getenv("NVIDIA_API_KEY", "").strip()

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/wav, audio/mpeg, */*",
        }
        payload = {
            "model": model,
            "input": text.strip(),
            "voice": "alloy",
            "response_format": "wav",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(tts_url, headers=headers, json=payload)

        if response.status_code == 200:
            audio_bytes = response.content
            if audio_bytes and len(audio_bytes) > 0:
                return audio_bytes
            logger.warning("Magpie TTS returned HTTP 200 with empty audio body.")
            return None
        else:
            logger.error(
                f"Magpie TTS API returned error status {response.status_code}: {response.text}"
            )
            return None

    except Exception as exc:
        logger.error(f"Unhandled exception during Magpie TTS synthesis: {exc}")
        return None
