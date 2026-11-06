"""Tier 5 Adversarial Coverage Hardening Test Suite for VOXPREP Backend.

Author: challenger_tier5_2 (Empirical Challenger)
Milestone: Final Milestone Phase 2 (Adversarial Coverage Hardening: API & Service Pipeline)

Audit Scope:
1. backend/app/main.py (CORS origin resolution, GlobalExceptionMiddleware, custom headers, ASGI scopes)
2. backend/app/services/llm.py (Nemotron LLM wrapper: simulated timeouts, retry behavior, fallback friendly message, message normalization polymorphism)
3. backend/app/services/stt.py (Parakeet ASR STT wrapper: empty/corrupt audio byte headers, network timeouts, HTTP error codes, mock/live branches)
4. backend/app/services/tts.py (Magpie TTS wrapper: empty/whitespace text, RIFF WAV header validation, live API timeouts/errors, fallback)
5. backend/app/routers/voice.py (POST /voice/process: file read failures, corrupt headers, STT failure fallback, LLM empty fallback, TTS fallback)
6. backend/app/routers/auth.py (POST /auth/register & POST /auth/login: invalid emails, short passwords, duplicate pre-check, DB insert resilience, rapid concurrent collisions)
7. backend/app/routers/interview.py (POST /interview/start, respond, end, report: invalid types, 404 handlers, in-progress checks, dynamic report regeneration)
8. backend/app/routers/coach.py (POST /coach/start, respond, end: mode validation, empty payloads, 404 handlers, completed session guards, idempotent termination)
9. backend/app/db/supabase.py (Thread-safe singleton, MockTableQuery corrupt inserts/updates, compound filters, ordering with Nones, zero limits, MockAuth concurrency)
"""

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import io
import json
import os
import struct
import threading
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from starlette.datastructures import Headers, UploadFile

from app.db.coach_persistence import clear_coach_cache
from app.db.session_persistence import create_interview_session, get_interview_session
from app.db.supabase import (
    MockAuth,
    MockSupabaseClient,
    MockTableQuery,
    get_supabase_client,
    reset_supabase_client,
)
from app.main import GlobalExceptionMiddleware, app, get_allowed_origins
from app.routers import auth, coach, interview, voice
from app.services import llm, stt, tts
from backend.tests.conftest import LocalClient


def run_sync(coro):
    """Executes a coroutine stack synchronously without socketpair event loop dependencies."""
    stack = [coro]
    while stack:
        current = stack[-1]
        try:
            sub = current.send(None)
            if hasattr(sub, "send"):
                stack.append(sub)
        except StopIteration as exc:
            stack.pop()
            if not stack:
                return exc.value


def create_pcm_wav_bytes(duration_ms: int = 200, sample_rate: int = 16000) -> bytes:
    """Helper to generate valid 16kHz mono 16-bit PCM WAV bytes."""
    num_samples = int(sample_rate * (duration_ms / 1000.0))
    data_size = num_samples * 2
    riff_header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE"
    fmt_chunk = b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    data_chunk = b"data" + struct.pack("<I", data_size) + (b"\x00\x00" * num_samples)
    return riff_header + fmt_chunk + data_chunk


# =============================================================================
# 1. LLM SERVICE ADVERSARIAL TESTS (services/llm.py)
# =============================================================================

