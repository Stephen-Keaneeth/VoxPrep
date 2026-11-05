# NVIDIA NIM Services & External Integration Survey Report

**Project:** VOXPREP Backend MVP  
**Investigator:** `explorer_survey_2`  
**Date:** 2026-11-05  
**Scope:** NVIDIA NIM APIs (Nemotron LLM, Parakeet STT, Magpie TTS), Supabase Client & Auth SDK, Testing & Mock Strategy, and Phase 1 curl Reference.

---

## 1. Executive Summary

VOXPREP utilizes a unified AI architecture powered by **NVIDIA NIM** (NVIDIA Inference Microservice) APIs under a single `NVIDIA_API_KEY`. This provides high-performance conversational AI, automatic speech recognition (ASR), and expressive multilingual speech synthesis (TTS) suitable for hackathon rapid prototyping and production deployment.

### Key Service Matrix

| Service | Target Capability | Model Identifier | Base URL / Endpoint | Protocol / SDK | Fallback Strategy |
|---|---|---|---|---|---|
| **LLM** | Conversational reasoning, rubric evaluation, report generation | `nvidia/llama-3.1-nemotron-70b-instruct` | `https://integrate.api.nvidia.com/v1` (`/chat/completions`) | `openai.AsyncOpenAI` | 1 automatic retry on failure -> friendly error text |
| **STT** | Voice answer transcription | `nvidia/parakeet-ctc-1.1b-asr` (or `nvidia/parakeet-tdt-0.6b-v3`) | `https://integrate.api.nvidia.com/v1/audio/transcriptions` | HTTP POST `multipart/form-data` (`httpx`) | Return `None` -> log error -> prompt user to repeat |
| **TTS** | Voice synthesis for interviewer & coach | `nvidia/magpie-tts-multilingual` | `https://integrate.api.nvidia.com/v1/audio/speech` | HTTP POST `multipart/form-data` / JSON (`httpx`) | Return `None` -> frontend Web Speech API fallback |
| **Database & Auth** | Persistence & user session authentication | PostgreSQL + GoTrue Auth | `SUPABASE_URL` | `supabase-py` (`create_client`) | Singleton pattern, structured HTTP 400/401/500 errors |

---

## 2. NVIDIA Nemotron LLM Integration (`services/llm.py`)

### 2.1 Specification & Configuration
- **Model:** `nvidia/llama-3.1-nemotron-70b-instruct`
- **Base URL:** `https://integrate.api.nvidia.com/v1`
- **Authentication:** `Authorization: Bearer $NVIDIA_API_KEY`
- **Client Library:** `openai.AsyncOpenAI` (OpenAI Python SDK >= 1.0)
- **Role in VOXPREP:**
  - Agent 1: Conducts HR/Technical interview question loop, evaluates answers on 4-dimension rubric (Relevance, Clarity, Depth, Examples 1–10), generates post-interview analytical reports.
  - Agent 2: Acts as communication coach across 3 modes (Conversation, Answer Training, English Improvement), providing gentle 1–2 corrections per exchange.

### 2.2 Recommended Architecture & Retry Mechanism
Per requirements, `services/llm.py` must expose:
`async def chat(messages: list[dict], system_prompt: str = "") -> str`

**Resilience Contract:**
1. If `system_prompt` is provided and not already in `messages`, inject as `{"role": "system", "content": system_prompt}` at the beginning.
2. Call `await client.chat.completions.create(...)` with:
   - `model="nvidia/llama-3.1-nemotron-70b-instruct"`
   - `temperature=0.6` (balanced between creative conversational flow and deterministic rubric evaluation)
   - `max_tokens=1024`
   - `top_p=0.95`
3. **Single Retry on Failure:** Wrap call in a loop (`range(2)`).
   - If attempt 0 fails (timeout, rate limit 429, 5xx server error), catch exception, log warning, wait 1.0 second (`asyncio.sleep(1)`), and retry once.
   - If attempt 1 fails, log error and return a graceful friendly message:
     `"I apologize, but I am experiencing connection difficulties right now. Please try your response again in a moment."`
   - Never let unhandled API exceptions crash the FastAPI worker or bubble up unformatted to the frontend.

