"""Auth helpers: PBKDF2 password hashing (stdlib) + JWT (PyJWT).

Per SECURITY.md §1:
- PBKDF2-SHA256, 260,000 iterations, 16-byte salt — stdlib hashlib only.
- JWT HS256 via PyJWT with strict claim validation (issuer check:
  ``trilok-trace``).
- Access token default 30 minutes (env-tunable; API.md §2 says 15 — the
  env var is the single source of truth).
- Refresh tokens (API.md §2 / docker-compose ACCESS_TOKEN_MINUTES block):
  7-day, rotating, revocable via ``jti`` denylist.
- Login/logout events are written to ``audit_events`` (``auth.*``).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from .config import settings

_PBKDF2_ITERATIONS = 260_000
JWT_ISSUER = "trilok-trace"


def utcnow() -> datetime:
    """Naive-UTC now (keeps SQLite DateTime handling simple)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    """PBKDF2-SHA256, 260k iterations, 16-byte random salt (SECURITY.md §1)."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2:sha256:{_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of ``password`` against a stored PBKDF2 digest.

    Stored format is ``pbkdf2:sha256:<iterations>$<salt_hex>$<digest_hex>``,
    which splits into exactly three ``$``-separated fields.
    """
    try:
        prefix, salt_hex, hash_hex = stored.split("$")
        scheme, algo, iterations = prefix.split(":")
        if scheme != "pbkdf2" or algo != "sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            algo, password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


def _encode(payload: dict) -> str:
    return pyjwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(username: str, role: str, user_id: str) -> str:
    """Short-lived access token (issuer-checked on decode)."""
    now = utcnow()
    payload = {
        "sub": username,
        "role": role,
        "uid": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "iss": JWT_ISSUER,
        "typ": "access",
    }
    return _encode(payload)


def create_refresh_token(username: str, role: str, user_id: str) -> tuple[str, str]:
    """Long-lived rotating refresh token; returns (token, jti)."""
    now = utcnow()
    jti = uuid.uuid4().hex
    payload = {
        "sub": username,
        "role": role,
        "uid": user_id,
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_days),
        "iss": JWT_ISSUER,
        "typ": "refresh",
        "jti": jti,
    }
    return _encode(payload), jti


def _decode(token: str, *, expected_typ: str) -> dict:
    """Strict decode: signature, expiry, issuer and token-type all checked."""
    payload = pyjwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
        issuer=JWT_ISSUER,
        options={"require": ["exp", "sub", "iss", "typ"]},
    )
    if payload.get("typ") != expected_typ:
        raise pyjwt.InvalidTokenError(f"expected {expected_typ} token")
    return payload


def decode_token(token: str) -> dict:
    """Decode and validate an access token (raises PyJWT errors on failure)."""
    return _decode(token, expected_typ="access")


def decode_refresh_token(token: str) -> dict:
    """Decode and validate a refresh token (raises PyJWT errors on failure)."""
    return _decode(token, expected_typ="refresh")


def make_secret(length: int = 48) -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))
