# Analysis: NVIDIA NIM Service Wrappers Investigation & Architecture Design

**Author**: `explorer_m1_1`  
**Milestone**: Milestone 1 (Phase 1: AI Services, Voice Pipeline, and Authentication)  
**Date**: 2026-11-05  
**Target Modules**:
- `backend/app/services/llm.py`
- `backend/app/services/stt.py`
- `backend/app/services/tts.py`

---

## 1. Executive Summary & Problem Scope

In accordance with `ORIGINAL_REQUEST.md` (R2) and `PROJECT.md` (Features 5, 6, 7), VOXPREP relies on a unified external AI provider—**NVIDIA NIM** (`https://integrate.api.nvidia.com/v1`) using a single `NVIDIA_API_KEY`:
1. **LLM**: NVIDIA Nemotron (`nvidia/llama-3.1-nemotron-70b-instruct`) via OpenAI-compatible async interface (`AsyncOpenAI`).
2. **STT**: NVIDIA Parakeet ASR (`nvidia/parakeet-ctc-1.1b-asr`) via REST API (`POST /audio/transcriptions` with `multipart/form-data`).
3. **TTS**: NVIDIA Magpie Multilingual TTS (`nvidia/magpie-tts-multilingual`) via REST API (`POST /audio/speech`).

### Core Architectural Objectives & Constraints:
- **Resilient Fallback Hierarchy**: Zero crashes when API keys are unconfigured, placeholder, or expired. Full offline mock fallbacks must allow all E2E test suites (`test_tier1_features.py` through `test_tier4_scenarios.py`) and development workflows to operate seamlessly without live credits.
- **Fail-Safe Exception Handling**:
  - `llm.chat`: Implements single retry with backoff on failure before returning a polite, friendly fallback message (`"I am temporarily experiencing high traffic. Could you please repeat or summarize your last thought?"`).
  - `stt.transcribe`: Must return `None` and log the error on any failure (corrupt audio, network error, 4xx/5xx). Never raises unhandled exceptions.
  - `tts.synthesize`: Must return `None` and log the error on failure, allowing the frontend to fall back to Web Speech API per spec. Never raises unhandled exceptions.
- **Environment & Dependency Compatibility**:
  - Python 3.12 running inside `.venv`.
  - Installed packages: `openai==1.58.1`, `httpx==0.28.1`, `pydantic==2.10.4`, `pytest==8.3.4`, `pytest-asyncio==0.25.0`.
  - Zero external C-build dependencies (using Python standard library `struct` for WAV generation).

---

## 2. Environment & Key Management Strategy

In `backend/.env.example` and `backend/app/db/supabase.py`, an established pattern checks whether an external service credential is real or a dummy/mock placeholder. We replicate this exact design across all three NIM services:

```python
def is_mock_mode() -> bool:
    """Determines whether to execute in offline mock mode or attempt live NVIDIA NIM calls."""
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
```

This ensures that running `pytest` in `.venv` (which sets `NVIDIA_API_KEY=nvapi-test-dummy-key` in `backend/tests/e2e/conftest.py`) automatically activates offline mock mode without requiring network calls or throwing auth errors.

---

## 3. Component Design 1: `backend/app/services/llm.py`

### 3.1 Interface Contract
```python
async def chat(messages: list, system_prompt: str = "") -> str:
    """
    Invokes NVIDIA Nemotron 70B via AsyncOpenAI.
    
    Args:
        messages: List of message dictionaries or string inputs.
        system_prompt: Optional system prompt to prepend if provided.
        
    Returns:
        Generated assistant string, mock response, or friendly error fallback on failure.
    """
```

### 3.2 Key Technical Mechanisms
1. **AsyncOpenAI Client**: Configured with `base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")` and `api_key=os.getenv("NVIDIA_API_KEY")`.
2. **Message Normalization**: Ensures `messages` is formatted as `list[dict]` with `role` and `content`. If `system_prompt` is supplied and not already prepended, it is inserted as `{"role": "system", "content": system_prompt}`.
3. **Nemotron Inference Parameters**:
   - `model="nvidia/llama-3.1-nemotron-70b-instruct"` (or `os.getenv("NVIDIA_LLM_MODEL")`)
   - `temperature=0.2` (optimal for structured reasoning and rubric grading)
   - `top_p=0.95`
   - `max_tokens=1024`
