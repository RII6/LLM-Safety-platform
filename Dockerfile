# Stage 1: Build the frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY src/frontend/package*.json ./
RUN npm ci
COPY src/frontend/ ./
RUN npm run build

# Stage 2: Build the backend and final image
FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create user and group, set working directory and give ownership
RUN groupadd -r appuser && useradd -r -m -g appuser appuser
WORKDIR /app
RUN chown appuser:appuser /app

# Switch to non-root IMMEDIATELY (Best Practice)
USER appuser

# Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    HF_HOME="/app/cache"

# Setup virtual environment and install dependencies.
# We explicitly install the CPU version of torch first to keep the image lean.
COPY --chown=appuser:appuser pyproject.toml uv.lock ./
RUN uv venv && \
    uv pip install torch && \
    uv sync --no-dev

# Copy backend source code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser scripts/ ./scripts/

# Copy built frontend from Stage 1 into the static directory
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/dist ./src/app/static/

# Create a reports directory for cache fallback if DB is not used (just in case)
RUN mkdir -p reports cache

# Expose the API port
EXPOSE 8000

# Start FastAPI app
CMD ["uvicorn", "src.app.server:app", "--host", "0.0.0.0", "--port", "8000"]