### 2.3 Reference Implementation Pattern (`services/llm.py`)

```python
import os
import asyncio
import logging
from openai import AsyncOpenAI

logger = logging.getLogger("voxprep.llm")

# Initialize client lazily or globally
_client: AsyncOpenAI | None = None

def get_llm_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("NVIDIA_API_KEY", "")
        _client = AsyncOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key or "mock-key",
        )
    return _client

async def chat(messages: list[dict], system_prompt: str = "") -> str:
    client = get_llm_client()
    
    formatted_messages = []
    if system_prompt:
        formatted_messages.append({"role": "system", "content": system_prompt})
    formatted_messages.extend(messages)
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model="nvidia/llama-3.1-nemotron-70b-instruct",
                messages=formatted_messages,
                temperature=0.6,
                max_tokens=1024,
            )
            content = response.choices[0].message.content
            return content or ""
        except Exception as e:
            if attempt == 0:
                logger.warning(f"LLM call attempt 1 failed: {e}. Retrying in 1s...")
                await asyncio.sleep(1.0)
                continue
            logger.error(f"LLM call failed after retry: {e}")
            return (
                "I apologize, but I am having trouble connecting right now. "
                "Please try again in a moment."
            )
```

---

## 3. NVIDIA Parakeet STT (ASR) Integration (`services/stt.py`)

### 3.1 Endpoint & Specification
- **Endpoint URL:** `https://integrate.api.nvidia.com/v1/audio/transcriptions`
- **Model Identifier:** `nvidia/parakeet-ctc-1.1b-asr` (also supports `nvidia/parakeet-tdt-0.6b-v3`)
- **HTTP Method:** `POST`
- **Request Format:** `multipart/form-data`
- **Headers:**
  - `Authorization: Bearer <NVIDIA_API_KEY>`
  - `Accept: application/json`
- **Form Fields:**
  - `file`: binary audio data with filename (e.g. `("audio.wav", audio_bytes, "audio/wav")` or `"audio/webm"`)
  - `model`: `"nvidia/parakeet-ctc-1.1b-asr"`
  - `language`: `"en-US"` (optional, defaults to English)
  - `response_format`: `"json"`
- **Response Structure (200 OK):**
  ```json
  {
    "text": "Hello, my name is Alex and I am applying for the full stack engineer role."
  }
  ```

### 3.2 Failure Handling & Browser Audio Compatibility
- **Browser Audio Format:** Modern browsers record via `MediaRecorder` producing `audio/webm;codecs=opus` or `audio/ogg;codecs=opus` on Chrome/Firefox and `audio/mp4` on Safari. The NVIDIA NIM endpoint accepts WAV, MP3, FLAC, WebM, and OGG containers.
- **Resilience Contract:**
  - Function signature: `async def transcribe(audio_bytes: bytes, filename: str = "audio.wav") -> str | None`
  - In case of network timeout, HTTP 4xx/5xx errors, empty audio bytes, or unparseable audio:
    - Log error details (`logger.error(...)`).
    - Return `None` immediately.
    - Do NOT raise unhandled exceptions.

### 3.3 Reference Implementation Pattern (`services/stt.py`)

