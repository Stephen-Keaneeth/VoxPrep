"""Voice Processing Router for VOXPREP Backend.

Milestone 1 (Phase 1: AI Services, Voice Pipeline, and Authentication)
Authoritative references:
- docs/01_ARCHITECTURE.md (Voice Pipeline: STT -> LLM -> TTS)
- docs/03_PHASE_PLAN.md (Phase 1 Deliverables)
- docs/07_GUARDRAILS.md (Voice fallbacks & error handling)
- ORIGINAL_REQUEST.md (R2: Voice Pipeline)
"""

import base64
import logging
from typing import Optional
from fastapi import APIRouter, File, Form, UploadFile, status
from pydantic import BaseModel

from app.services import llm, stt, tts

logger = logging.getLogger("voxprep.voice")

router = APIRouter(tags=["Voice Pipeline"])

FALLBACK_STT_PROMPT = "Could not understand. Please try again."


class VoiceProcessResponse(BaseModel):
    """Structured response model for voice processing pipeline."""

    transcript: str
    spoken_response: str
    audio_base64: Optional[str] = None
    session_id: Optional[str] = None


@router.post(
    "/process",
    response_model=VoiceProcessResponse,
    status_code=status.HTTP_200_OK,
    summary="End-to-end voice pipeline: STT -> LLM -> TTS",
)
async def process_voice(
    file: UploadFile = File(..., description="WAV/audio blob recorded from client microphone"),
    agent_type: Optional[str] = Form("interview", description="Target agent mode: 'interview' or 'coach'"),
    session_id: Optional[str] = Form(None, description="Optional active session identifier"),
    conversation_history: Optional[str] = Form(None, description="Optional conversation context or history"),
) -> VoiceProcessResponse:
    """Processes spoken audio through the complete VOXPREP voice loop:

    1. STT: Transcribes audio bytes via NVIDIA Parakeet ASR.
    2. Guardrail Check: If audio is empty, corrupt, or unparseable, returns a friendly prompt without 500 crash.
    3. LLM: Generates contextual reply via NVIDIA Nemotron 70B (Interview or Coach persona).
    4. TTS: Synthesizes spoken reply via NVIDIA Magpie TTS into WAV bytes.
    5. Fallback: If TTS is unavailable, returns audio_base64=None so frontend falls back to Web Speech API.
    """
    try:
        content = await file.read()
    except Exception as exc:
        logger.warning(f"Failed to read uploaded audio file: {exc}")
        return VoiceProcessResponse(
            transcript="",
            spoken_response=FALLBACK_STT_PROMPT,
            audio_base64=None,
            session_id=session_id,
        )

    # Boundary check: 0-byte or trivial payloads
    if not content or len(content) < 12:
        logger.warning("Empty or truncated audio payload received.")
        return VoiceProcessResponse(
            transcript="",
            spoken_response=FALLBACK_STT_PROMPT,
            audio_base64=None,
            session_id=session_id,
        )

    # 1. Speech-to-Text (STT)
    transcript = await stt.transcribe(content)
    if not transcript or not transcript.strip():
        logger.warning("STT transcription returned None or empty string.")
        return VoiceProcessResponse(
            transcript="",
            spoken_response=FALLBACK_STT_PROMPT,
            audio_base64=None,
            session_id=session_id,
        )

    clean_transcript = transcript.strip()

    # 2. LLM Dialog Response Generation
    normalized_agent = (agent_type or "interview").lower()
    if normalized_agent == "coach":
        system_prompt = (
            "You are VOXPREP AI Communication Coach. Provide supportive, concise feedback "
            "and continue the conversation in 1-2 spoken sentences."
        )
    else:
        system_prompt = (
            "You are VOXPREP AI Interviewer. Respond professionally and ask a relevant "
            "interview question in 1-2 spoken sentences."
        )

    messages = [{"role": "user", "content": clean_transcript}]
    spoken_response = await llm.chat(messages=messages, system_prompt=system_prompt)

    if not spoken_response or not spoken_response.strip():
        spoken_response = (
            "Thank you for your response. Could you please elaborate further on that topic?"
        )

    clean_spoken_response = spoken_response.strip()

    # 3. Text-to-Speech (TTS)
    audio_bytes = await tts.synthesize(clean_spoken_response)
    audio_base64: Optional[str] = None
    if audio_bytes and len(audio_bytes) > 0:
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
    else:
        logger.info("TTS returned None; frontend will utilize Web Speech API fallback.")

    return VoiceProcessResponse(
        transcript=clean_transcript,
        spoken_response=clean_spoken_response,
        audio_base64=audio_base64,
        session_id=session_id,
    )
