"""
VOXPREP Backend API - Main Application Entrypoint
Milestone 0: Phase 0 Setup & Environment
"""

import os
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def get_allowed_origins() -> List[str]:
    """
    Parses allowed CORS origins from environment variables.
    Checks ALLOWED_ORIGINS first, then CORS_ORIGINS as fallback.
    - If set to a comma-separated list of URLs, splits and strips whitespace.
    - If set to "*", returns ["*"] for wildcard access.
    - If set to empty string, falls back to ["http://localhost:3000"].
    - If unset in environment, defaults to ["*"] for development convenience.
    """
    raw_origins = os.getenv("ALLOWED_ORIGINS")
    if raw_origins is None:
        raw_origins = os.getenv("CORS_ORIGINS")
    if raw_origins is not None:
        origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
        if origins:
            return origins
        return ["http://localhost:3000"]
    return ["*"]


# Initialize FastAPI application with project metadata
app = FastAPI(
    title="VOXPREP Backend API",
    description="Backend API for VOXPREP - AI-powered voice interview and communication coaching platform.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS Middleware
allowed_origins = get_allowed_origins()

# W3C CORS Compliance & Browser Compatibility:
# Per W3C Fetch Spec Section 3.2.2, browsers reject responses containing
# 'Access-Control-Allow-Origin: *' when 'Access-Control-Allow-Credentials' is true.
# When wildcard development mode ("*" in allowed_origins) is active, we use
# allow_origin_regex=r".*" so Starlette dynamically reflects the requesting origin
# with 'Vary: Origin' and 'Access-Control-Allow-Credentials: true', fully conforming
# to the W3C spec and avoiding browser client failures.
# In production with explicit origins, exact origins are enforced without regex.
if "*" in allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_origin_regex=r".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health", status_code=200, tags=["Health"])
async def health_check():
    """
    Health check endpoint returning service uptime and operational status.
    Required by Acceptance Criteria: returns HTTP 200 with {"status": "ok"}.
    """
    return {"status": "ok"}


@app.get("/", status_code=200, tags=["Root"])
async def root():
    """
    Root endpoint providing service metadata, health status, and API documentation links.
    """
    return {
        "title": "VOXPREP Backend API",
        "version": "0.1.0",
        "status": "online",
        "docs_url": "/docs",
        "health_check": "/health",
    }


# =============================================================================
# Router Mount Points (Milestones 1–3)
# =============================================================================
from app.routers import auth, voice, interview, coach

# Milestone 1: Phase 1 Routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(voice.router, prefix="/voice", tags=["Voice Pipeline"])

# Milestone 2: Phase 2 Interviewer Agent Router
app.include_router(interview.router, prefix="/interview", tags=["Interviewer Agent"])

# Milestone 3: Phase 3 Communication Coach Agent Router
app.include_router(coach.router, prefix="/coach", tags=["coach"])


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