```python
import os
import logging
import httpx

logger = logging.getLogger("voxprep.stt")

STT_ENDPOINT = "https://integrate.api.nvidia.com/v1/audio/transcriptions"
MODEL_NAME = "nvidia/parakeet-ctc-1.1b-asr"

async def transcribe(audio_bytes: bytes, filename: str = "audio.wav") -> str | None:
    if not audio_bytes:
        logger.warning("Empty audio bytes received for transcription")
        return None

    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        logger.error("NVIDIA_API_KEY environment variable is not configured")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    
    files = {
        "file": (filename, audio_bytes, "audio/wav")
    }
    data = {
        "model": MODEL_NAME,
        "language": "en-US",
        "response_format": "json"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                STT_ENDPOINT,
                headers=headers,
                files=files,
                data=data
            )
            
            if response.status_code == 200:
                result = response.json()
                transcript = result.get("text", "").strip()
                return transcript if transcript else None
            else:
                logger.error(
                    f"Parakeet STT failed: HTTP {response.status_code} - {response.text}"
                )
                return None
    except Exception as e:
        logger.error(f"Exception during Parakeet STT transcription: {e}")
        return None
```

---

## 4. NVIDIA Magpie TTS Integration (`services/tts.py`)

### 4.1 Endpoint & Specification
- **Endpoint URL:** `https://integrate.api.nvidia.com/v1/audio/speech`
- **Model Identifier:** `nvidia/magpie-tts-multilingual`
- **HTTP Method:** `POST`
- **Request Format:** `multipart/form-data` or JSON payload:
  - Form Fields:
    - `text`: Input text to synthesize (e.g. `"Welcome to VOXPREP. Let's begin."`)
    - `voice`: `Magpie-Multilingual.EN-US.Aria` (or `Magpie-Multilingual.EN-US.Sofia`, `Magpie-Multilingual.EN-US.Jason`)
    - `model`: `nvidia/magpie-tts-multilingual`
    - `language`: `en-US`
    - `encoding`: `LINEAR_PCM` (or default container)
    - `sample_rate_hz`: `22050` (or `44100`)
- **Headers:**
  - `Authorization: Bearer <NVIDIA_API_KEY>`
- **Response Structure (200 OK):**
  - Content-Type: `audio/wav` or `application/octet-stream`
  - Body: Binary audio bytes representing the generated waveform.

### 4.2 Failure Handling & Web Speech API Fallback
- **Resilience Contract:**
  - Function signature: `async def synthesize(text: str, voice: str = "Magpie-Multilingual.EN-US.Aria") -> bytes | None`
  - In case of:
    - Empty or whitespace text input -> return `None`
    - API quota exceeded / HTTP 429 / 401 / 500 -> log error and return `None`
    - Network timeout -> log error and return `None`
- **Frontend Fallback Role:**
  - When the backend returns HTTP 200 with text but `null`/empty audio bytes (or headers indicate fallback), frontend immediately activates browser-native `window.speechSynthesis.speak(new SpeechSynthesisUtterance(text))`.
  - This ensures 100% demo resilience during live hackathon presentations even if NVIDIA credits are exhausted.

### 4.3 Reference Implementation Pattern (`services/tts.py`)

```python
import os
import logging
import httpx

logger = logging.getLogger("voxprep.tts")

TTS_ENDPOINT = "https://integrate.api.nvidia.com/v1/audio/speech"
DEFAULT_VOICE = "Magpie-Multilingual.EN-US.Aria"
MODEL_NAME = "nvidia/magpie-tts-multilingual"

async def synthesize(text: str, voice: str = DEFAULT_VOICE) -> bytes | None:
    if not text or not text.strip():
        logger.warning("Empty text received for synthesis")
        return None

    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        logger.error("NVIDIA_API_KEY environment variable is not configured")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    
    # NVIDIA NIM supports multipart/form-data for speech synthesis
    data = {
        "text": text.strip(),
        "voice": voice,
        "language": "en-US",
        "model": MODEL_NAME,
        "encoding": "LINEAR_PCM",
        "sample_rate_hz": "22050",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                TTS_ENDPOINT,
                headers=headers,
                data=data
            )
            
            if response.status_code == 200 and response.content:
                return response.content
            else:
                logger.error(
                    f"Magpie TTS failed: HTTP {response.status_code} - {response.text}"
                )
                return None
    except Exception as e:
        logger.error(f"Exception during Magpie TTS synthesis: {e}")
        return None
```

---

