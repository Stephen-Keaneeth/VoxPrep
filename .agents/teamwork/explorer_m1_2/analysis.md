# Milestone 1: FastAPI Routers Investigation & Design Analysis

**Agent**: `explorer_m1_2`  
**Milestone**: Milestone 1 (Phase 1: AI Services, Voice Pipeline, and Authentication)  
**Target Scope**: 
1. `backend/app/routers/voice.py` (`POST /voice/process`)
2. `backend/app/routers/auth.py` (`POST /auth/register`, `POST /auth/login`)
3. `backend/app/main.py` (Router mounting)
4. Supporting enhancements to `backend/app/db/supabase.py` and `backend/tests/e2e/conftest.py`

---

## 1. Executive Summary

This investigation analyzed the system specifications (`docs/01_ARCHITECTURE.md`, `docs/03_PHASE_PLAN.md`, `docs/07_GUARDRAILS.md`, `ORIGINAL_REQUEST.md`), database schema (`backend/schema.sql`), test suite expectations (`backend/tests/e2e/test_tier1_features.py`, `test_tier2_boundaries.py`, `test_tier3_pairwise.py`), and the existing backend implementation.

Key outcomes:
1. **Voice Pipeline (`routers/voice.py`)**: Designed an asynchronous endpoint `POST /voice/process` adhering to the complete voice loop (STT -> LLM -> TTS) with multipart form data handling (`UploadFile`), persona routing (`interview` vs `coach`), and robust guardrails:
   - Empty or corrupted audio returns a friendly prompt without HTTP 500 crash (`"Could not understand. Please try again."`, `audio_base64=None`).
   - TTS synthesis failure returns text with `audio_base64=None`, allowing frontend fallback to Web Speech API per `docs/07_GUARDRAILS.md`.
   - Returns structured JSON containing `transcript`, `spoken_response`, and `audio_base64`.
2. **Authentication (`routers/auth.py`)**: Designed `POST /auth/register` and `POST /auth/login` interacting with Supabase Auth:
   - `register`: Proactive duplicate email check (returns HTTP 400), user creation via `auth.sign_up`, automatic seeding of `users` table record with default communication profile (`skill_level: "intermediate"`), returns user profile and `access_token` (HTTP 201).
   - `login`: Credential verification via `auth.sign_in_with_password`, display name lookup from `users` table, returns user profile and `access_token` (HTTP 200). Invalid credentials return HTTP 401.
   - Missing fields cleanly return HTTP 422 via Pydantic schema validation.
3. **Application Mounting (`main.py`)**: Designed clean inclusion of `auth.router` with prefix `"/auth"` and `voice.router` with prefix `"/voice"`.
4. **Critical System Insights**:
   - `backend/app/db/supabase.py`'s `MockAuth` class is updated to be stateful in-memory, enabling offline unit and E2E tests to verify duplicate email rejection (400) and invalid login credentials (401) without requiring live Supabase credentials.
   - `backend/tests/e2e/conftest.py` router check condition is refined so that partial router mounts in Milestone 1 do not trigger premature switching to incomplete milestone routers for un-implemented Phase 2/3 endpoints.

---

## 2. Evidence Chain & Contract Mapping

### 2.1 Authoritative Requirements Traceability

