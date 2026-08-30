"""Canonicalization rules for identifier values.

Normalized forms are what the system compares on. Keeping them in one module
means ingestion, search and (later) correlation all agree on what "the same
identifier" means.
"""
from __future__ import annotations

import re

_WS = re.compile(r"\s+")
_HANDLE_TRIM = re.compile(r"^[@/]+|[.,;:]+$")


def normalize_handle(value: str) -> str:
    """Case-fold, strip leading @ and collapse whitespace."""
    return _WS.sub("", _HANDLE_TRIM.sub("", value.strip())).lower()


def normalize_pgp(value: str) -> str:
    """PGP fingerprints compare as uppercase hex with all spacing removed."""
    return _WS.sub("", value.strip()).upper().replace("0X", "")


def normalize_wallet(value: str) -> str:
    """Chain-aware wallet canonicalization.

    EVM addresses are case-insensitive (mixed case is only a checksum), so they
    fold to lowercase. Bech32 is defined lowercase. Base58 addresses are
    case-significant and are left untouched apart from whitespace.
    """
    cleaned = _WS.sub("", value.strip())
    if cleaned.lower().startswith("0x") or cleaned.lower().startswith("bc1"):
        return cleaned.lower()
    return cleaned


def normalize_domain(value: str) -> str:
    """Lowercase, drop a trailing dot and any scheme or path fragment."""
    cleaned = value.strip().lower()
    cleaned = re.sub(r"^[a-z]+://", "", cleaned)
    cleaned = cleaned.split("/", 1)[0]
    return cleaned.rstrip(".")


def normalize_email(value: str) -> str:
    return value.strip().lower()


_BY_KIND = {
    "handle": normalize_handle,
    "alias": normalize_handle,
    "pgp_key": normalize_pgp,
    "wallet": normalize_wallet,
    "domain": normalize_domain,
    "onion_service": normalize_domain,
    "email": normalize_email,
    "jabber": normalize_email,
}


def normalize_identifier(kind: str, value: str) -> str:
    """Dispatch to the canonicalizer for ``kind``, defaulting to case-folding."""
    return _BY_KIND.get(kind, normalize_email)(value)
