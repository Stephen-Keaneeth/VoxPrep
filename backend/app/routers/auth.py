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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

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