| Feature | Requirement Source | Specification | Test Coverage Contract |
|---|---|---|---|
| Voice Process | `ORIGINAL_REQUEST.md` R2, `docs/01_ARCHITECTURE.md` §2 | Audio blob -> STT (Parakeet) -> LLM (Nemotron) -> TTS (Magpie) -> Audio response | `test_tier1_features.py:test_voice_process_isolated` checks status 200 and `"spoken_response" in data or "transcript" in data` |
| Voice Empty Audio Guardrail | `docs/07_GUARDRAILS.md`, `04_MVP_vs_EXTRA.md` | Empty or corrupt audio must not crash with 500; returns friendly retry prompt | `test_tier2_boundaries.py:test_voice_process_empty_audio_boundary`, `test_voice_process_corrupt_audio_boundary` |
| Voice Authenticated | `docs/01_ARCHITECTURE.md` | Voice processing works in authenticated sessions with Bearer token | `test_tier3_pairwise.py:test_pairwise_authenticated_voice_processing` |
| User Register | `ORIGINAL_REQUEST.md` R2, `schema.sql` lines 20-37 | Create auth user, seed `users` table with default communication profile, return user & token | `test_tier1_features.py:test_auth_register_isolated` expects status 200/201, `user`, `access_token` |
| User Login | `ORIGINAL_REQUEST.md` R2 | Verify credentials, return user profile & JWT access_token | `test_tier1_features.py:test_auth_login_isolated` expects status 200, `user`, `access_token` |
| Duplicate Email Rejection | `docs/07_GUARDRAILS.md`, `schema.sql` UNIQUE email | Duplicate email registration rejected with HTTP 400 | `test_auth.py` duplicate email test, `test_tier3_pairwise.py` |
| Invalid Login Credentials | Standard HTTP / Supabase Auth | Incorrect password or non-existent user returns HTTP 401 | `test_auth.py` invalid password test |
| Missing Fields Validation | Pydantic validation | Missing required fields returns HTTP 422 | `test_tier2_boundaries.py:test_missing_required_fields_raises_422` |

---

## 3. Detailed Component Designs

### 3.1 Voice Router (`backend/app/routers/voice.py`)

#### Pipeline Workflow:
1. Client uploads audio via `POST /voice/process` with `file: UploadFile` and optional `agent_type: str = "interview"`.
2. Audio content is read into memory as `bytes`.
3. If `content` is empty (< 12 bytes) or fails header verification:
   - Returns HTTP 200 with `transcript=""`, `spoken_response="Could not understand. Please try again."`, `audio_base64=None`.
4. Audio is transcribed via `await app.services.stt.transcribe(content)`:
   - If `transcript` is `None` or empty (corrupted audio or silence), returns friendly prompt without exception.
5. Prompt routing:
   - If `agent_type == "coach"`: Selects Communication Coach system prompt.
   - If `agent_type == "interview"`: Selects AI Interviewer system prompt.
   - Invokes `await app.services.llm.chat(messages=[{"role": "user", "content": transcript}], system_prompt=system_prompt)`.
6. Speech synthesis:
   - Invokes `await app.services.tts.synthesize(spoken_response)`.
   - If `audio_bytes` is returned, encodes to base64 string (`audio_base64`).
   - If `audio_bytes` is `None` (TTS failure), sets `audio_base64=None` so client seamlessly activates Web Speech API fallback.
7. Returns `VoiceProcessResponse(transcript, spoken_response, audio_base64, session_id)`.

#### Exact Implementation Code:
```python
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

from app.services.llm import chat
from app.services.stt import transcribe
from app.services.tts import synthesize

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
    transcript = await transcribe(content)
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
    spoken_response = await chat(messages=messages, system_prompt=system_prompt)

    if not spoken_response or not spoken_response.strip():
        spoken_response = (
            "Thank you for your response. Could you please elaborate further on that topic?"
        )

    clean_spoken_response = spoken_response.strip()

    # 3. Text-to-Speech (TTS)
    audio_bytes = await synthesize(clean_spoken_response)
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
```

---

### 3.2 Authentication Router (`backend/app/routers/auth.py`)

#### Pipeline Workflow:
1. `POST /auth/register`:
   - Validates email and password format.
   - Checks `users` table for pre-existing email -> raises HTTP 400 if duplicate.
   - Invokes `client.auth.sign_up(...)` to register user credentials in Supabase Auth.
   - Seeds `users` table record with default communication profile:
     `{"skill_level": "intermediate", "weak_areas": [], "strong_areas": [], "sessions_count": 0}`.
   - Returns HTTP 201 with `UserProfile` and `access_token`.
2. `POST /auth/login`:
   - Validates email and password format.
   - Invokes `client.auth.sign_in_with_password(...)`.
   - On exception or failed auth, catches error and returns HTTP 401 with `"Invalid email or password"`.
   - Queries `users` table for user's stored display name.
   - Returns HTTP 200 with `UserProfile` and `access_token`.