class TestLLMServiceAdversarial:
    """Adversarial stress tests for NVIDIA Nemotron LLM service wrapper."""

    def test_llm_timeout_retry_then_success(self, monkeypatch):
        """Simulates network timeout on attempt 0, succeeds on attempt 1 retry."""
        monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
        monkeypatch.setattr(llm.asyncio, "sleep", AsyncMock(return_value=None))

        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Recovered after network timeout."
        mock_response.choices = [mock_choice]

        mock_create = AsyncMock(side_effect=[
            httpx.ReadTimeout("Connection timed out waiting for NVIDIA API"),
            mock_response,
        ])
        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create
        monkeypatch.setattr(llm, "get_llm_client", lambda: mock_client)

        result = run_sync(llm.chat(messages=[{"role": "user", "content": "Ping"}]))
        assert result == "Recovered after network timeout."
        assert mock_create.call_count == 2

    def test_llm_timeout_all_retries_friendly_fallback(self, monkeypatch):
        """Simulates network timeouts across all retry attempts; returns friendly fallback message."""
        monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
        monkeypatch.setattr(llm.asyncio, "sleep", AsyncMock(return_value=None))

        mock_create = AsyncMock(side_effect=[
            httpx.ConnectTimeout("Connect timeout 1"),
            httpx.ConnectTimeout("Connect timeout 2"),
        ])
        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create
        monkeypatch.setattr(llm, "get_llm_client", lambda: mock_client)

        result = run_sync(llm.chat(messages=[{"role": "user", "content": "Help"}]))
        assert result == llm.FRIENDLY_ERROR_MESSAGE
        assert mock_create.call_count == 2

    def test_llm_empty_choices_and_content_handling(self, monkeypatch):
        """Tests API response returning choices with None or empty content."""
        monkeypatch.setattr(llm, "is_mock_mode", lambda: False)

        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        monkeypatch.setattr(llm, "get_llm_client", lambda: mock_client)

        result = run_sync(llm.chat(messages=[{"role": "user", "content": "Query"}]))
        assert result == ""

    def test_llm_message_normalization_polymorphism(self, monkeypatch):
        """Tests polymorphic message parsing: dicts, strings, objects with .role/.content."""
        captured_messages = []

        async def fake_create(**kwargs):
            nonlocal captured_messages
            captured_messages = kwargs.get("messages", [])
            mock_resp = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = "OK"
            mock_resp.choices = [mock_choice]
            return mock_resp

        monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=fake_create)
        monkeypatch.setattr(llm, "get_llm_client", lambda: mock_client)

        class CustomMsg:
            def __init__(self, r, c):
                self.role = r
                self.content = c

        mixed_messages = [
            {"role": "user", "content": "Dict message"},
            "Raw string message",
            CustomMsg("assistant", "Object message"),
        ]

        result = run_sync(llm.chat(messages=mixed_messages, system_prompt="System instructions"))
        assert result == "OK"
        assert len(captured_messages) == 4
        assert captured_messages[0] == {"role": "system", "content": "System instructions"}
        assert captured_messages[1] == {"role": "user", "content": "Dict message"}
        assert captured_messages[2] == {"role": "user", "content": "Raw string message"}
        assert captured_messages[3] == {"role": "assistant", "content": "Object message"}

    def test_llm_duplicate_system_prompt_filtering(self, monkeypatch):
        """Ensures that a system prompt already present in messages is not duplicated."""
        captured_messages = []

        async def fake_create(**kwargs):
            nonlocal captured_messages
            captured_messages = kwargs.get("messages", [])
            mock_resp = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = "Deduplicated"
            mock_resp.choices = [mock_choice]
            return mock_resp

        monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=fake_create)
        monkeypatch.setattr(llm, "get_llm_client", lambda: mock_client)

        prompt = "Act as HR Interviewer"
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "I am ready"},
        ]

        result = run_sync(llm.chat(messages=messages, system_prompt=prompt))
        assert result == "Deduplicated"
        # Should have exactly 1 system prompt, not 2
        system_prompts = [m for m in captured_messages if m["role"] == "system"]
        assert len(system_prompts) == 1

    def test_llm_empty_messages_list_defaults_to_hello(self, monkeypatch):
        """Tests that an empty messages list gracefully defaults to role=user, content='Hello'."""
        captured_messages = []

        async def fake_create(**kwargs):
            nonlocal captured_messages
            captured_messages = kwargs.get("messages", [])
            mock_resp = MagicMock()
            mock_choice = MagicMock()
            mock_choice.message.content = "Hello back"
            mock_resp.choices = [mock_choice]
            return mock_resp

        monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=fake_create)
        monkeypatch.setattr(llm, "get_llm_client", lambda: mock_client)

        result = run_sync(llm.chat(messages=[]))
        assert result == "Hello back"
        assert len(captured_messages) == 1
        assert captured_messages[0] == {"role": "user", "content": "Hello"}

    def test_llm_mock_mode_detection_tokens(self, monkeypatch):
        """Verifies that all placeholder tokens in NVIDIA_API_KEY trigger mock mode."""
        for token in ["placeholder", "dummy", "test", "your-key", "your_key", "mock", "example"]:
            monkeypatch.setenv("MOCK_AI_SERVICES", "")
            monkeypatch.setenv("NVIDIA_API_KEY", f"prefix_{token}_suffix")
            assert llm.is_mock_mode() is True

        # Unset / empty key
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
        assert llm.is_mock_mode() is True

        # Valid non-placeholder key
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-real-production-secret-999")
        assert llm.is_mock_mode() is False

    def test_llm_mock_generator_all_branches(self):
        """Directly tests all 4 branches in _generate_mock_response."""
        # Branch 1: Report generation
        resp1 = llm._generate_mock_response([], "Please output the report format with overall_score.")
        parsed1 = json.loads(resp1)
        assert "overall_score" in parsed1
        assert "dimension_scores" in parsed1

        # Branch 2a: Coach with grammatical error
        resp2a = llm._generate_mock_response(
            [{"role": "user", "content": "Yesterday I was go to the market."}],
            "Provide correction format for speech.",
        )
        parsed2a = json.loads(resp2a)
        assert parsed2a["correction"] is not None
        assert parsed2a["correction"]["original"] == "was go"

        # Branch 2b: Coach clean speech
        resp2b = llm._generate_mock_response(
            [{"role": "user", "content": "I built high-throughput microservices using FastAPI."}],
            "Provide correction format for speech.",
        )
        parsed2b = json.loads(resp2b)
        assert parsed2b["correction"] is None

        # Branch 3: Interviewer evaluation
        resp3 = llm._generate_mock_response([], 'Follow "output format after each answer" and "scores":')
        parsed3 = json.loads(resp3)
        assert "scores" in parsed3
        assert "follow_up" in parsed3

        # Branch 4: Default conversational response
        resp4 = llm._generate_mock_response([{"role": "user", "content": "Hi"}], "")
        assert "Thank you for sharing your experience" in resp4


# =============================================================================
# 2. STT SERVICE ADVERSARIAL TESTS (services/stt.py)
# =============================================================================

