"""Unit tests for Phase 1 AI services (LLM, STT, TTS).

Tests cover:
- services/llm.py: chat success, single retry on failure, fallback string, system prompt, offline mode.
- services/stt.py: transcribe success, failure returns None, empty audio handling, offline mode.
- services/tts.py: synthesize success, failure returns None, empty text handling, offline mode.

Uses an in-memory coroutine driver (matching LocalClient in conftest.py) to execute
async functions without creating loopback sockets in restricted sandbox environments.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services import llm, stt, tts


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


# =============================================================================
# 1. LLM SERVICE TESTS (services/llm.py)
# =============================================================================

def test_llm_chat_success(monkeypatch):
    """Verify chat() successfully returns generated content from Nemotron."""
    monkeypatch.setattr(llm, "is_mock_mode", lambda: False)

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Nemotron response: Tell me about your background."
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    monkeypatch.setattr(llm, "get_llm_client", lambda: mock_client)

    messages = [{"role": "user", "content": "Hello"}]
    result = run_sync(llm.chat(messages, system_prompt="You are an expert interviewer."))

    assert result == "Nemotron response: Tell me about your background."
    assert mock_client.chat.completions.create.call_count == 1
    call_args = mock_client.chat.completions.create.call_args[1]
    assert call_args["messages"][0]["role"] == "system"
    assert call_args["messages"][0]["content"] == "You are an expert interviewer."
    assert call_args["messages"][1]["role"] == "user"


def test_llm_chat_single_retry_on_failure(monkeypatch):
    """Verify chat() retries exactly once on transient failure before succeeding."""
    monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
    monkeypatch.setattr(llm.asyncio, "sleep", AsyncMock(return_value=None))

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Success on second attempt."
    mock_response.choices = [mock_choice]

    # Call 1 fails, Call 2 succeeds
    mock_create = AsyncMock(side_effect=[
        Exception("503 Service Unavailable"),
        mock_response
    ])
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    monkeypatch.setattr(llm, "get_llm_client", lambda: mock_client)

    messages = [{"role": "user", "content": "Hello"}]
    result = run_sync(llm.chat(messages, system_prompt=""))

    assert result == "Success on second attempt."
    assert mock_create.call_count == 2


def test_llm_chat_fallback_on_double_failure(monkeypatch):
    """Verify chat() catches double failure and returns friendly fallback without crashing."""
    monkeypatch.setattr(llm, "is_mock_mode", lambda: False)
    monkeypatch.setattr(llm.asyncio, "sleep", AsyncMock(return_value=None))

    mock_create = AsyncMock(side_effect=[
        Exception("Attempt 1 failure"),
        Exception("Attempt 2 failure")
    ])
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    monkeypatch.setattr(llm, "get_llm_client", lambda: mock_client)

    messages = [{"role": "user", "content": "Hello"}]
    result = run_sync(llm.chat(messages, system_prompt=""))

    assert isinstance(result, str)
    assert len(result) > 0
    # Must contain friendly message per docs/07_GUARDRAILS.md
    lower_res = result.lower()
    assert any(term in lower_res for term in ["experiencing", "repeat", "traffic", "apologize", "technical"])
    assert mock_create.call_count == 2


def test_llm_chat_offline_mode():
    """Verify chat() operates cleanly with dummy API key in offline mode."""
    result = run_sync(llm.chat([{"role": "user", "content": "Hello"}], system_prompt="Test"))
    assert isinstance(result, str)
    assert len(result) > 0


# =============================================================================
# 2. STT SERVICE TESTS (services/stt.py)
# =============================================================================

def test_stt_transcribe_success(monkeypatch, dummy_wav_bytes):
    """Verify transcribe() returns transcribed text on successful API response."""
    monkeypatch.setattr(stt, "is_mock_mode", lambda: False)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"text": "I have experience with Python and FastAPI."}

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(stt.httpx, "AsyncClient", lambda **kwargs: mock_client)

    result = run_sync(stt.transcribe(dummy_wav_bytes))
    assert result == "I have experience with Python and FastAPI."


def test_stt_transcribe_failure_returns_none(monkeypatch, dummy_wav_bytes):
    """Verify transcribe() returns None on API failure without raising unhandled exceptions."""
    monkeypatch.setattr(stt, "is_mock_mode", lambda: False)

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=stt.httpx.HTTPError("Connection failed"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(stt.httpx, "AsyncClient", lambda **kwargs: mock_client)

    result = run_sync(stt.transcribe(dummy_wav_bytes))
    assert result is None


def test_stt_transcribe_empty_bytes_returns_none(empty_audio_bytes):
    """Verify transcribe() handles empty bytes gracefully by returning None."""
    result = run_sync(stt.transcribe(empty_audio_bytes))
    assert result is None


def test_stt_transcribe_offline_mode(dummy_wav_bytes):
    """Verify transcribe() in offline test mode returns mock transcript."""
    result = run_sync(stt.transcribe(dummy_wav_bytes))
    assert isinstance(result, str)
    assert len(result) > 0


# =============================================================================
# 3. TTS SERVICE TESTS (services/tts.py)
# =============================================================================

def test_tts_synthesize_success(monkeypatch, dummy_wav_bytes):
    """Verify synthesize() returns valid WAV audio bytes on success."""
    monkeypatch.setattr(tts, "is_mock_mode", lambda: False)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = dummy_wav_bytes

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(tts.httpx, "AsyncClient", lambda **kwargs: mock_client)

    result = run_sync(tts.synthesize("Welcome to your interview."))
    assert result is not None
    assert isinstance(result, bytes)
    assert result.startswith(b"RIFF")


def test_tts_synthesize_failure_returns_none(monkeypatch):
    """Verify synthesize() returns None on API failure without raising unhandled exceptions."""
    monkeypatch.setattr(tts, "is_mock_mode", lambda: False)

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=tts.httpx.RequestError("Gateway timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(tts.httpx, "AsyncClient", lambda **kwargs: mock_client)

    result = run_sync(tts.synthesize("Welcome to your interview."))
    assert result is None


def test_tts_synthesize_empty_text_returns_none():
    """Verify synthesize() returns None for empty or whitespace text."""
    assert run_sync(tts.synthesize("")) is None
    assert run_sync(tts.synthesize("   ")) is None


def test_tts_synthesize_offline_mode():
    """Verify synthesize() in offline test mode returns valid dummy audio bytes."""
    result = run_sync(tts.synthesize("Hello candidate"))
    assert isinstance(result, bytes)
    assert len(result) > 0
    assert result.startswith(b"RIFF")
