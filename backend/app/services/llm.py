"""NVIDIA Nemotron LLM Service Wrapper for VOXPREP Backend.
Milestone 1: Phase 1 AI Services, Voice Pipeline, and Authentication.

Wraps nvidia/llama-3.1-nemotron-70b-instruct using the OpenAI-compatible AsyncOpenAI SDK.
Implements single retry with backoff, friendly error fallback, and full offline mock mode.
"""

import asyncio
import json
import logging
import os
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
    """Executes chat completion with NVIDIA Nemotron 70B with retry and offline mock support.

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
                logger.error(
                    f"NVIDIA Nemotron call failed after {max_retries + 1} attempts: {exc}. Returning friendly fallback."
                )
                return FRIENDLY_ERROR_MESSAGE
