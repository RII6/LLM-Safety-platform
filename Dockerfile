FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

LABEL IMAGE_CONTAINER_METADATA_VERSION=1.0.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./

RUN uv venv && \
    . .venv/bin/activate && \
    uv pip install torch --index-url https://pytorch.org && \
    uv pip install vllm>=0.7.0 && \
    uv sync

COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.app.server:app", "--host", "0.0.0.0", "--port", "8000"]