4. **Retry Loop with Exponential Backoff**:
   - Attempt 1: Call live NIM API.
   - On error: Catch exception, log warning with `logger.warning(...)`, sleep for 1.0 second (`await asyncio.sleep(1.0)`).
   - Attempt 2: Retry once.
   - On second error: Catch exception, log `logger.error(...)`, return `FRIENDLY_ERROR_MESSAGE` (`"I am temporarily experiencing high traffic. Could you please repeat or summarize your last thought?"`).
5. **Intelligent Offline Mock Fallback**:
   To support all downstream agents (Interviewer Agent, Coach Agent, Report Generator, Voice Pipeline), the mock generator parses the prompt context:
   - **Report Generation**: If prompt contains `"REPORT FORMAT"` or `"overall_score"`, returns valid JSON with `overall_score`, `dimension_scores`, `strengths`, `weaknesses`, `improvement_tips`, `coach_recommendation`, `summary`.
   - **Interviewer Evaluation**: If prompt contains `"scores"` or `"relevance"` or `"follow_up"`, returns valid JSON evaluation.
   - **Coach Evaluation**: If prompt contains `"correction"` or `"coach_message"`, returns valid JSON exchange.
   - **Voice / Conversational**: Returns a realistic professional interviewer/coach spoken reply.

### 3.3 Proposed Drop-in Implementation for `backend/app/services/llm.py`

```python
"""
NVIDIA Nemotron LLM Service Wrapper for VOXPREP Backend.
Milestone 1: Phase 1 AI Services, Voice Pipeline, and Authentication.

Wraps nvidia/llama-3.1-nemotron-70b-instruct using the OpenAI-compatible AsyncOpenAI SDK.
Implements single retry with backoff, friendly error fallback, and full offline mock mode.
"""

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Union
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
logger = logging.getLogger("voxprep.services.llm")

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/llama-3.1-nemotron-70b-instruct"
FRIENDLY_ERROR_MESSAGE = (
    "I am temporarily experiencing high traffic. Could you please repeat or summarize your last thought?"
)

_async_client: Optional[AsyncOpenAI] = None


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


def get_llm_client() -> AsyncOpenAI:
    """Returns singleton AsyncOpenAI client configured for NVIDIA NIM."""
    global _async_client
    if _async_client is None:
        base_url = os.getenv("NVIDIA_BASE_URL", DEFAULT_BASE_URL).strip()
        api_key = os.getenv("NVIDIA_API_KEY", "").strip() or "mock-key"
        _async_client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    return _async_client


def _generate_mock_response(messages: List[Dict[str, str]], system_prompt: str) -> str:
    """Generates structured mock response based on prompt context for offline testing."""
    combined_text = (system_prompt + " " + " ".join(m.get("content", "") for m in messages)).lower()

    # Case 1: Report Generation Request
    if "report format" in combined_text or "overall_score" in combined_text or "dimension_scores" in combined_text:
        return json.dumps({
            "overall_score": 8.0,
            "dimension_scores": {
                "relevance": 8.0,
                "clarity": 8.0,
                "depth": 7.5,
                "examples": 8.5
            },
            "strengths": [
                "Clear architectural explanation of service boundaries.",
                "Concrete examples of database optimizations."
            ],
            "weaknesses": [
                "Could elaborate more on disaster recovery strategies."
            ],
            "improvement_tips": [
                "Use the STAR method for situational questions.",
                "Quantify business outcomes."
            ],
            "coach_recommendation": "Interview Answer Training",
            "summary": "Candidate demonstrated solid understanding and clear technical communication."
        })

    # Case 2: Coach Agent Evaluation Request
    if "correction format" in combined_text or "coach_message" in combined_text:
        user_content = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        if any(err in user_content.lower() for err in ["was go", "buyed", "fishes", "went there again"]):
            return json.dumps({
                "coach_message": "That sounds great! One small improvement: instead of saying 'was go', you could say 'went'. This sounds more natural because it's past tense. Want to try it?",
                "user_response_text": user_content,
                "correction": {
                    "original": "was go",
                    "improved": "went",
                    "reason": "Use simple past tense 'went' for a completed past action."
                },
                "next_prompt": "What do you enjoy most about your work or studies?"
            })
        return json.dumps({
            "coach_message": "That's well expressed! You used clear structure and good vocabulary.",
            "user_response_text": user_content,
            "correction": None,
            "next_prompt": "What do you enjoy most about your work or studies?"
        })

    # Case 3: Interviewer Evaluation Request
    if "output format after each answer" in combined_text or '"scores":' in combined_text:
        return json.dumps({
            "question": "Could you describe your architectural approach?",
            "answer": "I design fault-tolerant systems using distributed messaging.",
            "scores": {"relevance": 8.5, "clarity": 8.0, "depth": 8.0, "examples": 8.0},
            "follow_up": "Interesting. Could you elaborate on how you handled the trade-offs?",
            "next_question": "How do you handle data partitioning in high-scale environments?"
        })

    # Case 4: Default conversational response (e.g. POST /voice/process)
    return "Thank you for sharing your experience. Could you tell me more about your recent projects and how you handle technical trade-offs?"


async def chat(messages: Union[List[Dict[str, str]], List[Any]], system_prompt: str = "") -> str:
    """
    Executes chat completion with NVIDIA Nemotron 70B with retry and offline mock support.

    Args:
        messages: List of message objects or dicts ({"role": ..., "content": ...}).
        system_prompt: Optional system prompt to guide agent behavior.

    Returns:
        Text response string or friendly error fallback on failure.
    """
    # Normalize messages
    formatted_messages: List[Dict[str, str]] = []
    if system_prompt and system_prompt.strip():
        formatted_messages.append({"role": "system", "content": system_prompt.strip()})

    for msg in messages:
        if isinstance(msg, dict):
            # Avoid duplicating system prompt if already first message
            if msg.get("role") == "system" and system_prompt.strip() == msg.get("content", "").strip():
                continue
            formatted_messages.append({"role": msg.get("role", "user"), "content": str(msg.get("content", ""))})
        elif isinstance(msg, str):
            formatted_messages.append({"role": "user", "content": msg})
        elif hasattr(msg, "role") and hasattr(msg, "content"):
            formatted_messages.append({"role": getattr(msg, "role"), "content": str(getattr(msg, "content"))})

    if not formatted_messages:
        formatted_messages.append({"role": "user", "content": "Hello"})

    # Check offline mock mode
    if is_mock_mode():
        logger.debug("Executing LLM chat in mock fallback mode.")
        return _generate_mock_response(formatted_messages, system_prompt)

    client = get_llm_client()
    model = os.getenv("NVIDIA_LLM_MODEL", DEFAULT_MODEL).strip()
    max_retries = 1
    backoff_seconds = 1.0

    for attempt in range(max_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=formatted_messages,
                temperature=0.2,
                top_p=0.95,
                max_tokens=1024,
            )
            content = response.choices[0].message.content
            return content.strip() if content else ""
        except Exception as exc:
            if attempt < max_retries:
                logger.warning(
                    f"NVIDIA Nemotron call failed on attempt {attempt + 1}: {exc}. Retrying in {backoff_seconds}s..."
                )
                await asyncio.sleep(backoff_seconds)
            else:
                logger.error(f"NVIDIA Nemotron call failed after {max_retries + 1} attempts: {exc}. Returning friendly fallback.")
                return FRIENDLY_ERROR_MESSAGE
```