## 5. Voice Pipeline Router (`routers/voice.py`)

### 5.1 Endpoint Specification: `POST /voice/process`
- **Purpose:** Full voice loop execution in a single request: audio upload -> STT -> LLM response -> TTS audio output.
- **Request:**
  - `Content-Type: multipart/form-data`
  - Form Fields:
    - `audio`: Uploaded audio file (binary)
    - `session_id`: Optional session string
    - `context`: Optional system prompt / agent role context
- **Response Modes:**
  1. **Success with Audio:** Returns `audio/wav` response with custom response headers:
     - `X-Transcript`: Base64 encoded or sanitized transcript string
     - `X-Response-Text`: Base64 encoded or sanitized LLM reply text
  2. **Fallback Mode (TTS failed or skipped):** Returns JSON or fallback headers allowing frontend to play via Web Speech API:
     ```json
     {
       "transcript": "Hello, tell me about your background.",
       "text_response": "Thank you for joining. Let's begin with your recent projects.",
       "audio_available": false
     }
     ```

### 5.2 Reference Implementation Pattern (`routers/voice.py`)

```python
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from app.services.stt import transcribe
from app.services.llm import chat
from app.services.tts import synthesize
import urllib.parse
import logging

router = APIRouter(prefix="/voice", tags=["Voice"])
logger = logging.getLogger("voxprep.voice")

@router.post("/process")
async def process_voice(
    audio: UploadFile = File(...),
    system_prompt: str = Form(default="You are VOXPREP, a helpful AI interviewer.")
):
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file uploaded")

    # Step 1: STT
    transcript = await transcribe(audio_bytes, filename=audio.filename or "audio.wav")
    if not transcript:
        raise HTTPException(
            status_code=422,
            detail="Speech recognition failed. Please speak clearly and try again."
        )

    # Step 2: LLM
    llm_response = await chat(
        messages=[{"role": "user", "content": transcript}],
        system_prompt=system_prompt
    )

    # Step 3: TTS
    audio_out = await synthesize(llm_response)
    
    if audio_out:
        # Return audio stream with transcript in headers
        headers = {
            "X-Transcript": urllib.parse.quote(transcript),
            "X-Response-Text": urllib.parse.quote(llm_response),
        }
        return Response(content=audio_out, media_type="audio/wav", headers=headers)
    else:
        # Fallback to JSON indicating TTS was unavailable
        return {
            "transcript": transcript,
            "response_text": llm_response,
            "audio_available": False,
            "message": "Audio synthesis unavailable; use client-side speech synthesis."
        }
```

---

## 6. Supabase Integration (`db/supabase.py` & `routers/auth.py`)

### 6.1 Supabase Client Singleton (`db/supabase.py`)
Supabase Python SDK (`supabase>=2.0.0`) utilizes `create_client(supabase_url, supabase_key)`.
- Use a thread-safe singleton.
- Prioritize `SUPABASE_SERVICE_KEY` (service role key for backend operations bypassing RLS) or fall back to `SUPABASE_KEY` / `SUPABASE_ANON_KEY`.

```python
import os
import logging
from supabase import create_client, Client

logger = logging.getLogger("voxprep.db")

_supabase_client: Client | None = None

def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError(
                "Supabase configuration missing: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set."
            )
        _supabase_client = create_client(url, key)
    return _supabase_client
```

### 6.2 Supabase Auth SDK Operations (`routers/auth.py`)
`supabase-py` v2 uses snake_case methods that raise exceptions on failure (unlike JS client `{ data, error }`).

#### Register (`POST /auth/register`):
```python
@router.post("/register")
async def register(payload: AuthSchema):
    supabase = get_supabase()
    try:
        auth_response = supabase.auth.sign_up({
            "email": payload.email,
            "password": payload.password
        })
        user = auth_response.user
        if not user:
            raise HTTPException(status_code=400, detail="Registration failed")
            
        # Initialize default user record in public.users table
        supabase.table("users").upsert({
            "id": user.id,
            "email": user.email,
            "name": payload.name or user.email.split("@")[0],
            "communication_profile": {
                "skill_level": "intermediate",
                "weak_areas": [],
                "strong_areas": [],
                "sessions_count": 0
            }
        }).execute()

        return {
            "status": "success",
            "user_id": user.id,
            "email": user.email,
            "message": "User registered successfully."
        }
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
```

