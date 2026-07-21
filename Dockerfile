# Stage 1: Build the frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Build the backend and final image
FROM python:3.11-slim

RUN groupadd -r appuser && useradd -r -m -g appuser appuser
WORKDIR /app
RUN chown appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    HF_HOME="/app/cache"

COPY --chown=appuser:appuser pyproject.toml ./
RUN python -m venv .venv && \
    .venv/bin/pip install --no-cache-dir "torch>=2.12.0" --extra-index-url https://download.pytorch.org/whl/cpu && \
    .venv/bin/pip install --no-cache-dir "openai>=1.0.0" "pyyaml>=6.0" "fastapi>=0.115.0" "uvicorn>=0.30.0" "huggingface-hub>=0.34.0" "psycopg[binary]>=3.1" "transformers>=5.12.0" "datasets>=5.0.0"

COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser generate.py ./
COPY --chown=appuser:appuser configs/ ./configs/
COPY --chown=appuser:appuser data/corpus/ ./data/corpus/

COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/dist ./app/static/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