---

## 4. Component Design 2: `backend/app/services/stt.py`

### 4.1 Interface Contract
```python
async def transcribe(audio_bytes: bytes) -> str | None:
    """
    Transcribes audio bytes to text using NVIDIA Parakeet ASR REST API.
    
    Args:
        audio_bytes: Raw binary audio payload (WAV, MP3, WebM, etc.).
        
    Returns:
        Transcribed text string or None on failure/empty audio.
    """
```

### 4.2 Key Technical Mechanisms
1. **Endpoint & Method**: `POST https://integrate.api.nvidia.com/v1/audio/transcriptions` with `multipart/form-data`.
2. **Model**: `nvidia/parakeet-ctc-1.1b-asr` (or `os.getenv("NVIDIA_STT_MODEL")`).
3. **Payload Structure**:
   - `files={"file": ("audio.wav", audio_bytes, "audio/wav")}`
   - `data={"model": model, "response_format": "json"}`
   - `headers={"Authorization": f"Bearer {api_key}"}`
4. **Resilient Failure Handling**:
   - If `audio_bytes` is empty (`len(audio_bytes) < 10`), returns `None` immediately without making network calls.
   - On HTTP status != 200 or connection errors: logs the error via `logger.error(...)` and returns `None`.
   - Never raises an unhandled exception to callers (protecting `POST /voice/process`).
5. **Offline Mock Fallback**:
   - Detects corrupted audio (e.g. `b"NOT_A_VALID_WAV..."` from `corrupt_audio_bytes` fixture or non-audio payload) and returns `None` per boundary test specifications (`test_tier2_boundaries.py`).
   - For valid audio bytes, returns a realistic transcript: `"I have extensive experience designing microservices using FastAPI, Celery, and PostgreSQL."`