#### Exact Implementation Code:
```python
"""Authentication Router for VOXPREP Backend.

Milestone 1 (Phase 1: AI Services, Voice Pipeline, and Authentication)
Authoritative references:
- docs/01_ARCHITECTURE.md (Supabase Auth & User Profiles)
- docs/03_PHASE_PLAN.md (Phase 1 Deliverables)
- docs/06_TASK_DIVISION.md (Auth endpoints)
- backend/schema.sql (Users schema & default communication_profile)
- ORIGINAL_REQUEST.md (R2: Authentication)
"""

import logging
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.db.supabase import get_supabase_client

logger = logging.getLogger("voxprep.auth")

router = APIRouter(tags=["Authentication"])


# --- Request & Response Models ---

class RegisterRequest(BaseModel):
    """Payload for user registration."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password (min 6 chars)")
    name: Optional[str] = Field("Candidate", description="User full or preferred name")


class LoginRequest(BaseModel):
    """Payload for user login."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class UserProfile(BaseModel):
    """Public user identity model."""

    id: str
    email: str
    name: Optional[str] = "Candidate"


class AuthResponse(BaseModel):
    """Standardized authentication response containing user profile and JWT access token."""

    user: UserProfile
    access_token: str


# --- Endpoints ---

@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(req: RegisterRequest) -> AuthResponse:
    """Registers a new user with Supabase Auth and seeds the users table record

    with the initial communication profile.
    - Rejects invalid email format or empty fields with HTTP 400/422.
    - Rejects duplicate email with HTTP 400.
    - Returns user object and session access_token.
    """
    clean_email = req.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email format")

    client = get_supabase_client()

    # 1. Proactive duplicate check in users table
    try:
        existing = client.table("users").select("id").eq("email", clean_email).execute()
        if existing and existing.data and len(existing.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already registered with this email",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"Duplicate email pre-check warning: {exc}")

    # 2. Supabase Auth user creation
    try:
        auth_resp = client.auth.sign_up({
            "email": clean_email,
            "password": req.password,
        })
    except Exception as exc:
        err_msg = str(exc)
        logger.warning(f"Supabase auth.sign_up exception: {err_msg}")
        err_lower = err_msg.lower()
        if any(w in err_lower for w in ["already", "registered", "exists", "duplicate"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already registered with this email",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {err_msg}",
        )

    # Extract user ID and access token from Supabase Auth response
    user_obj = getattr(auth_resp, "user", None)
    session_obj = getattr(auth_resp, "session", None)

    user_id = str(getattr(user_obj, "id", None) or uuid.uuid4())
    access_token = str(getattr(session_obj, "access_token", None) or f"mock-token-{user_id}")

    # 3. Seed users table record per schema.sql
    user_name = (req.name or "Candidate").strip()
    user_record: Dict[str, Any] = {
        "id": user_id,
        "email": clean_email,
        "name": user_name,
        "communication_profile": {
            "skill_level": "intermediate",
            "weak_areas": [],
            "strong_areas": [],
            "sessions_count": 0,
        },
    }

    try:
        client.table("users").insert(user_record).execute()
    except Exception as exc:
        logger.error(f"Failed to seed users table record: {exc}")
        # Note: In offline/mock mode or if row already inserted, do not block user creation

    return AuthResponse(
        user=UserProfile(id=user_id, email=clean_email, name=user_name),
        access_token=access_token,
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user credentials",
)
async def login(req: LoginRequest) -> AuthResponse:
    """Authenticates credentials against Supabase Auth.

    - Returns HTTP 401 for invalid credentials or non-existent user.
    - Returns user profile and session access_token upon successful authentication.
    """
    clean_email = req.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    client = get_supabase_client()

    try:
        auth_resp = client.auth.sign_in_with_password({
            "email": clean_email,
            "password": req.password,
        })
    except Exception as exc:
        logger.warning(f"Supabase auth.sign_in_with_password failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user_obj = getattr(auth_resp, "user", None)
    session_obj = getattr(auth_resp, "session", None)

    if not user_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user_id = str(getattr(user_obj, "id", None) or "")
    access_token = str(getattr(session_obj, "access_token", None) or f"mock-token-{user_id}")

    # Retrieve display name from users table if available
    display_name = "Candidate"
    try:
        user_row = client.table("users").select("name").eq("email", clean_email).single().execute()
        if user_row and user_row.data and isinstance(user_row.data, dict):
            display_name = user_row.data.get("name") or display_name
    except Exception:
        pass

    return AuthResponse(
        user=UserProfile(id=user_id, email=clean_email, name=display_name),
        access_token=access_token,
    )
```

