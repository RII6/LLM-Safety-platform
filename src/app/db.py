"""app/db.py — PostgreSQL store for scan reports.

Replaces the reports/*.json file cache with a `scans` table: the full report is
kept as JSONB and a few fields are extracted into columns for fast listing,
history and filtering. ``cache_key`` (the content hash from scan.py) is UNIQUE
and serves as the cache lookup.

Connection string comes from DATABASE_URL (see config.py); a running PostgreSQL
is required. Schema is created on demand via init_db().
"""
from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id                BIGSERIAL   PRIMARY KEY,
    repo              TEXT        NOT NULL,
    cache_key         TEXT        NOT NULL UNIQUE,
    verdict_code      TEXT        NOT NULL,
    represents_harm   BOOLEAN,
    params            BIGINT,
    weight_bytes      BIGINT,
    sample            INTEGER,
    dtype             TEXT,
    generated_harmful INTEGER     NOT NULL DEFAULT 0,
    generated_benign  INTEGER     NOT NULL DEFAULT 0,
    elapsed_s         DOUBLE PRECISION,
    report            JSONB       NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_scans_repo ON scans (repo);
CREATE INDEX IF NOT EXISTS idx_scans_created ON scans (created_at DESC);
"""

# Users and their scan history. ``users`` is the account store (password_hash is a
# PBKDF2 string from app.auth). ``user_scans`` links accounts to shared ``scans``
# rows: the content cache in ``scans`` stays global (compute is de-duped by
# cache_key) while each user still gets their own history via this join.
_USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL   PRIMARY KEY,
    username      TEXT        NOT NULL UNIQUE,
    email         TEXT        UNIQUE,
    password_hash TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS user_scans (
    user_id    BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    scan_id    BIGINT      NOT NULL REFERENCES scans (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, scan_id)
);
CREATE INDEX IF NOT EXISTS idx_user_scans_user ON user_scans (user_id, created_at DESC);
"""


class UserExists(Exception):
    """Raised by create_user when the username or email is already taken."""


def _connect():
    return psycopg.connect(config.DATABASE_URL)


def init_db() -> None:
    """Create the scans, users and user_scans tables if absent. Call once at startup."""
    with _connect() as conn:
        conn.execute(_SCHEMA)
        conn.execute(_USERS_SCHEMA)


def get_cached(cache_key: str) -> dict | None:
    """Return the stored report dict for *cache_key*, or None on a miss."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT report FROM scans WHERE cache_key = %s", (cache_key,)
        ).fetchone()
    return row[0] if row else None


def save_scan(repo: str, cache_key: str, result: dict) -> int | None:
    """Persist a freshly computed report; upsert on cache_key. Returns the scan id."""
    meta = result.get("meta", {})
    verdict = result.get("verdict", {})
    gen = meta.get("generated", {})
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scans (repo, cache_key, verdict_code, represents_harm,
                                   params, weight_bytes, sample, dtype,
                                   generated_harmful, generated_benign, elapsed_s, report)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (cache_key) DO UPDATE
                    SET report = EXCLUDED.report,
                        verdict_code = EXCLUDED.verdict_code,
                        created_at = now()
                RETURNING id
                """,
                (
                    repo, cache_key, verdict.get("code"), verdict.get("represents_harm"),
                    meta.get("params"), meta.get("weight_bytes"), meta.get("sample"),
                    meta.get("dtype"), gen.get("harmful", 0), gen.get("benign", 0),
                    meta.get("elapsed_s"), Jsonb(result),
                ),
            )
            row = cur.fetchone()
            return row[0] if row else None


def list_scans(user_id: int | None = None) -> list[dict]:
    """Most-recent-first list for the reports view: [{id, repo, verdict}, ...].

    With *user_id*, return only the scans in that account's history; without it,
    return every scan (used by unauthenticated/admin contexts).
    """
    with _connect() as conn:
        if user_id is None:
            rows = conn.execute(
                "SELECT id, repo, verdict_code FROM scans ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT s.id, s.repo, s.verdict_code
                FROM user_scans us JOIN scans s ON s.id = us.scan_id
                WHERE us.user_id = %s
                ORDER BY us.created_at DESC
                """,
                (user_id,),
            ).fetchall()
    return [{"id": r[0], "repo": r[1], "verdict": r[2]} for r in rows]


def get_scan_by_id(scan_id: int) -> dict | None:
    """Return the full report for a given scan ID, or None if not found."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT report FROM scans WHERE id = %s", (scan_id,)
        ).fetchone()
    return row[0] if row else None


# ── users ─────────────────────────────────────────────────────────────────────

_PUBLIC_USER_COLS = "id, username, email, created_at"


def _user_dict(row) -> dict:
    """Shape a (id, username, email, created_at) row into a public user dict."""
    return {
        "id": row[0],
        "username": row[1],
        "email": row[2],
        "created_at": row[3].isoformat() if row[3] is not None else None,
    }


def create_user(username: str, email: str | None, password_hash: str) -> dict:
    """Insert a new account; return the public user dict.

    Raises UserExists if the username or email is already taken.
    """
    try:
        with _connect() as conn:
            row = conn.execute(
                f"""
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING {_PUBLIC_USER_COLS}
                """,
                (username, email, password_hash),
            ).fetchone()
    except psycopg.errors.UniqueViolation:
        raise UserExists("username or email already taken")
    return _user_dict(row)


def get_user_by_username(username: str) -> dict | None:
    """Return the account (including password_hash, for login) or None."""
    with _connect() as conn:
        row = conn.execute(
            f"SELECT {_PUBLIC_USER_COLS}, password_hash FROM users WHERE username = %s",
            (username,),
        ).fetchone()
    if row is None:
        return None
    user = _user_dict(row)
    user["password_hash"] = row[4]
    return user


def get_user_by_id(user_id: int) -> dict | None:
    """Return the public account record for *user_id*, or None."""
    with _connect() as conn:
        row = conn.execute(
            f"SELECT {_PUBLIC_USER_COLS} FROM users WHERE id = %s", (user_id,)
        ).fetchone()
    return _user_dict(row) if row else None


def record_user_scan(user_id: int, scan_id: int) -> None:
    """Link a scan to an account's history (idempotent; refreshes the timestamp)."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO user_scans (user_id, scan_id) VALUES (%s, %s)
            ON CONFLICT (user_id, scan_id) DO UPDATE SET created_at = now()
            """,
            (user_id, scan_id),
        )


def record_user_scan_by_key(user_id: int, cache_key: str) -> None:
    """Link the scan identified by *cache_key* to an account's history.

    Used on a cache hit, where only the content hash is at hand.
    """
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO user_scans (user_id, scan_id)
            SELECT %s, id FROM scans WHERE cache_key = %s
            ON CONFLICT (user_id, scan_id) DO UPDATE SET created_at = now()
            """,
            (user_id, cache_key),
        )