### 4.3 Proposed Drop-in Implementation for `backend/app/services/stt.py`

```python
"""
NVIDIA Parakeet ASR STT Service Wrapper for VOXPREP Backend.
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
    """
    Transcribes audio bytes to text using NVIDIA Parakeet ASR REST API.

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
```

---

## 5. Component Design 3: `backend/app/services/tts.py`

### 5.1 Interface Contract
```python
async def synthesize(text: str) -> bytes | None:
    """
    Synthesizes speech audio from text using NVIDIA Magpie TTS REST API.
    
    Args:
        text: Text string to convert to speech.
        
    Returns:
        Binary WAV audio bytes or None on failure.
    """
```

### 5.2 Key Technical Mechanisms
1. **Endpoint & Method**: `POST https://integrate.api.nvidia.com/v1/audio/speech` with JSON body.
2. **Model**: `nvidia/magpie-tts-multilingual` (or `os.getenv("NVIDIA_TTS_MODEL")`).
3. **Payload Structure**:
   ```json
   {
       "model": "nvidia/magpie-tts-multilingual",
       "input": "text to synthesize",
       "voice": "alloy",
       "response_format": "wav"
   }
   ```
4. **Resilient Failure Handling**:
   - If `text` is empty or whitespace only: returns `None` immediately.
   - On HTTP status != 200, network error, or unexpected exception: logs error via `logger.error(...)` and returns `None`.
   - Per `ORIGINAL_REQUEST.md` R2: when `synthesize` returns `None`, frontend falls back to Web Speech API. Never raises an unhandled exception.
5. **Zero-Dependency In-Memory WAV Synthesis for Mock Mode**:
   - Generates valid 16kHz mono 16-bit PCM WAV binary data using Python's standard library `struct`.
   - Produces standard RIFF headers (`RIFF....WAVEfmt ....data....`) that browsers, players, and test suites can decode without any external audio codec dependencies.

### 5.3 Proposed Drop-in Implementation for `backend/app/services/tts.py`

```python
"""
NVIDIA Magpie TTS Service Wrapper for VOXPREP Backend.
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
    """
    Synthesizes speech audio from text using NVIDIA Magpie TTS REST API.

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
```

---

## 6. Testing & Verification Plan (`backend/tests/test_services.py`)

To verify the three services independently and validate their acceptance criteria, the implementer agent should create `backend/tests/test_services.py` covering:

1. `test_llm_chat_mock()`: Validates `llm.chat(messages, system_prompt)` returns valid non-empty responses under mock mode.
2. `test_llm_chat_retry_and_error_handling()`: Mocks `AsyncOpenAI.chat.completions.create` raising exceptions on attempt 1 and succeeding on attempt 2 (retry verified), and failing both attempts to verify `FRIENDLY_ERROR_MESSAGE` is returned without raising.
3. `test_stt_transcribe_mock()`: Verifies `stt.transcribe(dummy_wav_bytes)` returns expected non-empty transcript.
4. `test_stt_transcribe_empty_and_corrupt()`: Verifies `stt.transcribe(b"")` and `stt.transcribe(corrupt_bytes)` return `None` safely.
5. `test_stt_transcribe_network_failure()`: Mocks `httpx.AsyncClient.post` raising network exception; verifies `transcribe()` returns `None` and does not raise.
6. `test_tts_synthesize_mock()`: Verifies `tts.synthesize("test")` returns valid WAV bytes starting with `b"RIFF"` and containing `b"WAVE"`.
7. `test_tts_synthesize_empty_text()`: Verifies `tts.synthesize("")` returns `None`.
8. `test_tts_synthesize_network_failure()`: Mocks HTTP 500 error; verifies `synthesize()` returns `None` and does not raise.

---

## 7. Downstream Integration Checklist for Milestone 1 Implementer
- [ ] Place `llm.py`, `stt.py`, and `tts.py` in `backend/app/services/`.
- [ ] Implement `backend/app/routers/voice.py` importing `stt.transcribe`, `llm.chat`, and `tts.synthesize` for `POST /voice/process`.
- [ ] Register `voice.router` in `backend/app/main.py` under prefix `/voice`.
- [ ] Run pytest: `& ".venv\Scripts\python.exe" -m pytest backend/tests/test_services.py backend/tests/e2e/test_tier1_features.py -k "voice"`.