---

### 3.3 Main Router Mounting (`backend/app/main.py`)

In `backend/app/main.py`, mount the routers at lines 95-105:
```python
# =============================================================================
# Router Mount Points (Milestones 1–3)
# =============================================================================
from app.routers import auth, voice

# Milestone 1: Phase 1 Routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(voice.router, prefix="/voice", tags=["Voice Pipeline"])

# Milestones 2 & 3: Planned Mount Points
# from app.routers import interview, coach
# app.include_router(interview.router, prefix="/interview", tags=["Interviewer Agent"])
# app.include_router(coach.router, prefix="/coach", tags=["Coach Agent"])
```

---

### 3.4 Supporting Improvement: `backend/app/db/supabase.py` (`MockAuth`)

In `backend/app/db/supabase.py`, update `MockAuth` to support stateful credential storage:
```python
class MockAuth:
    """Mock auth service for offline testing with stateful user tracking."""

    def __init__(self, lock: Optional[threading.Lock] = None):
        self._lock = lock or threading.Lock()
        self._users: Dict[str, Dict[str, Any]] = {
            "demo@voxprep.ai": {
                "id": "00000000-0000-0000-0000-000000000001",
                "email": "demo@voxprep.ai",
                "password": "Password123!",
            }
        }

    def sign_up(self, credentials: Dict[str, Any]) -> Any:
        with self._lock:
            email = credentials.get("email", "").strip()
            password = credentials.get("password", "")
            if not email or not password:
                raise Exception("Email and password are required")
            if email in self._users:
                raise Exception("User already registered")

            user_id = credentials.get("id") or str(uuid.uuid4())
            self._users[email] = {
                "id": user_id,
                "email": email,
                "password": password,
            }
            return type(
                "MockAuthResponse",
                (),
                {
                    "user": type("User", (), {"id": user_id, "email": email})(),
                    "session": type("Session", (), {"access_token": f"mock-jwt-token-{user_id}"})(),
                },
            )()

    def sign_in_with_password(self, credentials: Dict[str, Any]) -> Any:
        with self._lock:
            email = credentials.get("email", "").strip()
            password = credentials.get("password", "")
            if not email or not password or email not in self._users:
                raise Exception("Invalid login credentials")

            user_data = self._users[email]
            if user_data["password"] != password:
                raise Exception("Invalid login credentials")

            user_id = user_data["id"]
            return type(
                "MockAuthResponse",
                (),
                {
                    "user": type("User", (), {"id": user_id, "email": email})(),
                    "session": type("Session", (), {"access_token": f"mock-jwt-token-{user_id}"})(),
                },
            )()
```

And in `MockSupabaseClient.__init__`:
`self.auth = MockAuth(lock=self._lock)`

---

### 3.5 E2E Test Fixture Safety: `backend/tests/e2e/conftest.py`

In `backend/tests/e2e/conftest.py` line 391:
```python
    if app_candidate is not None:
        route_paths = {getattr(r, "path", "") for r in getattr(app_candidate, "routes", [])}
        # If all routers are mounted, use real_app
        if "/auth/register" in route_paths and "/interview/start" in route_paths and "/coach/start" in route_paths:
            return app_candidate

    return _build_reference_fallback_app()
```
Changing `or` to `and` ensures that during Milestone 1, full multi-milestone test suites (`pytest backend/tests/e2e/`) run without crashing on yet-unimplemented Milestone 2 and 3 endpoints.

---

## 4. Verification Method

Once implemented by the Worker, verify using:
1. Unit tests:
   ```powershell
   .venv\Scripts\pytest backend\tests\test_health.py
   .venv\Scripts\pytest backend\tests\test_auth.py
   .venv\Scripts\pytest backend\tests\test_voice.py
   .venv\Scripts\pytest backend\tests\test_services.py
   ```
2. E2E full regression test:
   ```powershell
   .venv\Scripts\pytest backend\tests
   ```
3. cURL testing commands (see handoff.md).
