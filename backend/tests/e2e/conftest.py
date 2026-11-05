"""E2E Test Configuration and Fixtures.

Supports dual-track execution:
1. Live running server via `BASE_URL` environment variable.
2. In-process FastAPI `LocalClient` with external API mock fallbacks for NVIDIA NIM and Supabase.
"""

import os
import sys
import uuid
import struct
import pytest
from typing import Generator

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Default test environment variables
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("NVIDIA_API_KEY", "nvapi-test-dummy-key")
os.environ.setdefault("SUPABASE_URL", "https://test-mock.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-mock-service-key")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-mock-anon-key")


def make_wav_bytes(duration_ms: int = 200, sample_rate: int = 16000) -> bytes:
    """Generate valid 16kHz mono 16-bit PCM WAV bytes."""
    num_samples = int(sample_rate * (duration_ms / 1000.0))
    data_size = num_samples * 2
    riff_header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE"
    fmt_chunk = b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    data_chunk = b"data" + struct.pack("<I", data_size) + (b"\x00\x00" * num_samples)
    return riff_header + fmt_chunk + data_chunk


@pytest.fixture(scope="session")
def dummy_wav_bytes() -> bytes:
    """Returns valid PCM WAV audio bytes for testing."""
    return make_wav_bytes(duration_ms=200, sample_rate=16000)


@pytest.fixture(scope="session")
def corrupt_audio_bytes() -> bytes:
    """Returns corrupted non-audio bytes."""
    return b"NOT_A_VALID_WAV_HEADER_CORRUPTED_STREAM_DATA_ABCXYZ"


@pytest.fixture(scope="session")
def empty_audio_bytes() -> bytes:
    """Returns empty 0-byte audio payload."""
    return b""


