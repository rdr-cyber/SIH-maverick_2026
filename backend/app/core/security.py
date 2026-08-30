"""Auth helpers: PBKDF2 password hashing (stdlib, no bcrypt dep) + JWT (PyJWT).

Role policy (RBAC appendix): admins manage users/decisions, analysts decide
correlation hypotheses, auditors read-only.
Roles: admin | senior_analyst | analyst | auditor
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import string
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from .config import settings

_ITER = 260_000


def utcnow() -> datetime:
    """Naive-UTC now (keeps SQLite DateTime handling simple)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITER)
    return f"pbkdf2:sha256:{_ITER}${salt.hex()}${digest.hex()}"


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


def create_access_token(username: str, role: str, user_id: str) -> str:
    now = utcnow()
    payload = {
        "sub": username,
        "role": role,
        "uid": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "iss": "shadowgraph",
    }
    return pyjwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return pyjwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm],
                        issuer="shadowgraph")


def make_secret(length: int = 48) -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))
