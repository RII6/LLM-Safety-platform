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

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus"
REPORTS = ROOT.parent / "reports"

# Path to the YAML config; override with SCAN_CONFIG if needed.
_CONFIG_PATH = Path(os.environ.get("SCAN_CONFIG", ROOT / "configs" / "general.yaml"))


def _load_section(name: str) -> dict:
    """Return a top-level section of the YAML config, or {} on any problem."""
    try:
        import yaml

        with open(_CONFIG_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return raw.get(name, {}) or {}
    except Exception:
        return {}


_cfg = _load_section("scanner")
_gen = _cfg.get("generation", {}) or {}


def _resolve(env_key: str, source: dict, key: str, default, cast=str):
    """Resolve one setting: env var, then YAML value, then default."""
    if env_key in os.environ:
        return cast(os.environ[env_key])
    if source.get(key) is not None:
        return cast(source[key])
    return default


# ── Scan params ────────────────────────────────────────────────────────────────
SAMPLE = _resolve("SCAN_SAMPLE", _cfg, "sample", 25, int)
MAX_PARAMS = _resolve("SCAN_MAX_PARAMS", _cfg, "max_params", 400_000_000, int)
MAX_WEIGHT_BYTES = _resolve("SCAN_MAX_WEIGHT_BYTES", _cfg, "max_weight_bytes", 1_500_000_000, int)
DEVICE = _resolve("SCAN_DEVICE", _cfg, "device", "cpu", str)

_DTYPES = {"float32": torch.float32, "float16": torch.float16, "bfloat16": torch.bfloat16}
DTYPE = _DTYPES[_resolve("SCAN_DTYPE", _cfg, "dtype", "bfloat16", str)]

DEMO_MODEL = _resolve("SCAN_DEMO_MODEL", _cfg, "demo_model", "HuggingFaceTB/SmolLM2-360M-Instruct", str)

# ── PostgreSQL ──────────────────────────────────────────────────────────────────
DATABASE_URL = _resolve(
    "DATABASE_URL", _cfg, "database_url", "postgresql://postgres:postgres@localhost:5432/aisafety", str
)

# ── Auth ────────────────────────────────────────────────────────────────────────
# Key used to sign session tokens. MUST be overridden in production (set
# AUTH_SECRET); the default is intentionally obvious so a misconfigured deploy is
# easy to spot. Token TTL is in seconds; PBKDF2 iterations tune password-hash cost.
AUTH_SECRET = _resolve("AUTH_SECRET", _cfg, "auth_secret", "dev-insecure-change-me", str)
AUTH_TOKEN_TTL = _resolve("AUTH_TOKEN_TTL", _cfg, "auth_token_ttl", 86_400, int)
AUTH_PBKDF2_ITERATIONS = _resolve("AUTH_PBKDF2_ITERATIONS", _cfg, "auth_pbkdf2_iterations", 200_000, int)

# Comma-separated list of allowed CORS origins for a separate frontend (e.g. the
# Vite dev server). "*" allows any origin; credentials are not used (Bearer token).
AUTH_CORS_ORIGINS = [
    o.strip()
    for o in _resolve("AUTH_CORS_ORIGINS", _cfg, "auth_cors_origins", "*", str).split(",")
    if o.strip()
]

# ── Dynamic test-case generation (scan-time corpus augmentation) ────────────────
GEN_N = _resolve("SCAN_GEN_N", _gen, "n", 0, int)
GEN_PROVIDER = _resolve("SCAN_GEN_PROVIDER", _gen, "provider", "groq", str)
GEN_MODEL = _resolve("SCAN_GEN_MODEL", _gen, "model", None, str) or None
GEN_SEED = _resolve("SCAN_GEN_SEED", _gen, "seed", 0, int)
GEN_CLASS = _resolve("SCAN_GEN_CLASS", _gen, "class", "harmful", str)
GEN_CACHE = CORPUS / "generated"
