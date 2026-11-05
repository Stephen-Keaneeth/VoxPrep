# ==============================================================================
# VOXPREP Backend - Production Dockerfile
# Base: Python 3.12 Slim (Debian Bookworm)
# Security: Non-root execution (appuser:appuser, UID 1001)
# ==============================================================================

FROM python:3.12-slim AS runtime

# Default container environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    PYTHONPATH=/app

# Install minimal OS dependencies for health check and clean apt cache
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated unprivileged user and group
RUN groupadd -r appuser && useradd -r -u 1001 -g appuser -d /app -s /sbin/nologin appuser

# Set working directory
WORKDIR /app

# Layer Caching Optimization: copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source code and schema
COPY app/ ./app/
COPY schema.sql .

# Ensure app directory permissions belong to non-root appuser
RUN chown -R appuser:appuser /app

# Switch to non-root execution
USER appuser

# Expose default application port (overridden by Railway $PORT at runtime)
EXPOSE 8000

# Container healthcheck instruction calling curl
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Production entrypoint: uvicorn binding to dynamic $PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