#### Login (`POST /auth/login`):
```python
@router.post("/login")
async def login(payload: AuthSchema):
    supabase = get_supabase()
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
        })
        session = auth_response.session
        user = auth_response.user
        if not session or not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
        return {
            "access_token": session.access_token,
            "token_type": "bearer",
            "user_id": user.id,
            "email": user.email
        }
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=401, detail="Invalid email or password")
```

### 6.3 Database Table Operations Pattern
- **Insert:** `supabase.table("interview_sessions").insert(record_dict).execute()`
- **Select:** `res = supabase.table("interview_sessions").select("*").eq("id", session_id).execute(); data = res.data`
- **Update:** `supabase.table("interview_sessions").update(update_dict).eq("id", session_id).execute()`
- Always inspect `res.data` for empty list `[]` to trigger HTTP 404 if record is not found.

---

## 7. Testing Strategy: Unit, Integration & Mock Fallbacks

To ensure tests execute reliably in all environments (local development, CI pipelines without secrets, and live integration environments), we use a **layered testing approach**:

### 7.1 Architecture for Mocking External Services
1. **Mocking AsyncOpenAI (Nemotron LLM):**
   - Mock `client.chat.completions.create` to return an object mimicking `ChatCompletion` with `choices[0].message.content`.
   - Test both success and failure retry behavior (first call raises `APIConnectionError`, second succeeds, or both fail).
2. **Mocking httpx (Parakeet STT & Magpie TTS):**
   - Use `pytest-mock` (`mocker.patch("httpx.AsyncClient.post")`) or `unittest.mock.patch`.
   - STT Mock: Returns HTTP 200 with `{"text": "Sample transcription"}` or HTTP 500 to assert `transcribe(...) is None`.
   - TTS Mock: Returns HTTP 200 with `b"RIFF....WAVE"` or HTTP 500 to assert `synthesize(...) is None`.
3. **Mocking Supabase Client:**
   - Create a mock Supabase fixture returning simulated auth user/session and fluent query builder (`.table().insert().execute()`).
   - Test `POST /auth/register` and `POST /auth/login` completely in-memory without reaching Supabase cloud.

### 7.2 Sample Pytest Fixture Structure (`tests/conftest.py`)

```python
import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_nvidia_llm(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="Hello candidate! Let us begin."))]
    
    mock_create = AsyncMock(return_value=mock_resp)
    monkeypatch.setattr("openai.resources.chat.AsyncCompletions.create", mock_create)
    return mock_create

@pytest.fixture
def mock_nvidia_stt(monkeypatch):
    async def mock_transcribe(audio_bytes, filename="audio.wav"):
        return "I have five years of experience building Python APIs."
    monkeypatch.setattr("app.services.stt.transcribe", mock_transcribe)

@pytest.fixture
def mock_nvidia_tts(monkeypatch):
    async def mock_synthesize(text, voice=""):
        return b"RIFFMOCKWAVEAUDIOBYTES"
    monkeypatch.setattr("app.services.tts.synthesize", mock_synthesize)
```

### 7.3 Conditional Live Integration Tests
For developers with active API keys, tests can be marked with:
```python
import os
import pytest

requires_nvidia = pytest.mark.skipif(
    not os.getenv("NVIDIA_API_KEY"),
    reason="NVIDIA_API_KEY required for live test"
)

@requires_nvidia
@pytest.mark.asyncio
async def test_live_nemotron_llm():
    from app.services.llm import chat
    response = await chat([{"role": "user", "content": "Reply with 'OK'"}])
    assert "OK" in response
```