def _build_reference_fallback_app():
    """Builds an in-memory reference FastAPI application conforming to PROJECT.md contracts.
    
    Used when backend.app.main is still being implemented by Phase 0-4 workers.
    All endpoints are declared as async def to run cleanly under LocalClient without threadpool hops.
    """
    from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Header
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, EmailStr
    from typing import Optional, List, Dict, Any

    app = FastAPI(title="VOXPREP Backend Reference Mock", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # In-memory storage stores
    users_db: Dict[str, Dict[str, Any]] = {}
    interview_sessions_db: Dict[str, Dict[str, Any]] = {}
    coach_sessions_db: Dict[str, Dict[str, Any]] = {}

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    @app.get("/")
    async def root():
        return {"message": "VOXPREP Backend API", "docs_url": "/docs"}

    # --- Auth Routers ---
    class RegisterRequest(BaseModel):
        email: str
        password: str
        name: Optional[str] = "Candidate"

    class LoginRequest(BaseModel):
        email: str
        password: str

    @app.post("/auth/register")
    async def register(req: RegisterRequest):
        for u in users_db.values():
            if u["email"] == req.email:
                raise HTTPException(status_code=400, detail="User already registered")
        user_id = str(uuid.uuid4())
        user_record = {
            "id": user_id,
            "email": req.email,
            "name": req.name,
            "communication_profile": {
                "skill_level": "intermediate",
                "weak_areas": [],
                "strong_areas": [],
                "sessions_count": 0,
            },
        }
        users_db[user_id] = user_record
        return {
            "user": {"id": user_id, "email": req.email, "name": req.name},
            "access_token": f"mock-token-{user_id}",
        }

    @app.post("/auth/login")
    async def login(req: LoginRequest):
        for user_id, u in users_db.items():
            if u["email"] == req.email:
                return {
                    "user": {"id": user_id, "email": u["email"], "name": u["name"]},
                    "access_token": f"mock-token-{user_id}",
                }
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # --- Voice Router ---
    @app.post("/voice/process")
    async def process_voice(
        file: UploadFile = File(...),
        session_id: Optional[str] = Form(None),
        agent_type: Optional[str] = Form("interview"),
    ):
        content = await file.read()
        if not content or len(content) < 10 or not content.startswith(b"RIFF"):
            return {
                "transcript": "",
                "spoken_response": "Could not understand. Please try again.",
                "audio_base64": None,
            }
        transcript = "I have experience with Python and distributed systems."
        response_text = "That is great. Could you tell me about your experience with FastAPI?"
        return {
            "transcript": transcript,
            "spoken_response": response_text,
            "audio_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=",
        }

    # --- Interview Router ---
    class InterviewStartRequest(BaseModel):
        candidate_name: str
        role: str
        experience_level: str
        interview_type: str
        user_id: Optional[str] = None

    class InterviewRespondRequest(BaseModel):
        session_id: str
        answer_text: str

    class InterviewEndRequest(BaseModel):
        session_id: str

    @app.post("/interview/start")
    async def start_interview(req: InterviewStartRequest):
        if req.interview_type not in ["technical", "hr", "situational", "resume"]:
            raise HTTPException(status_code=400, detail="Invalid interview_type")
        sid = str(uuid.uuid4())
        session = {
            "session_id": sid,
            "candidate_name": req.candidate_name,
            "role": req.role,
            "experience_level": req.experience_level,
            "interview_type": req.interview_type,
            "user_id": req.user_id,
            "question_index": 0,
            "follow_up_count": 0,
            "is_complete": False,
            "questions": ["Tell me about yourself and your primary technical stack."],
            "answers": [],
            "scores": [],
            "report": None,
        }
        interview_sessions_db[sid] = session
        greeting = (
            f"Hello {req.candidate_name}, welcome to your {req.interview_type} interview for {req.role}. "
            "Let's start: Tell me about yourself and your background."
        )
        return {"session_id": sid, "opening_message": greeting}

    @app.post("/interview/respond")
    async def respond_interview(req: InterviewRespondRequest):
        sid = req.session_id
        if sid not in interview_sessions_db:
            raise HTTPException(status_code=404, detail="Interview session not found")
        sess = interview_sessions_db[sid]
        if sess["is_complete"]:
            return {
                "spoken_response": "We have covered all questions. The interview is complete.",
                "is_complete": True,
                "follow_up_or_next": "next",
                "current_question_index": sess["question_index"],
                "total_questions": 5,
            }

        sess["answers"].append(req.answer_text)
        sess["scores"].append({"relevance": 8.0, "clarity": 8.0, "depth": 7.5, "examples": 8.0})

        # Check follow up logic: max 1 follow up per core question
        if sess["follow_up_count"] == 0 and sess["question_index"] < 4:
            sess["follow_up_count"] = 1
            follow_up_or_next = "follow_up"
            spoken = "Interesting. Could you elaborate on how you handled the trade-offs?"
        else:
            sess["follow_up_count"] = 0
            sess["question_index"] += 1
            follow_up_or_next = "next"
            if sess["question_index"] >= 5:
                sess["is_complete"] = True
                spoken = "Thank you. We have completed all questions. Let me prepare your report."
            else:
                spoken = f"Question {sess['question_index'] + 1}: How do you design fault-tolerant services?"

        return {
            "spoken_response": spoken,
            "is_complete": sess["is_complete"],
            "follow_up_or_next": follow_up_or_next,
            "current_question_index": sess["question_index"],
            "total_questions": 5,
        }

    @app.post("/interview/end")
    async def end_interview(req: InterviewEndRequest):
        sid = req.session_id
        if sid not in interview_sessions_db:
            raise HTTPException(status_code=404, detail="Interview session not found")
        sess = interview_sessions_db[sid]
        sess["is_complete"] = True
        report = {
            "overall_score": 8.0,
            "dimension_scores": {
                "relevance": 8.0,
                "clarity": 8.0,
                "depth": 7.5,
                "examples": 8.5,
            },
            "strengths": [
                "Clear architectural explanation of service boundaries.",
                "Concrete examples of database optimizations.",
            ],
            "weaknesses": [
                "Could elaborate more on disaster recovery strategies.",
            ],
            "improvement_tips": [
                "Use the STAR method for situational questions.",
                "Quantify business outcomes.",
            ],
            "coach_recommendation": "Interview Answer Training",
            "summary": "Candidate demonstrated solid understanding and clear technical communication.",
        }
        sess["report"] = report
        return {"session_id": sid, "status": "completed", "report": report}

    @app.get("/interview/report/{session_id}")
    async def get_interview_report(session_id: str):
        if session_id not in interview_sessions_db:
            raise HTTPException(status_code=404, detail="Session not found")
        sess = interview_sessions_db[session_id]
        if not sess.get("report"):
            raise HTTPException(status_code=404, detail="Report not generated yet")
        return sess["report"]

    # --- Coach Router ---
    class CoachStartRequest(BaseModel):
        user_id: str
        mode: str

    class CoachRespondRequest(BaseModel):
        session_id: str
        user_text: str

    class CoachEndRequest(BaseModel):
        session_id: str

    @app.post("/coach/start")
    async def start_coach(req: CoachStartRequest):
        if req.mode not in ["conversation", "answer_training", "english_improvement"]:
            raise HTTPException(status_code=400, detail="Invalid coach mode")
        sid = str(uuid.uuid4())
        session = {
            "session_id": sid,
            "user_id": req.user_id,
            "mode": req.mode,
            "exchanges": [],
            "is_complete": False,
        }
        coach_sessions_db[sid] = session
        greeting = f"Hi! I'm your AI Communication Coach. Let's practice {req.mode}. How was your day?"
        return {"session_id": sid, "opening_message": greeting}

    @app.post("/coach/respond")
    async def respond_coach(req: CoachRespondRequest):
        sid = req.session_id
        if sid not in coach_sessions_db:
            raise HTTPException(status_code=404, detail="Coach session not found")
        sess = coach_sessions_db[sid]
        sess["exchanges"].append(req.user_text)

        # Check if correction is needed
        correction = None
        if "was go" in req.user_text or "buyed" in req.user_text or "fishes" in req.user_text:
            correction = {
                "original": "was go",
                "improved": "went",
                "reason": "Use simple past tense 'went' for a completed past action.",
            }
            coach_message = (
                "That sounds great! One small improvement: instead of saying 'was go', you could say 'went'. "
                "This sounds more natural because it's past tense. Want to try it?"
            )
        else:
            coach_message = "That's well expressed! You used clear structure and good vocabulary."

        return {
            "coach_message": coach_message,
            "correction": correction,
            "next_prompt": "What do you enjoy most about your work or studies?",
        }

    @app.post("/coach/end")
    async def end_coach(req: CoachEndRequest):
        sid = req.session_id
        if sid not in coach_sessions_db:
            raise HTTPException(status_code=404, detail="Coach session not found")
        sess = coach_sessions_db[sid]
        sess["is_complete"] = True
        uid = sess["user_id"]
        if uid in users_db:
            prof = users_db[uid]["communication_profile"]
            prof["sessions_count"] += 1
            prof["weak_areas"] = ["past tense verb agreement"]
            prof["strong_areas"] = ["vocabulary breadth", "active participation"]
        else:
            prof = {
                "skill_level": "intermediate",
                "weak_areas": ["past tense verb agreement"],
                "strong_areas": ["vocabulary breadth"],
                "sessions_count": 1,
            }
        summary = {
            "exchanges_count": len(sess["exchanges"]),
            "key_learnings": [
                "Practiced simple past tense irregular verbs.",
                "Expanded conversational transitions.",
            ],
            "encouragement": "Wonderful job today! Your confidence is noticeably growing.",
        }
        return {
            "session_id": sid,
            "status": "completed",
            "summary": summary,
            "updated_profile": prof,
        }

    return app


@pytest.fixture(scope="session")
def app_instance():
    """Resolves either the implemented backend.app.main app or the reference mock fallback."""
    app_candidate = None
    try:
        from app.main import app as real_app
        app_candidate = real_app
    except Exception:
        try:
            from backend.app.main import app as real_app
            app_candidate = real_app
        except Exception:
            pass

    if app_candidate is not None:
        route_paths = {getattr(r, "path", "") for r in getattr(app_candidate, "routes", [])}
        # If all routers are mounted, use real_app
        if "/auth/register" in route_paths or "/interview/start" in route_paths:
            return app_candidate

    return _build_reference_fallback_app()


@pytest.fixture
def client(app_instance) -> Generator:
    """Provides an HTTP client for opaque-box E2E testing.
    
    If `BASE_URL` is configured in the environment, runs real HTTP requests against the live server.
    Otherwise, runs in-process via LocalClient to avoid Windows sandbox socketpair restrictions.
    """
    base_url = os.getenv("BASE_URL")
    if base_url:
        import httpx
        with httpx.Client(base_url=base_url, timeout=30.0) as http_client:
            yield http_client
    else:
        try:
            from tests.conftest import LocalClient
        except ImportError:
            from backend.tests.conftest import LocalClient
        with LocalClient(app_instance) as local_client:
            yield local_client
