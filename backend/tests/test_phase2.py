"""Phase 2 backend-foundation tests.

Covers the phase-2 validation battery:
1. Auth flow — login, refresh rotation, logout revocation, audit auth.*
2. RBAC matrix — analyst / senior_analyst / admin per SECURITY.md §2
3. Ingestion boundary — non-synthetic/authorized/public sources rejected
4. Security envelope — request_id, API.md §1.1 error envelope, safe 500s, headers
5. Migrations — alembic upgrade head / downgrade base on a scratch DB

Run:  cd backend && python -m pytest tests/test_phase2.py -v
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

# Isolated in-memory DB per test session; unique secret per run.
os.environ["DATABASE_URL"] = "sqlite:///"
os.environ["SECRET_KEY"] = "phase2-test-" + uuid.uuid4().hex
os.environ["APP_MODE"] = "local"
os.environ["SEED_ON_STARTUP"] = "true"
os.environ["LOG_LEVEL"] = "WARNING"

_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

app = create_app()
client = TestClient(app, raise_server_exceptions=False)
client.__enter__()


def _login(username: str, password: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"login {username} failed: {r.text}"
    body = r.json()
    return {
        "access": body["access_token"],
        "refresh": body["refresh_token"],
        "user": body["user"],
    }


@pytest.fixture(scope="module")
def tokens() -> dict:
    return {
        "admin": _login("ami", "ami43210"),
        "senior": _login("amra", "amra4321"),
        "analyst": _login("tumi", "tumi1430"),
    }


def _auth(tokens: dict, role: str) -> dict:
    return {"Authorization": f"Bearer {tokens[role]['access']}"}


# ===========================================================================
# 1. AUTH FLOW (validation item 2)
# ===========================================================================

def test_login_returns_canonical_user_object_and_compat_fields(tokens):
    """The API.md §2 canonical `user` object AND the deprecated flat
    username/role fields must both be present (frontend compat shim)."""
    admin = tokens["admin"]
    assert admin["user"]["username"] == "ami"
    assert admin["user"]["role"] == "admin"
    assert admin["user"]["email"] == "ami@mavericks.local"
    assert admin["user"]["is_active"] is True
    assert "full_name" in admin["user"]
    # compat shim for the current Login page
    r = client.post("/api/v1/auth/login", json={"username": "ami", "password": "ami43210"})
    body = r.json()
    assert body["username"] == "ami" and body["role"] == "admin"


def test_jwt_issuer_checked_and_typ_bound():
    import jwt as pyjwt
    from app.core.config import settings
    from app.core.security import create_access_token, decode_token, decode_refresh_token

    tok = create_access_token("ami", "admin", "uid-123")
    payload = decode_token(tok)
    assert payload["iss"] == "trilok-trace"
    assert payload["typ"] == "access"
    assert payload["uid"] == "uid-123"

    # tampered issuer → rejected
    claims = pyjwt.decode(tok, options={"verify_signature": False})
    claims["iss"] = "evil"
    bad = pyjwt.encode(claims, settings.secret_key, algorithm="HS256")
    with pytest.raises(pyjwt.PyJWTError):
        decode_token(bad)

    # refresh token cannot be used as an access token (typ binding)
    refresh_tok, jti = (lambda t: (t[0], t[1]))(  # type: ignore[misc]
        __import__("app.core.security", fromlist=["x"]).create_refresh_token("ami", "admin", "u")
    )
    with pytest.raises(pyjwt.PyJWTError):
        decode_token(refresh_tok)
    assert decode_refresh_token(refresh_tok)["jti"] == jti


def test_refresh_rotation_and_revocation():
    login = client.post(
        "/api/v1/auth/login", json={"username": "ami", "password": "ami43210"}
    ).json()
    old_refresh = login["refresh_token"]

    # rotate: old jti revoked, new pair issued
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200, r.text
    new_pair = r.json()
    assert new_pair["access_token"] and new_pair["refresh_token"]
    assert new_pair["refresh_token"] != old_refresh

    # replaying the rotated token must fail (revoked jti)
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r2.status_code == 401

    # logout revokes the current refresh token
    tok = login["access_token"]
    r3 = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": new_pair["refresh_token"]},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r3.status_code == 200
    r4 = client.post("/api/v1/auth/refresh", json={"refresh_token": new_pair["refresh_token"]})
    assert r4.status_code == 401


def test_auth_audit_actions_written(tokens):
    """Self-contained: generate each auth.* event, then verify the audit log."""
    from sqlalchemy import select
    from app.core.database import SessionLocal
    from app.models.ops import AuditEvent

    # login (fixture already did, but be explicit) + a failed attempt
    client.post("/api/v1/auth/login", json={"username": "tumi", "password": "tumi1430"})
    client.post("/api/v1/auth/login", json={"username": "tumi", "password": "nope"})
    # refresh
    login = client.post(
        "/api/v1/auth/login", json={"username": "ami", "password": "ami43210"}
    ).json()
    client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    # logout
    client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": client.post(
            "/api/v1/auth/login", json={"username": "ami", "password": "ami43210"}
        ).json()["refresh_token"]},
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )

    session = SessionLocal()
    try:
        actions = set(
            session.execute(
                select(AuditEvent.action).where(AuditEvent.action.like("auth.%"))
            ).scalars()
        )
        assert "auth.login" in actions
        assert "auth.login_failed" in actions
        assert "auth.refresh" in actions
        assert "auth.logout" in actions
        # no legacy UPPERCASE actions from the new auth router
        assert "LOGIN_SUCCESS" not in actions
    finally:
        session.close()


def test_bad_credentials_401_no_user_oracle():
    r = client.post("/api/v1/auth/login", json={"username": "ami", "password": "wrong"})
    assert r.status_code == 401
    r2 = client.post("/api/v1/auth/login", json={"username": "ghost", "password": "x"})
    assert r2.status_code == 401
    # same generic message for both (no account-existence oracle)
    assert r.json()["error"]["message"] == r2.json()["error"]["message"]


# ===========================================================================
# 2. RBAC MATRIX (validation item 3) — SECURITY.md §2
# ===========================================================================

def test_rbac_read_intelligence_all_roles_allowed(tokens):
    """Read intelligence: analyst ✅ senior ✅ admin ✅"""
    for role in ("analyst", "senior", "admin"):
        r = client.get("/api/v1/actors", headers=_auth(tokens, role))
        assert r.status_code == 200, f"{role} read actors → {r.status_code}"


def test_rbac_create_investigation_analyst_allowed(tokens):
    """Create investigations/notes/targets: analyst ✅ (§2 row 2)."""
    r = client.post(
        "/api/v1/investigations",
        json={
            "title": "RBAC probe",
            "description": "phase2 rbac",
            "lead_analyst": "tumi",
            "targets": [],
        },
        headers=_auth(tokens, "analyst"),
    )
    assert r.status_code == 201, f"analyst create investigation → {r.status_code}: {r.text}"


def test_rbac_review_decision_senior_only(tokens):
    """Review relationships: analyst – / senior ✅ / admin ✅ (§2 row 3)."""
    from sqlalchemy import text
    from app.core.database import engine

    with engine.connect() as conn:
        rel_id = conn.execute(
            text('SELECT id FROM relationships WHERE code = "REL-DM-SV-001"')
        ).scalar()

    def _decide(headers):
        return client.post(
            "/api/v1/investigations/decide",
            json={
                "relationship_id": rel_id,
                "decision": "uncertain",
                "analyst": "amra",
                "review_note": "phase2 rbac probe",
            },
            headers=headers,
        )

    assert _decide(_auth(tokens, "analyst")).status_code == 403
    assert _decide(_auth(tokens, "senior")).status_code == 200
    assert _decide(_auth(tokens, "admin")).status_code == 200


def test_rbac_scan_trigger_senior_only(tokens):
    """Trigger scans: analyst – / senior ✅ / admin ✅ (§2 row 5)."""
    for role, expected in (("analyst", 403), ("senior", 200), ("admin", 200)):
        r = client.post(
            "/api/v1/ingestion/scan?scenario=darkmerchant", headers=_auth(tokens, role)
        )
        assert r.status_code == expected, f"{role} scan → {r.status_code}"


def test_rbac_admin_endpoints_admin_only(tokens):
    """Manage analysts + audit log: analyst – / senior – / admin ✅ (§2 row 6)."""
    for role, expected in (("analyst", 403), ("senior", 403), ("admin", 200)):
        r = client.get("/api/v1/admin/analysts", headers=_auth(tokens, role))
        assert r.status_code == expected, f"{role} admin/analysts → {r.status_code}"
        r2 = client.get("/api/v1/admin/audit", headers=_auth(tokens, role))
        assert r2.status_code == expected, f"{role} admin/audit → {r2.status_code}"

    # admin can create + patch an analyst
    uname = f"probe_{uuid.uuid4().hex[:6]}"
    r = client.post(
        "/api/v1/admin/analysts",
        json={
            "username": uname,
            "full_name": "RBAC Probe",
            "email": f"{uname}@mavericks.local",
            "password": "probe-pass-123",
            "role": "analyst",
        },
        headers=_auth(tokens, "admin"),
    )
    assert r.status_code == 201, r.text
    analyst_id = r.json()["id"]
    r2 = client.patch(
        f"/api/v1/admin/analysts/{analyst_id}",
        json={"is_active": False},
        headers=_auth(tokens, "admin"),
    )
    assert r2.status_code == 200 and r2.json()["is_active"] is False


def test_unauthenticated_401_everywhere():
    for method, url in (
        ("GET", "/api/v1/actors"),
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/admin/audit"),
        ("POST", "/api/v1/ingestion/scan"),
    ):
        r = getattr(client, method.lower())(url)
        assert r.status_code == 401, f"{method} {url} → {r.status_code}"


# ===========================================================================
# 3. INGESTION BOUNDARY (validation item 4) — DATABASE.md §2 guardrail
# ===========================================================================

def test_boundary_rejects_disallowed_access_methods():
    from app.ingestion import ALLOWED_ACCESS_METHODS, ForbiddenSourceError
    from app.ingestion.boundary import assert_source_allowed
    from app.core.database import SessionLocal
    from sqlalchemy.exc import IntegrityError
    from app.models.identity import Source

    # Unit level: each forbidden method must raise at the boundary check.
    for method in ("subpoenaed", "scraped", "tor_hidden_service", "leaked_dump", ""):
        fake = Source(name=f"bad-{uuid.uuid4().hex[:6]}", kind="forum", access_method=method)
        with pytest.raises(ForbiddenSourceError):
            assert_source_allowed(fake)

    # The locked allow-list itself
    assert ALLOWED_ACCESS_METHODS == ("synthetic", "authorized", "public")

    # DB level: the CHECK constraint (ck_sources_access_method) must refuse to
    # even STORE a disallowed source — defense in depth below the boundary.
    session = SessionLocal()
    try:
        bad = Source(
            name=f"subpoena-{uuid.uuid4().hex[:6]}",
            kind="forum",
            access_method="subpoenaed",
        )
        session.add(bad)
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.rollback()
        session.close()


def test_boundary_accepts_synthetic_and_blocks_pipeline_write():
    """Happy path: synthetic source passes; a disallowed source cannot reach a
    pipeline write. The DB CHECK makes an invalid access_method unstoreable,
    so the only bypass left is a name the pipeline does not resolve — which
    the boundary must also refuse (missing/disabled source)."""
    from app.core.database import SessionLocal
    from app.models.identity import Source
    from app.services.ingestion import RawObservation, run_ingestion_pipeline
    from sqlalchemy import select

    ALLOWED = ("synthetic", "authorized", "public")

    session = SessionLocal()
    try:
        # synthetic passes the boundary ('Silk Harbor Market' is seeded
        # synthetic in the demo catalogue)
        obs_ok = RawObservation(
            source_name="Silk Harbor Market",
            source_type="marketplace",
            content_type="listing",
            external_id=f"p2-{uuid.uuid4().hex[:8]}",
            retrieved_at="2026-09-01T00:00:00",
            published_at=None,
            content="PGP: 9F2A4C81D3E5B7091A62F84C5D30E7B29C41A8F6",
        )
        result = run_ingestion_pipeline([obs_ok], session)
        assert result.observations_processed == 1
        session.rollback()

        # Unknown source name → boundary refuses (no auto-creating a row the
        # pipeline could then silently trust; refusal is recorded per-record).
        obs_unknown = RawObservation(
            source_name=f"never-registered-{uuid.uuid4().hex[:6]}",
            source_type="forum",
            content_type="post",
            external_id=f"p2-{uuid.uuid4().hex[:8]}",
            retrieved_at="2026-09-01T00:00:00",
            published_at=None,
            content="should never be ingested",
        )
        result2 = run_ingestion_pipeline([obs_unknown], session)
        assert result2.observations_processed == 0
        assert result2.errors, "boundary rejection must be recorded in result.errors"

        # And the DB CHECK means a 'scraped'/'subpoenaed' source row cannot
        # exist at all — proven in test_boundary_rejects_disallowed_access_methods.
        assert session.execute(
            select(Source).where(Source.access_method.notin_(ALLOWED))
        ).scalars().first() is None
    finally:
        session.rollback()
        session.close()


# ===========================================================================
# 4. SECURITY ENVELOPE & HEADERS (SECURITY.md §3–4, §7)
# ===========================================================================

def test_error_envelope_shape_with_request_id(tokens):
    r = client.get("/api/v1/actors/nonexistent_xyz", headers=_auth(tokens, "admin"))
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "ACTOR_NOT_FOUND"
    assert body["error"]["request_id"].startswith("req_")
    assert r.headers.get("x-request-id") == body["error"]["request_id"]
    # legacy compat fields preserved for the current frontend/tests
    assert body["code"] == "actor_not_found"


def test_validation_error_envelope():
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "", "password": ""},
    )
    assert r.status_code in (400, 422)
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "request_id" in body["error"]


def test_security_headers_on_every_response():
    r = client.get("/api/v1/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("referrer-policy") == "no-referrer"
    assert "default-src 'self'" in r.headers.get("content-security-policy", "")
    assert r.headers.get("x-request-id", "").startswith("req_")
    # HSTS only in production (SECURITY.md §4: dev allows HTTP on localhost)
    assert "strict-transport-security" not in r.headers


def test_safe_500_no_stack_trace(tokens):
    """An unexpected exception must yield a generic 500 envelope, not a trace."""
    from app.services.actors import ActorService

    original = ActorService.search

    def _boom(self, *a, **kw):  # pragma: no cover - trivially raises
        raise RuntimeError("secret internal detail xyzzy")

    ActorService.search = _boom
    try:
        r = client.get("/api/v1/actors", headers=_auth(tokens, "admin"))
        assert r.status_code == 500
        body = r.json()
        assert body["error"]["code"] == "INTERNAL_ERROR"
        # no stack trace or internal message leaks
        assert "xyzzy" not in r.text
        assert "RuntimeError" not in r.text
        assert body["error"]["request_id"].startswith("req_")
    finally:
        ActorService.search = original


def test_rate_limit_429_envelope():
    """Sliding-window limiter returns 429 with the §1.1 envelope once exceeded."""
    # Pre-fill the limiter's window for this client IP to just under the limit,
    # so the next request trips it deterministically (no 120+ real requests).
    # The store lives in the create_app closure; reach it via the middleware's
    # documented contract instead: fire requests until 429 (cap 200).
    codes = []
    body = None
    for _ in range(200):
        resp = client.get("/api/v1/auth/me")
        codes.append(resp.status_code)
        if resp.status_code == 429:
            body = resp.json()
            break
    assert 429 in codes, f"expected a 429 within 200 requests; got {sorted(set(codes))}"
    assert body is not None and body["error"]["code"] == "RATE_LIMITED"
    assert "request_id" in body["error"]


# ===========================================================================
# 5. MIGRATIONS (validation item 1) — up/down on a scratch DB
# ===========================================================================

def test_alembic_single_head():
    out = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=_backend_dir, capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, out.stderr
    heads = [ln for ln in out.stdout.splitlines() if ln.strip()]
    assert len(heads) == 1, f"expected single head, got: {heads}"


def test_alembic_upgrade_downgrade_cycle(tmp_path):
    db_path = tmp_path / "mig.db"
    url = f"sqlite:///{db_path.as_posix()}"

    up = subprocess.run(
        [sys.executable, "-m", "alembic", "-x", f"db_url={url}", "upgrade", "head"],
        cwd=_backend_dir, capture_output=True, text=True, timeout=300,
    )
    assert up.returncode == 0, up.stderr[-2000:]

    import sqlite3

    con = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
        )
    }
    con.close()

    expected = {
        "sources", "actors", "personas", "identifiers",
        "handles", "aliases", "pgp_keys", "wallets",
        "domains", "infrastructure", "certificate_metadata",
        "marketplaces", "forums", "posts",
        "observations", "evidence", "relationships", "relationship_observations",
        "timeline_events", "behavior_profiles", "stylometric_profiles",
        "analysts", "investigations", "investigation_notes",
        "graph_sync_state", "scan_jobs", "alerts", "reports", "audit_events",
    }
    missing = expected - tables
    assert not missing, f"tables missing after upgrade: {missing}"

    down = subprocess.run(
        [sys.executable, "-m", "alembic", "-x", f"db_url={url}", "downgrade", "base"],
        cwd=_backend_dir, capture_output=True, text=True, timeout=300,
    )
    assert down.returncode == 0, down.stderr[-2000:]

    con = sqlite3.connect(db_path)
    leftover = [
        row[0]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
        )
    ]
    con.close()
    assert leftover == [], f"tables left after downgrade: {leftover}"


def test_no_legacy_reliability_column_in_schema():
    """The prototype's `reliability` column must not survive in the DDL."""
    import sqlite3
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        url = f"sqlite:///{Path(td).joinpath('x.db').as_posix()}"
        subprocess.run(
            [sys.executable, "-m", "alembic", "-x", f"db_url={url}", "upgrade", "head"],
            cwd=_backend_dir, capture_output=True, text=True, timeout=300, check=True,
        )
        db = Path(td).joinpath("x.db")
        con = sqlite3.connect(db)
        cols = {row[1] for row in con.execute("PRAGMA table_info(sources)")}
        con.close()
        assert "reliability" not in cols, "legacy sources.reliability must be gone"
        assert "trust_level" in cols