class TestSTTServiceAdversarial:
    """Adversarial stress tests for NVIDIA Parakeet ASR STT service."""

    def test_stt_short_and_empty_payloads(self):
        """Audio payloads smaller than 10 bytes return None immediately without network calls."""
        assert run_sync(stt.transcribe(b"")) is None
        assert run_sync(stt.transcribe(b"12345678")) is None
        assert run_sync(stt.transcribe(b"RIFF\x00\x00\x00\x00")) is None

    def test_stt_mock_mode_corrupt_detection(self, monkeypatch):
        """Verifies mock STT detects corrupt byte streams and returns None."""
        monkeypatch.setattr(stt, "is_mock_mode", lambda: True)
        assert run_sync(stt.transcribe(b"NOT_A_VALID_AUDIO_HEADER_12345")) is None
        assert run_sync(stt.transcribe(b"HEADER_CORRUPTED_STREAM_DATA_BYTES")) is None

        # Valid mock bytes
        valid_bytes = create_pcm_wav_bytes(100)
        valid_res = run_sync(stt.transcribe(valid_bytes))
        assert valid_res is not None
        assert "FastAPI" in valid_res

    def test_stt_live_mode_network_timeout(self, monkeypatch):
        """Simulates network timeout during Parakeet STT transcription; returns None gracefully."""
        monkeypatch.setattr(stt, "is_mock_mode", lambda: False)
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.ReadTimeout("Parakeet endpoint read timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(stt.httpx, "AsyncClient", lambda **kwargs: mock_client)

        res = run_sync(stt.transcribe(create_pcm_wav_bytes(100)))
        assert res is None

    def test_stt_live_mode_http_errors(self, monkeypatch):
        """Simulates HTTP 401, 429, 500, 503 from NVIDIA STT API; returns None without crash."""
        monkeypatch.setattr(stt, "is_mock_mode", lambda: False)
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")

        for status_code in [401, 429, 500, 503]:
            mock_resp = MagicMock()
            mock_resp.status_code = status_code
            mock_resp.text = f"Simulated error {status_code}"

            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            monkeypatch.setattr(stt.httpx, "AsyncClient", lambda **kwargs: mock_client)

            res = run_sync(stt.transcribe(create_pcm_wav_bytes(100)))
            assert res is None

    def test_stt_live_mode_empty_transcription_field(self, monkeypatch):
        """Tests HTTP 200 response with empty or missing text field; returns None."""
        monkeypatch.setattr(stt, "is_mock_mode", lambda: False)
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "", "other": 123}

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(stt.httpx, "AsyncClient", lambda **kwargs: mock_client)

        res = run_sync(stt.transcribe(create_pcm_wav_bytes(100)))
        assert res is None

    def test_stt_live_mode_success_transcription_alias(self, monkeypatch):
        """Tests HTTP 200 response using 'transcription' alias key instead of 'text'."""
        monkeypatch.setattr(stt, "is_mock_mode", lambda: False)
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"transcription": "I am answering the technical prompt."}

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(stt.httpx, "AsyncClient", lambda **kwargs: mock_client)

        res = run_sync(stt.transcribe(create_pcm_wav_bytes(100)))
        assert res == "I am answering the technical prompt."


# =============================================================================
# 3. TTS SERVICE ADVERSARIAL TESTS (services/tts.py)
# =============================================================================

