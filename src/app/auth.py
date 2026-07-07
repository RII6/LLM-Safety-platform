"""app/auth.py — password hashing, signed session tokens, and the FastAPI
dependency that resolves the current user from a request.

Crypto is intentionally stdlib-only (no bcrypt / PyJWT):

* passwords are hashed with PBKDF2-HMAC-SHA256 and a per-user random salt, stored
  as ``pbkdf2_sha256$<iterations>$<salt>$<hash>`` so the cost is self-describing;
* tokens are a compact ``<payload>.<signature>`` pair, the payload base64url-encoded
  JSON and the signature an HMAC-SHA256 over it keyed by ``config.AUTH_SECRET``.

Both verifications use ``hmac.compare_digest`` for constant-time comparison. This
keeps the app dependency-light; swap in bcrypt/PyJWT here without touching callers.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config, db

# ── base64url helpers (no padding, url-safe) ────────────────────────────────────


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ── passwords ───────────────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    """Return a self-describing PBKDF2 hash string for *password*."""
    if not password:
        raise ValueError("password must not be empty")
    iterations = config.AUTH_PBKDF2_ITERATIONS
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64e(salt)}${_b64e(dk)}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of *password* against a stored PBKDF2 hash string."""
    try:
        algo, iterations, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _b64d(salt_b64), int(iterations)
        )
        return hmac.compare_digest(dk, _b64d(hash_b64))
    except Exception:
        return False


# ── tokens ──────────────────────────────────────────────────────────────────────


def _sign(payload_b64: str) -> str:
    sig = hmac.new(config.AUTH_SECRET.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256)
    return _b64e(sig.digest())


def create_token(user_id: int, username: str, ttl: Optional[int] = None) -> str:
    """Issue a signed token for *user_id* that expires after *ttl* seconds."""
    now = int(time.time())
    payload = {
        "sub": int(user_id),
        "username": username,
        "iat": now,
        "exp": now + (config.AUTH_TOKEN_TTL if ttl is None else ttl),
    }
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(body)}"


def decode_token(token: str) -> Optional[dict]:
    """Return the token payload if the signature is valid and it hasn't expired."""
    try:
        body, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, _sign(body)):
            return None
        payload = json.loads(_b64d(body))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


# ── FastAPI dependency ──────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Resolve the authenticated user from the ``Authorization: Bearer`` header.

    Use as a dependency on any route that requires a logged-in user; it returns
    the public user record (id, username, email, created_at) or raises 401.
    """
    if creds is None or not creds.credentials:
        raise _unauthorized("Not authenticated")
    payload = decode_token(creds.credentials)
    if payload is None:
        raise _unauthorized("Invalid or expired token")
    user = db.get_user_by_id(payload["sub"])
    if user is None:
        raise _unauthorized("User no longer exists")
    return user

_bearer_optional = HTTPBearer(auto_error=False)

async def get_current_user_optional(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_optional),
) -> Optional[dict]:
    if creds is None or not creds.credentials:
        return None
    try:
        payload = decode_token(creds.credentials)
        if payload is None:
            return None
        user = db.get_user_by_id(payload["sub"])
        return user
    except Exception:
        return None