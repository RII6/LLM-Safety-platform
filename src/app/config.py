"""Runtime configuration for the scanner app.

The tunable values live in ``configs/general.yaml`` (the ``scanner:`` section),
alongside the module configs. This file is just the loader: it reads that YAML
and lets environment variables override any value — precedence is
**env > yaml > built-in default** — then resolves paths and the torch dtype.

The import surface is unchanged: code keeps using ``config.SAMPLE``,
``config.DEVICE``, ``config.DATABASE_URL`` and so on.
"""
import os
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS = ROOT / "src" / "data" / "corpus"
GEN_CACHE = ROOT / "reports" / "cache"

MAX_PARAMS = int(os.getenv("SCAN_MAX_PARAMS", "400000000"))
MAX_WEIGHT_BYTES = MAX_PARAMS * 4
SAMPLE = int(os.getenv("SCAN_SAMPLE", "25"))

DEVICE = os.getenv("SCAN_DEVICE")
if not DEVICE:
    if torch.cuda.is_available():
        DEVICE = "cuda"
    elif torch.backends.mps.is_available():
        DEVICE = "mps"
    else:
        DEVICE = "cpu"

_dtype_str = os.getenv("SCAN_DTYPE", "auto" if DEVICE != "cpu" else "float32")
if _dtype_str == "auto":
    DTYPE = "auto"
elif _dtype_str == "bfloat16":
    DTYPE = torch.bfloat16
elif _dtype_str == "float16":
    DTYPE = torch.float16
else:
    DTYPE = torch.float32

DEMO_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
GEN_N = 5
GEN_PROVIDER = "groq"
GEN_MODEL = None
GEN_SEED = 42
GEN_CLASS = "harmful"

AUTH_SECRET = os.getenv("AUTH_SECRET", "dev-insecure-change-me")
AUTH_TOKEN_TTL = int(os.getenv("AUTH_TOKEN_TTL", "86400"))
AUTH_PBKDF2_ITERATIONS = int(os.getenv("AUTH_PBKDF2_ITERATIONS", "200000"))

_origins = os.getenv("AUTH_CORS_ORIGINS", "*")
AUTH_CORS_ORIGINS = [x.strip() for x in _origins.split(",") if x.strip()]