---

## 8. Sample cURL Command Cookbook for Phase 1

### 8.1 Backend Endpoint cURL Commands

#### 1. Backend Health Ping (`GET /health`)
```bash
curl -X GET http://localhost:8000/health \
  -H "Accept: application/json"
```
**Expected Response:**
```json
{"status": "ok"}
```

#### 2. User Registration (`POST /auth/register`)
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testcandidate@example.com",
    "password": "SecurePassword123!",
    "name": "Alex Candidate"
  }'
```
**Expected Response (200 OK):**
```json
{
  "status": "success",
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "email": "testcandidate@example.com",
  "message": "User registered successfully."
}
```

#### 3. User Login (`POST /auth/login`)
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testcandidate@example.com",
    "password": "SecurePassword123!"
  }'
```
**Expected Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "email": "testcandidate@example.com"
}
```

#### 4. Voice Processing Pipeline (`POST /voice/process`)
```bash
curl -X POST http://localhost:8000/voice/process \
  -F "audio=@sample_answer.wav;type=audio/wav" \
  -F "system_prompt=You are VOXPREP AI Interviewer conducting a Technical Interview." \
  --output response_audio.wav \
  -i
```
**Expected Output:**
- HTTP status 200 with binary WAV audio written to `response_audio.wav`.
- Inspect response headers for `-i` to view `X-Transcript` and `X-Response-Text`.

---

### 8.2 Direct NVIDIA NIM Endpoints cURL Commands

#### 1. Direct Nemotron LLM Completion
```bash
curl -X POST "https://integrate.api.nvidia.com/v1/chat/completions" \
  -H "Authorization: Bearer $NVIDIA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nvidia/llama-3.1-nemotron-70b-instruct",
    "messages": [
      {"role": "system", "content": "You are a concise interviewer."},
      {"role": "user", "content": "Introduce yourself in one sentence."}
    ],
    "temperature": 0.5,
    "max_tokens": 128
  }'
```

#### 2. Direct Parakeet STT Transcription
```bash
curl -X POST "https://integrate.api.nvidia.com/v1/audio/transcriptions" \
  -H "Authorization: Bearer $NVIDIA_API_KEY" \
  -H "Accept: application/json" \
  -F "file=@sample_speech.wav;type=audio/wav" \
  -F "model=nvidia/parakeet-ctc-1.1b-asr" \
  -F "language=en-US" \
  -F "response_format=json"
```

#### 3. Direct Magpie TTS Synthesis
```bash
curl -X POST "https://integrate.api.nvidia.com/v1/audio/speech" \
  -H "Authorization: Bearer $NVIDIA_API_KEY" \
  -F "text=Hello and welcome to VOXPREP. Let us start your interview practice." \
  -F "voice=Magpie-Multilingual.EN-US.Aria" \
  -F "model=nvidia/magpie-tts-multilingual" \
  -F "language=en-US" \
  -F "encoding=LINEAR_PCM" \
  -F "sample_rate_hz=22050" \
  --output magpie_output.wav
```

---

## 9. Recommendations for Milestone Implementation

1. **Keep Service Wrappers Independent:**
   Each service file (`services/llm.py`, `services/stt.py`, `services/tts.py`) should be modular, independently importable, and fail-safe.
2. **Defensive Error Handling:**
   - Any external API failure in STT or TTS returns `None` and logs structured details.
   - The LLM service retries once after a 1.0s delay before returning a friendly fallback message.
3. **Environment Configuration:**
   - Document all three keys clearly in `.env.example`:
     ```env
     NVIDIA_API_KEY=nvapi-...
     SUPABASE_URL=https://your-project.supabase.co
     SUPABASE_SERVICE_KEY=eyJhbGci...
     ```
4. **Mock Fixture Library:**
   Provide ready-to-use fixtures in `tests/conftest.py` so downstream test suites for Phase 1, Phase 2, and Phase 3 can run in CI without needing live API tokens.