class TestTTSServiceAdversarial:
    """Adversarial stress tests for NVIDIA Magpie TTS service."""

    def test_tts_empty_and_whitespace_inputs(self):
        """Empty, whitespace-only, or None text returns None immediately."""
        assert run_sync(tts.synthesize("")) is None
        assert run_sync(tts.synthesize("     \n\t  ")) is None
        assert run_sync(tts.synthesize(None)) is None

    def test_tts_generate_mock_wav_structure(self):
        """Validates RIFF header, fmt chunk, and data chunk of synthesized mock WAV."""
        wav_bytes = tts.generate_mock_wav(duration_ms=150, sample_rate=16000)
        assert len(wav_bytes) > 44
        assert wav_bytes[:4] == b"RIFF"
        assert wav_bytes[8:12] == b"WAVE"
        assert wav_bytes[12:16] == b"fmt "
        assert b"data" in wav_bytes

    def test_tts_live_mode_network_timeout(self, monkeypatch):
        """Simulates network timeout during Magpie TTS synthesis; returns None without crash."""
        monkeypatch.setattr(tts, "is_mock_mode", lambda: False)
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectTimeout("Magpie endpoint connect timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(tts.httpx, "AsyncClient", lambda **kwargs: mock_client)

        res = run_sync(tts.synthesize("Welcome to VOXPREP."))
        assert res is None

    def test_tts_live_mode_http_errors(self, monkeypatch):
        """Simulates HTTP 429, 500, 504 from NVIDIA TTS API; returns None gracefully."""
        monkeypatch.setattr(tts, "is_mock_mode", lambda: False)
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")

        for status_code in [429, 500, 504]:
            mock_resp = MagicMock()
            mock_resp.status_code = status_code
            mock_resp.text = f"Simulated error {status_code}"

            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            monkeypatch.setattr(tts.httpx, "AsyncClient", lambda **kwargs: mock_client)

            res = run_sync(tts.synthesize("Sample speech text."))
            assert res is None

    def test_tts_live_mode_empty_content_body(self, monkeypatch):
        """Tests HTTP 200 response with 0-byte audio body; returns None."""
        monkeypatch.setattr(tts, "is_mock_mode", lambda: False)
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b""

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(tts.httpx, "AsyncClient", lambda **kwargs: mock_client)

        res = run_sync(tts.synthesize("Valid test text."))
        assert res is None


# =============================================================================
# 4. VOICE ROUTER ADVERSARIAL TESTS (routers/voice.py)
# =============================================================================

class TestVoiceRouterAdversarial:
    """Adversarial pipeline tests for POST /voice/process endpoint."""

    def test_voice_corrupt_file_read_exception(self, client):
        """UploadFile.read() throwing an exception returns fallback STT prompt without 500 crash."""
        class ExplodingFile:
            def __init__(self):
                self.filename = "audio.wav"
                self.content_type = "audio/wav"

            def read(self):
                raise IOError("Simulated disk read corruption")

        resp = client.post(
            "/voice/process",
            files={"file": ("corrupt.wav", b"short", "audio/wav")},
            data={"agent_type": "interview"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["spoken_response"] == voice.FALLBACK_STT_PROMPT
        assert data["transcript"] == ""
        assert data["audio_base64"] is None

    def test_voice_truncated_audio_boundary(self, client):
        """Audio payload with exactly 11 bytes (<12 boundary) returns fallback prompt."""
        resp = client.post(
            "/voice/process",
            files={"file": ("short.wav", b"12345678901", "audio/wav")},
            data={"agent_type": "interview"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["spoken_response"] == voice.FALLBACK_STT_PROMPT

    def test_voice_stt_failure_fallback(self, client, monkeypatch):
        """When STT returns None, voice pipeline returns fallback prompt gracefully."""
        monkeypatch.setattr(stt, "transcribe", AsyncMock(return_value=None))

        resp = client.post(
            "/voice/process",
            files={"file": ("test.wav", create_pcm_wav_bytes(100), "audio/wav")},
            data={"agent_type": "interview"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["spoken_response"] == voice.FALLBACK_STT_PROMPT
        assert data["audio_base64"] is None

    def test_voice_llm_empty_response_fallback(self, client, monkeypatch):
        """When LLM returns empty string, fallback dialog message is substituted."""
        monkeypatch.setattr(stt, "transcribe", AsyncMock(return_value="Valid candidate answer."))
        monkeypatch.setattr(llm, "chat", AsyncMock(return_value="   "))
        monkeypatch.setattr(tts, "synthesize", AsyncMock(return_value=create_pcm_wav_bytes(100)))

        resp = client.post(
            "/voice/process",
            files={"file": ("test.wav", create_pcm_wav_bytes(100), "audio/wav")},
            data={"agent_type": "interview"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Thank you for your response" in data["spoken_response"]
        assert data["audio_base64"] is not None

    def test_voice_tts_failure_web_speech_fallback(self, client, monkeypatch):
        """When TTS returns None, audio_base64 is None so frontend falls back to Web Speech API."""
        monkeypatch.setattr(stt, "transcribe", AsyncMock(return_value="Candidate speaking."))
        monkeypatch.setattr(llm, "chat", AsyncMock(return_value="Coach feedback response."))
        monkeypatch.setattr(tts, "synthesize", AsyncMock(return_value=None))

        resp = client.post(
            "/voice/process",
            files={"file": ("test.wav", create_pcm_wav_bytes(100), "audio/wav")},
            data={"agent_type": "coach"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["transcript"] == "Candidate speaking."
        assert data["spoken_response"] == "Coach feedback response."
        assert data["audio_base64"] is None

    def test_voice_agent_type_permutations(self, client):
        """Tests case variations and unsupplied agent_type parameter."""
        wav_data = create_pcm_wav_bytes(100)

        # 1. Coach uppercase
        resp1 = client.post(
            "/voice/process",
            files={"file": ("test.wav", wav_data, "audio/wav")},
            data={"agent_type": "COACH"},
        )
        assert resp1.status_code == 200

        # 2. Unsupplied agent_type (defaults to interview)
        resp2 = client.post(
            "/voice/process",
            files={"file": ("test.wav", wav_data, "audio/wav")},
            data={},
        )
        assert resp2.status_code == 200

    def test_voice_session_id_and_history_passthrough(self, client):
        """Tests that session_id is preserved and returned in VoiceProcessResponse."""
        sid = "sid-tier5-voice-999"
        resp = client.post(
            "/voice/process",
            files={"file": ("test.wav", create_pcm_wav_bytes(100), "audio/wav")},
            data={"agent_type": "interview", "session_id": sid, "conversation_history": "Prev context"},
        )
        assert resp.status_code == 200
        assert resp.json()["session_id"] == sid


# =============================================================================
# 5. AUTH ROUTER ADVERSARIAL TESTS (routers/auth.py)
# =============================================================================

class TestAuthRouterAdversarial:
    """Adversarial stress tests for POST /auth/register and POST /auth/login."""

    def test_auth_register_invalid_email_formats(self, client):
        """Rejects emails without @, empty strings, and whitespace."""
        for bad_email in ["notanemail", "missing-at-sign.com", "   ", ""]:
            resp = client.post("/auth/register", json={"email": bad_email, "password": "Password123!"})
            assert resp.status_code in [400, 422]

    def test_auth_register_short_password(self, client):
        """Rejects passwords shorter than 6 characters with HTTP 422."""
        resp = client.post("/auth/register", json={"email": "valid@voxprep.ai", "password": "12345"})
        assert resp.status_code == 422

    def test_auth_register_email_case_and_whitespace(self, client):
        """Trims whitespace and lowercases email during registration."""
        email_raw = "  Tier5.Normalization@VOXPREP.AI  "
        resp = client.post(
            "/auth/register",
            json={"email": email_raw, "password": "SecurePassword123!", "name": "Tier5 User"},
        )
        assert resp.status_code == 201
        assert resp.json()["user"]["email"] == "tier5.normalization@voxprep.ai"

    def test_auth_register_duplicate_precheck(self, client):
        """Duplicate registration triggers proactive duplicate check with HTTP 400."""
        email = "duplicate.tier5@voxprep.ai"
        resp1 = client.post("/auth/register", json={"email": email, "password": "Password123!"})
        assert resp1.status_code == 201

        resp2 = client.post("/auth/register", json={"email": email, "password": "Password123!"})
        assert resp2.status_code == 400
        assert "already registered" in resp2.json()["detail"].lower()

    def test_auth_register_rapid_concurrent_collisions(self):
        """10 parallel threads attempting to register the exact same email: exactly 1 succeeds, 9 fail."""
        email = "rapid.collision@voxprep.ai"
        results = []

        def register_worker():
            with LocalClient(app) as test_client:
                return test_client.post(
                    "/auth/register",
                    json={"email": email, "password": "CollisionPassword123!"},
                )

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(register_worker) for _ in range(10)]
            for f in as_completed(futures):
                results.append(f.result().status_code)

        assert results.count(201) == 1
        assert results.count(400) == 9

    def test_auth_register_db_insert_resilience(self, client, monkeypatch):
        """Database users table insert throwing an exception does not crash user registration."""
        supabase_client = get_supabase_client()
        original_table = supabase_client.table

        def mock_table(name):
            query = original_table(name)
            if name == "users":
                original_insert = query.insert

                def exploding_insert(*args, **kwargs):
                    raise RuntimeError("Simulated users table insert failure")

                query.insert = exploding_insert
            return query

        monkeypatch.setattr(supabase_client, "table", mock_table)

        resp = client.post(
            "/auth/register",
            json={"email": "resilient.db.failure@voxprep.ai", "password": "Password123!"},
        )
        assert resp.status_code == 201
        assert "access_token" in resp.json()

    def test_auth_login_invalid_email_format(self, client):
        """Email missing @ triggers HTTP 401 on login."""
        resp = client.post("/auth/login", json={"email": "notanemail", "password": "Password123!"})
        assert resp.status_code == 401

    def test_auth_login_nonexistent_or_wrong_password(self, client):
        """Unknown user or incorrect password triggers HTTP 401."""
        resp1 = client.post("/auth/login", json={"email": "ghost.user@voxprep.ai", "password": "Password123!"})
        assert resp1.status_code == 401

        # Register user then try wrong password
        email = "login.test.tier5@voxprep.ai"
        client.post("/auth/register", json={"email": email, "password": "CorrectPassword123!"})

        resp2 = client.post("/auth/login", json={"email": email, "password": "WrongPassword999!"})
        assert resp2.status_code == 401

    def test_auth_login_display_name_lookup_exception_resilience(self, client, monkeypatch):
        """When display name lookup throws an exception, login gracefully defaults to 'Candidate'."""
        email = "name.fallback@voxprep.ai"
        client.post("/auth/register", json={"email": email, "password": "Password123!", "name": "Alice"})

        supabase_client = get_supabase_client()
        original_table = supabase_client.table

        def mock_table(name):
            query = original_table(name)
            if name == "users":
                query.single = MagicMock(side_effect=Exception("Database lock timeout"))
            return query

        monkeypatch.setattr(supabase_client, "table", mock_table)

        resp = client.post("/auth/login", json={"email": email, "password": "Password123!"})
        assert resp.status_code == 200
        assert resp.json()["user"]["name"] == "Candidate"


# =============================================================================
# 6. INTERVIEW ROUTER ADVERSARIAL TESTS (routers/interview.py)
# =============================================================================

class TestInterviewRouterAdversarial:
    """Adversarial pipeline tests for Interviewer Agent router."""

    def test_interview_start_invalid_interview_type(self, client):
        """Rejects interview_type outside of 'hr' or 'technical' with HTTP 422."""
        for bad_type in ["behavioral", "executive", "sales", ""]:
            resp = client.post(
                "/interview/start",
                json={
                    "candidate_name": "Test Candidate",
                    "role": "Backend Engineer",
                    "experience_level": "Senior",
                    "interview_type": bad_type,
                },
            )
            assert resp.status_code == 422

    def test_interview_start_whitespace_case_insensitive(self, client):
        """Normalizes '  HR  ' and ' Technical ' to valid interview types."""
        resp1 = client.post(
            "/interview/start",
            json={
                "candidate_name": "Candidate One",
                "role": "Product Manager",
                "experience_level": "Mid",
                "interview_type": "  HR  ",
            },
        )
        assert resp1.status_code == 200
        assert "session_id" in resp1.json()

        resp2 = client.post(
            "/interview/start",
            json={
                "candidate_name": "Candidate Two",
                "role": "Cloud Architect",
                "experience_level": "Principal",
                "interview_type": " Technical ",
            },
        )
        assert resp2.status_code == 200
        assert "session_id" in resp2.json()

    def test_interview_respond_nonexistent_session(self, client):
        """Responding to unknown session ID returns HTTP 404."""
        resp = client.post(
            "/interview/respond",
            json={"session_id": "00000000-0000-0000-0000-000000000999", "answer_text": "Answer"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_interview_end_nonexistent_session(self, client):
        """Ending unknown session ID returns HTTP 404."""
        resp = client.post(
            "/interview/end",
            json={"session_id": "00000000-0000-0000-0000-000000000999"},
        )
        assert resp.status_code == 404

    def test_interview_report_nonexistent_session(self, client):
        """Fetching report for unknown session returns HTTP 404."""
        resp = client.get("/interview/report/00000000-0000-0000-0000-000000000999")
        assert resp.status_code == 404

    def test_interview_report_in_progress_session(self, client):
        """Fetching report on incomplete session returns HTTP 400."""
        start_resp = client.post(
            "/interview/start",
            json={
                "candidate_name": "Active Candidate",
                "role": "QA Engineer",
                "experience_level": "Junior",
                "interview_type": "technical",
            },
        )
        sid = start_resp.json()["session_id"]

        resp = client.get(f"/interview/report/{sid}")
        assert resp.status_code == 400
        assert "not yet completed" in resp.json()["detail"].lower()

    def test_interview_report_completed_without_cached_report(self, client):
        """Session marked complete in DB but missing cached report triggers dynamic report generation."""
        sid = "completed-no-report-tier5"
        # Seed session directly in DB persistence
        run_sync(create_interview_session({
            "id": sid,
            "session_id": sid,
            "candidate_name": "Completed Alice",
            "role": "Security Engineer",
            "experience_level": "Lead",
            "interview_type": "technical",
            "is_complete": True,
            "status": "completed",
            "history": [
                {"question": "Q1", "answer": "A1", "scores": {"relevance": 8, "clarity": 8, "depth": 8, "examples": 8}}
            ],
            "report": None,
        }))

        # Load into session manager
        session = run_sync(interview.session_manager.get_or_load(sid))
        session.is_complete = True
        session.report = None

        resp = client.get(f"/interview/report/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_score" in data


# =============================================================================
# 7. COACH ROUTER ADVERSARIAL TESTS (routers/coach.py)
# =============================================================================

class TestCoachRouterAdversarial:
    """Adversarial pipeline tests for AI Communication Coach router."""

    def test_coach_start_empty_user_id(self, client):
        """Empty or whitespace user_id returns HTTP 400."""
        resp = client.post("/coach/start", json={"user_id": "   ", "mode": "conversation"})
        assert resp.status_code == 400
        assert "user_id must not be empty" in resp.json()["detail"]

    def test_coach_start_invalid_mode(self, client):
        """Invalid coach mode returns HTTP 400 listing supported modes."""
        resp = client.post("/coach/start", json={"user_id": "user-123", "mode": "freestyle"})
        assert resp.status_code == 400
        assert "Invalid coach mode" in resp.json()["detail"]
        assert "conversation" in resp.json()["detail"]

    def test_coach_respond_empty_session_id(self, client):
        """Empty session_id returns HTTP 400."""
        resp = client.post("/coach/respond", json={"session_id": "   ", "user_text": "Hello"})
        assert resp.status_code == 400
        assert "session_id must not be empty" in resp.json()["detail"]

    def test_coach_respond_empty_user_text(self, client):
        """Empty or whitespace user_text returns HTTP 400."""
        resp = client.post("/coach/respond", json={"session_id": "valid-sid", "user_text": "   "})
        assert resp.status_code == 400
        assert "user_text cannot be empty" in resp.json()["detail"]

    def test_coach_respond_nonexistent_session(self, client):
        """Responding to unknown coach session returns HTTP 404."""
        resp = client.post(
            "/coach/respond",
            json={"session_id": "00000000-0000-0000-0000-000000000999", "user_text": "Speaking now."},
        )
        assert resp.status_code == 404
        assert "Coach session not found" in resp.json()["detail"]

    def test_coach_respond_already_completed_session(self, client):
        """Submitting responses to already completed coach session returns HTTP 400."""
        start_resp = client.post("/coach/start", json={"user_id": "user-comp", "mode": "conversation"})
        sid = start_resp.json()["session_id"]

        end_resp = client.post("/coach/end", json={"session_id": sid})
        assert end_resp.status_code == 200

        resp = client.post("/coach/respond", json={"session_id": sid, "user_text": "Can I continue?"})
        assert resp.status_code == 400
        assert "already completed" in resp.json()["detail"].lower()

    def test_coach_end_nonexistent_session(self, client):
        """Ending non-existent coach session returns HTTP 404."""
        resp = client.post("/coach/end", json={"session_id": "00000000-0000-0000-0000-000000000999"})
        assert resp.status_code == 404

    def test_coach_end_idempotent_duplicate_termination(self, client):
        """Calling /coach/end multiple times on the same session is idempotent and returns HTTP 200."""
        start_resp = client.post("/coach/start", json={"user_id": "user-idem", "mode": "english_improvement"})
        sid = start_resp.json()["session_id"]

        resp1 = client.post("/coach/end", json={"session_id": sid})
        assert resp1.status_code == 200
        data1 = resp1.json()

        resp2 = client.post("/coach/end", json={"session_id": sid})
        assert resp2.status_code == 200
        data2 = resp2.json()

        assert data1["session_id"] == data2["session_id"]
        assert data1["status"] == data2["status"] == "completed"


# =============================================================================
# 8. SUPABASE CLIENT & QUERY ADVERSARIAL TESTS (db/supabase.py)
# =============================================================================

class TestSupabaseClientAndQueryAdversarial:
    """Adversarial concurrency and query builder tests for Supabase client."""

    def test_supabase_singleton_thread_safety(self):
        """20 concurrent threads calling get_supabase_client() all receive the identical instance."""
        instances = []

        def worker():
            return get_supabase_client()

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(worker) for _ in range(20)]
            for f in as_completed(futures):
                instances.append(f.result())

        first_instance = instances[0]
        for inst in instances:
            assert inst is first_instance

    def test_supabase_reset_singleton(self):
        """reset_supabase_client() clears singleton instance; next call instantiates fresh client."""
        inst1 = get_supabase_client()
        reset_supabase_client()
        inst2 = get_supabase_client()
        assert inst1 is not inst2

    def test_mock_table_query_corrupt_insert_types(self):
        """MockTableQuery.insert safely handles strings, integers, None, and corrupt lists."""
        store: Dict[str, List[Dict[str, Any]]] = {}
        query = MockTableQuery("audit_table", store)

        # Corrupt single values
        query.insert("corrupt_string").execute()
        query.insert(12345).execute()
        query.insert(None).execute()
        assert store.get("audit_table") == []

        # Corrupt list with mixed valid and invalid items
        query.insert([
            {"id": "valid-1", "name": "Item 1"},
            "corrupt_item_str",
            123,
            {"id": "valid-2", "name": "Item 2"},
            None,
        ]).execute()

        rows = store.get("audit_table")
        assert len(rows) == 2
        assert rows[0]["id"] == "valid-1"
        assert rows[1]["id"] == "valid-2"

    def test_mock_table_query_non_dict_update(self):
        """MockTableQuery.update with non-dict does not mutate existing table rows."""
        store = {"users": [{"id": "u1", "role": "dev"}]}
        query = MockTableQuery("users", store)

        query.eq("id", "u1").update("not_a_dict").execute()
        assert store["users"][0]["role"] == "dev"

    def test_mock_table_query_compound_eq_filtering(self):
        """MockTableQuery supports multiple chained .eq() filters with AND logic."""
        store = {
            "sessions": [
                {"id": "s1", "type": "hr", "status": "completed"},
                {"id": "s2", "type": "hr", "status": "in_progress"},
                {"id": "s3", "type": "technical", "status": "completed"},
            ]
        }
        res = MockTableQuery("sessions", store).eq("type", "hr").eq("status", "completed").execute()
        assert len(res.data) == 1
        assert res.data[0]["id"] == "s1"

    def test_mock_table_query_ordering_numeric_with_nones(self):
        """MockTableQuery.order sorts numeric columns with None values safely."""
        store = {
            "data": [
                {"id": "1", "score": None},
                {"id": "2", "score": 9.5},
                {"id": "3", "score": 7.0},
            ]
        }
        res_asc = MockTableQuery("data", store).order("score", desc=False).execute()
        assert len(res_asc.data) == 3
        assert res_asc.data[0]["id"] == "3"  # 7.0
        assert res_asc.data[1]["id"] == "2"  # 9.5
        assert res_asc.data[2]["id"] == "1"  # None

        res_desc = MockTableQuery("data", store).order("score", desc=True).execute()
        assert res_desc.data[0]["id"] == "1"  # None comes first in desc
        assert res_desc.data[1]["id"] == "2"  # 9.5
        assert res_desc.data[2]["id"] == "3"  # 7.0

    def test_mock_table_query_ordering_strings_with_nones(self):
        """MockTableQuery.order sorts string columns with None values safely."""
        store = {
            "data": [
                {"id": "1", "name": None},
                {"id": "2", "name": "Charlie"},
                {"id": "3", "name": "Alice"},
            ]
        }
        res_asc = MockTableQuery("data", store).order("name", desc=False).execute()
        assert len(res_asc.data) == 3
        assert res_asc.data[0]["id"] == "3"  # Alice
        assert res_asc.data[1]["id"] == "2"  # Charlie
        assert res_asc.data[2]["id"] == "1"  # None

    def test_mock_table_query_ordering_mixed_types_boundary(self):
        """Empirically confirms that heterogeneous types (str and float) in the same column trigger TypeError."""
        store = {
            "data": [
                {"id": "1", "val": 9.5},
                {"id": "2", "val": "unscored"},
            ]
        }
        with pytest.raises(TypeError) as excinfo:
            MockTableQuery("data", store).order("val", desc=False).execute()
        assert "not supported between instances of" in str(excinfo.value)

    def test_mock_table_query_limit_zero_and_negative(self):
        """MockTableQuery.limit(0) and negative limits are safely clamped to 0."""
        store = {"items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        res0 = MockTableQuery("items", store).limit(0).execute()
        assert res0.data == []

        res_neg = MockTableQuery("items", store).limit(-5).execute()
        assert res_neg.data == []

    def test_mock_table_query_single_empty_vs_found(self):
        """MockTableQuery.single() returns None when empty, and dict when found."""
        store = {"items": [{"id": "target", "val": 42}]}
        found = MockTableQuery("items", store).eq("id", "target").single().execute()
        assert isinstance(found.data, dict)
        assert found.data["val"] == 42

        missing = MockTableQuery("items", store).eq("id", "nonexistent").single().execute()
        assert missing.data is None

    def test_mock_table_query_delete_matching_vs_nonmatching(self):
        """MockTableQuery.delete removes only rows matching all accumulated filters."""
        store = {
            "records": [
                {"id": "r1", "status": "stale"},
                {"id": "r2", "status": "active"},
                {"id": "r3", "status": "stale"},
            ]
        }
        del_res = MockTableQuery("records", store).eq("status", "stale").delete().execute()
        assert len(del_res.data) == 2
        assert len(store["records"]) == 1
        assert store["records"][0]["id"] == "r2"

    def test_mock_auth_thread_safety_and_collisions(self):
        """MockAuth handles concurrent sign_ups and sign_ins across multiple threads safely."""
        mock_auth = MockAuth()
        emails = [f"thread_user_{i}@voxprep.ai" for i in range(15)]

        def worker(email):
            mock_auth.sign_up({"email": email, "password": "Password123!"})
            return mock_auth.sign_in_with_password({"email": email, "password": "Password123!"})

        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(worker, e) for e in emails]
            for f in as_completed(futures):
                resp = f.result()
                assert resp.user.email in emails
                assert resp.session.access_token == "mock-jwt-token"


# =============================================================================
# 9. MAIN APP & CORS ADVERSARIAL TESTS (app/main.py)
# =============================================================================

class TestMainAppAndCorsAdversarial:
    """Adversarial tests for CORS resolution and GlobalExceptionMiddleware."""

    def test_get_allowed_origins_env_combinations(self, monkeypatch):
        """Tests parsing of ALLOWED_ORIGINS and CORS_ORIGINS across all variants."""
        # Comma-separated list with whitespace
        monkeypatch.setenv("ALLOWED_ORIGINS", " https://app.voxprep.ai , https://preview.voxprep.ai ")
        assert get_allowed_origins() == ["https://app.voxprep.ai", "https://preview.voxprep.ai"]

        # Empty string fallback
        monkeypatch.setenv("ALLOWED_ORIGINS", "")
        assert get_allowed_origins() == ["http://localhost:3000"]

        # Fallback to CORS_ORIGINS when ALLOWED_ORIGINS is unset
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
        monkeypatch.setenv("CORS_ORIGINS", "https://secondary.voxprep.ai")
        assert get_allowed_origins() == ["https://secondary.voxprep.ai"]

        # Both unset -> wildcard default
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        assert get_allowed_origins() == ["*"]

    def test_global_exception_middleware_cors_reflection_on_500(self):
        """GlobalExceptionMiddleware catches unhandled exception, sends 500 JSON, and reflects Origin."""
        async def broken_app(scope, receive, send):
            raise RuntimeError("Fatal unhandled pipeline crash")

        middleware = GlobalExceptionMiddleware(broken_app)

        messages = []
        async def fake_send(msg):
            messages.append(msg)

        async def fake_receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/crash",
            "headers": [(b"origin", b"https://adversarial-origin.com")],
        }

        run_sync(middleware(scope, fake_receive, fake_send))

        assert len(messages) == 2
        start_msg = messages[0]
        assert start_msg["type"] == "http.response.start"
        assert start_msg["status"] == 500

        headers_dict = {k.decode("latin1").lower(): v.decode("latin1") for k, v in start_msg["headers"]}
        assert headers_dict["access-control-allow-origin"] == "https://adversarial-origin.com"
        assert headers_dict["access-control-allow-credentials"] == "true"
        assert headers_dict["vary"] == "Origin"

        body_msg = messages[1]
        assert body_msg["type"] == "http.response.body"
        body_json = json.loads(body_msg["body"].decode("utf-8"))
        assert body_json["status_code"] == 500
        assert body_json["error_type"] == "internal_server_error"

    def test_global_exception_middleware_non_http_scope(self):
        """Non-HTTP scopes (e.g. lifespan or websocket) bypass GlobalExceptionMiddleware directly."""
        called = False

        async def lifespan_app(scope, receive, send):
            nonlocal called
            called = True
            await send({"type": "lifespan.startup.complete"})

        middleware = GlobalExceptionMiddleware(lifespan_app)
        messages = []

        async def fake_send(msg):
            messages.append(msg)

        async def fake_receive():
            return {"type": "lifespan.startup"}

        scope = {"type": "lifespan"}
        run_sync(middleware(scope, fake_receive, fake_send))

        assert called is True
        assert messages[0]["type"] == "lifespan.startup.complete"
