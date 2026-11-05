"""Integration tests for POST /voice/process endpoint.

Tests cover:
- Valid audio processing with interview and coach agent types.
- Empty audio fallback (returns friendly retry message).
- Corrupt audio fallback.
- STT failure fallback (graceful degradation without 500).
- TTS failure fallback (returns text with audio_base64=None for Web Speech API).
- Authenticated voice processing requests.
"""

import pytest
from unittest.mock import AsyncMock
from app.services import stt, tts, llm


def test_voice_process_valid_audio_interview(client, dummy_wav_bytes):
    """Verify POST /voice/process with valid audio returns transcript, response, and audio."""
    files = {"file": ("recording.wav", dummy_wav_bytes, "audio/wav")}
    data = {"agent_type": "interview"}

    response = client.post("/voice/process", files=files, data=data)
    assert response.status_code == 200, f"Failed: {response.status_code} {response.text}"

    json_data = response.json()
    assert "transcript" in json_data
    assert "spoken_response" in json_data
    assert "audio_base64" in json_data
    assert len(json_data["spoken_response"]) > 0


def test_voice_process_valid_audio_coach(client, dummy_wav_bytes):
    """Verify POST /voice/process with coach agent_type succeeds."""
    files = {"file": ("coach_test.wav", dummy_wav_bytes, "audio/wav")}
    data = {"agent_type": "coach"}

    response = client.post("/voice/process", files=files, data=data)
    assert response.status_code == 200
    json_data = response.json()
    assert "spoken_response" in json_data
    assert len(json_data["spoken_response"]) > 0


def test_voice_process_empty_audio_fallback(client, empty_audio_bytes):
    """Verify 0-byte audio returns friendly retry message without server crash."""
    files = {"file": ("empty.wav", empty_audio_bytes, "audio/wav")}
    data = {"agent_type": "interview"}

    response = client.post("/voice/process", files=files, data=data)
    assert response.status_code in [200, 400, 422]

    if response.status_code == 200:
        json_data = response.json()
        resp_text = (json_data.get("spoken_response") or json_data.get("transcript") or "").lower()
        assert any(term in resp_text for term in ["not understand", "try again", "could not", "repeat"])
        assert json_data.get("audio_base64") is None


def test_voice_process_corrupt_audio_fallback(client, corrupt_audio_bytes):
    """Verify corrupted non-audio bytes return friendly retry message."""
    files = {"file": ("corrupt.wav", corrupt_audio_bytes, "audio/wav")}
    data = {"agent_type": "interview"}

    response = client.post("/voice/process", files=files, data=data)
    assert response.status_code in [200, 400, 422]

    if response.status_code == 200:
        json_data = response.json()
        resp_text = (json_data.get("spoken_response") or "").lower()
        assert any(term in resp_text for term in ["not understand", "try again", "could not", "repeat"])


def test_voice_process_stt_failure_fallback(client, monkeypatch, dummy_wav_bytes):
    """Verify system handles STT returning None by prompting candidate to repeat."""
    monkeypatch.setattr(stt, "transcribe", AsyncMock(return_value=None))

    files = {"file": ("sample.wav", dummy_wav_bytes, "audio/wav")}
    data = {"agent_type": "interview"}

    response = client.post("/voice/process", files=files, data=data)
    assert response.status_code == 200

    json_data = response.json()
    assert json_data.get("transcript") == ""
    spoken = json_data.get("spoken_response", "").lower()
    assert "understand" in spoken or "try again" in spoken
    assert json_data.get("audio_base64") is None


def test_voice_process_tts_failure_fallback(client, monkeypatch, dummy_wav_bytes):
    """Verify system handles TTS returning None by returning text with null audio_base64."""
    monkeypatch.setattr(tts, "synthesize", AsyncMock(return_value=None))

    files = {"file": ("sample.wav", dummy_wav_bytes, "audio/wav")}
    data = {"agent_type": "interview"}

    response = client.post("/voice/process", files=files, data=data)
    assert response.status_code == 200

    json_data = response.json()
    assert len(json_data.get("spoken_response", "")) > 0
    # audio_base64 must be null so frontend can fall back to browser Web Speech API
    assert json_data.get("audio_base64") is None


def test_voice_process_authenticated(client, dummy_wav_bytes):
    """Verify voice processing works with Authorization Bearer header."""
    files = {"file": ("auth_voice.wav", dummy_wav_bytes, "audio/wav")}
    data = {"agent_type": "interview"}
    headers = {"Authorization": "Bearer mock-jwt-token"}

    response = client.post("/voice/process", files=files, data=data, headers=headers)
    assert response.status_code == 200
