"""Comprehensive test suite for all SHADOWGRAPH endpoints.

Covers: health, actors, evidence, timeline, infrastructure, graph,
correlation, confidence, investigations, monitoring, reports.

Run: python tests/test_full.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from fastapi.testclient import TestClient

# Use in-memory SQLite to avoid file lock issues
import app.core.config as _cfg
class _TestSettings:
    database_url = "sqlite:///"
    seed_on_startup = True
    app_mode = "local"
    cors_origins = "http://localhost:5173"
    secret_key = "test-key-for-testing-only"
    log_level = "WARNING"
    max_page_size = 200
def _patch_settings():
    pass

# Override before importing app
import os
os.environ["DATABASE_URL"] = "sqlite:///"
os.environ["SECRET_KEY"] = "test-key-for-testing-only"
os.environ["APP_MODE"] = "local"
os.environ["SEED_ON_STARTUP"] = "true"
os.environ["LOG_LEVEL"] = "WARNING"

from app.main import create_app
app = create_app()
client = TestClient(app, raise_server_exceptions=False)
client.__enter__()

# Authenticate as admin for all tests
_login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
assert _login.status_code == 200, f"Login failed: {_login.text}"
AUTH = {"Authorization": f"Bearer {_login.json()['access_token']}"}

def _get(url: str, **kw):
    return client.get(url, headers=AUTH, **kw)

def _post(url: str, **kw):
    return client.post(url, headers=AUTH, **kw)

def _put(url: str, **kw):
    return client.put(url, headers=AUTH, **kw)

def _delete(url: str, **kw):
    return client.delete(url, headers=AUTH, **kw)

passed = 0
failed = 0
errors: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        msg = f"FAIL: {label} — {detail}" if detail else f"FAIL: {label}"
        errors.append(msg)
        print(f"  [FAIL] {label} ({detail})")


def section(title: str) -> None:
    print(f"\n  {title}")


# =====================================================================
# 1. HEALTH
# =====================================================================
section("1. Health")
r = _get("/api/v1/health")
check("health status 200", r.status_code == 200, str(r.status_code))
h = r.json()
check("health=ok", h.get("status") == "ok")
check("app_mode=local", h.get("adapters", {}).get("app_mode") == "local")
check("db=sqlite", h.get("adapters", {}).get("database") == "sqlite")
check("security headers present", "x-content-type-options" in r.headers)

# =====================================================================
# 2. ACTORS
# =====================================================================
section("2. Actors")
r = _get("/api/v1/actors")
check("list actors 200", r.status_code == 200)
check("actors total > 0", r.json()["total"] > 0, str(r.json()["total"]))

r = _get("/api/v1/actors?q=darkmerchant")
check("search darkmerchant", r.json()["total"] >= 1)

r = _get("/api/v1/actors/darkmerchant")
check("get darkmerchant 200", r.status_code == 200)
check("darkmerchant has personas", len(r.json().get("personas", [])) > 0)
check("darkmerchant has identifiers", len(r.json().get("identifiers", [])) > 0)

r = _get("/api/v1/actors/nonexistent_xyz")
check("actor 404", r.status_code == 404)

r = _get("/api/v1/actors/stats")
check("stats 200", r.status_code == 200)
check("stats total_actors", r.json()["total_actors"] == 13)

r = _get("/api/v1/actors?risk_level=critical")
check("filter risk_level=critical", all(i["risk_level"] == "critical" for i in r.json()["items"]))

r = _get("/api/v1/actors?sort=confidence&order=desc&limit=3")
check("sort+pagination", len(r.json()["items"]) <= 3)

# =====================================================================
# 3. EVIDENCE & RELATIONSHIPS
# =====================================================================
section("3. Evidence & Relationships")
r = _get("/api/v1/evidence/relationships")
check("list relationships 200", r.status_code == 200)
rels = r.json()
check("relationships count >= 3", len(rels) >= 3, str(len(rels)))
check("has from_name", "from_name" in rels[0])
check("has to_name", "to_name" in rels[0])
check("has scoring_factors", "scoring_factors" in rels[0])

r = _get("/api/v1/evidence/relationships/REL-DM-SV-001")
check("get relationship detail 200", r.status_code == 200)
d = r.json()
check("detail has evidence", len(d.get("evidence", [])) > 0)
check("detail has explanation", bool(d.get("explanation")))
check("detail has hypothesis_label", bool(d.get("hypothesis_label")))

r = _get("/api/v1/evidence/relationships/NONEXISTENT")
check("relationship 404", r.status_code == 404)

r = _get("/api/v1/evidence/items")
check("list evidence items 200", r.status_code == 200)
check("evidence count >= 5", len(r.json()) >= 5, str(len(r.json())))
check("evidence has class", "evidence_class" in r.json()[0])

# =====================================================================
# 4. TIMELINE
# =====================================================================
section("4. Timeline")
r = _get("/api/v1/timeline")
check("list timeline 200", r.status_code == 200)
events = r.json()
# Timeline may return {"items": [...]} or a plain list
events_list = events if isinstance(events, list) else events.get("items", [])
check("timeline events >= 10", len(events_list) >= 10, str(len(events_list)))
check("has actor code", "actor_code" in events_list[0] or "actor" in events_list[0])

r = _get("/api/v1/timeline?actor=darkmerchant")
check("filter by actor", r.status_code == 200)
filtered = r.json()
filtered_list = filtered if isinstance(filtered, list) else filtered.get("items", [])
check("filtered count >= 3", len(filtered_list) >= 3)

r = _get("/api/v1/timeline?kind=relationship_added")
check("filter by kind", r.status_code == 200)
kind_filtered = r.json()
kind_list = kind_filtered if isinstance(kind_filtered, list) else kind_filtered.get("items", [])
check("relationship_added events", len(kind_list) >= 2)

r = _get("/api/v1/timeline/migration/darkmerchant")
check("migration story 200", r.status_code == 200)
check("migration has events", len(r.json()) > 0)

# =====================================================================
# 5. INFRASTRUCTURE
# =====================================================================
section("5. Infrastructure")
r = _get("/api/v1/infrastructure")
check("list infra 200", r.status_code == 200)
infra = r.json()
infra_list = infra if isinstance(infra, list) else infra.get("items", [])
check("infra count >= 5", len(infra_list) >= 5, str(len(infra_list)))
check("has kind", "kind" in infra_list[0])
check("has value", "value" in infra_list[0])

r = _get("/api/v1/infrastructure?kind=onion_service")
check("filter onion_service", r.status_code == 200)
onion_data = r.json()
onion_list = onion_data if isinstance(onion_data, list) else onion_data.get("items", [])
check("onion count >= 4", len(onion_list) >= 4)

r = _get("/api/v1/infrastructure?kind=domain")
check("filter domain", r.status_code == 200)

r = _get("/api/v1/infrastructure/clusters")
check("clusters 200", r.status_code == 200)

# =====================================================================
# 6. GRAPH
# =====================================================================
section("6. Graph")
r = _get("/api/v1/graph")
check("graph 200", r.status_code == 200)
g = r.json()
check("has nodes", len(g.get("nodes", [])) > 0, str(len(g.get("nodes", []))))
check("has edges", len(g.get("edges", [])) > 0, str(len(g.get("edges", []))))

r = _get("/api/v1/graph?focus=darkmerchant")
check("graph focus 200", r.status_code == 200)
check("focused has nodes", len(r.json().get("nodes", [])) > 0)

r = _get("/api/v1/graph/edge/evidence?source=ACTOR:darkmerchant&target=ACTOR:shadow_vendor")
check("edge evidence 200", r.status_code == 200)

# =====================================================================
# 7. CORRELATION
# =====================================================================
section("7. Correlation")
r = _get("/api/v1/correlation/evaluate?actor_a=darkmerchant&actor_b=shadow_vendor")
check("correlation evaluate 200", r.status_code == 200)
c = r.json()
check("has signals", len(c.get("signals", [])) > 0)
check("has total_score", "total_score" in c)
check("has band", "band" in c)
check("has explanation", bool(c.get("explanation")))
check("pgp_match detected", any(s["signal_type"] == "pgp_match" for s in c["signals"]))
check("wallet_match detected", any(s["signal_type"] == "wallet_match" for s in c["signals"]))

r = _get("/api/v1/correlation/evaluate?actor_a=darkmerchant&actor_b=quietsteel")
check("unrelated pair score=0", r.json()["total_score"] == 0)

r = _get("/api/v1/correlation/existing")
check("existing correlations 200", r.status_code == 200)
check("existing count >= 3", len(r.json()) >= 3)

# =====================================================================
# 8. CONFIDENCE
# =====================================================================
section("8. Confidence")
r = _get("/api/v1/confidence/evaluate?actor_a=darkmerchant&actor_b=shadow_vendor")
check("confidence evaluate 200", r.status_code == 200)
conf = r.json()
check("has score", "score" in conf)
check("has band", "band" in conf)
check("has derivation", "derivation" in conf)
check("has disclaimer", "disclaimer" in conf)
check("score > 0", conf["score"] > 0, str(conf["score"]))
check("band is MEDIUM or HIGH", conf["band"] in ("MEDIUM", "HIGH"), conf["band"])
check("has source_reliability_avg", "source_reliability_avg" in conf)

r = _get("/api/v1/confidence/evaluate?actor_a=launderpipe&actor_b=crimson_ledger")
check("launderpipe confidence", r.json()["score"] > 0)

r = _get("/api/v1/confidence/existing")
check("existing confidence 200", r.status_code == 200)
check("existing count >= 3", len(r.json().get("relationships", [])) >= 3)

# =====================================================================
# 9. INVESTIGATIONS
# =====================================================================
section("9. Investigations")
r = _get("/api/v1/investigations")
check("list investigations 200", r.status_code == 200)
check("investigations count >= 2", len(r.json()) >= 2)

r = _get("/api/v1/investigations/INV-001")
check("get INV-001 200", r.status_code == 200)
inv = r.json()
check("INV-001 has title", bool(inv.get("title")))
check("INV-001 has relationships", len(inv.get("relationships", [])) > 0)

# Create
r = _post("/api/v1/investigations", json={
    "title": "Test Inv",
    "description": "Testing",
    "lead_analyst": "jmartinez",
    "targets": ["pharmakon"],
})
check("create investigation 201", r.status_code == 201)
new_code = r.json()["code"]

# Activate
r = _post(f"/api/v1/investigations/{new_code}/activate?analyst=jmartinez")
check("activate", r.json()["status"] == "active")

# Add note
r = _post(f"/api/v1/investigations/{new_code}/notes", json={
    "analyst": "jmartinez", "note": "Test note."
})
check("add note", r.json()["ok"] is True)

# Pause
r = _post(f"/api/v1/investigations/{new_code}/pause?analyst=jmartinez")
check("pause", r.json()["status"] == "paused")

# Close
r = _post(f"/api/v1/investigations/{new_code}/close?analyst=jmartinez")
check("close", r.json()["status"] == "closed")

# Invalid analyst
r = _post("/api/v1/investigations", json={
    "title": "X", "description": "X", "lead_analyst": "nobody"
})
check("invalid analyst rejected", "error" in r.json())

# Decide
from sqlalchemy import text
from app.core.database import engine
with engine.connect() as conn:
    rel_id = conn.execute(text('SELECT id FROM relationships WHERE code = "REL-DM-SV-001"')).scalar()

r = _post("/api/v1/investigations/decide", json={
    "relationship_id": rel_id,
    "decision": "accepted",
    "analyst": "jmartinez",
    "review_note": "Test decision.",
})
check("decide accepted", r.json()["decision"] == "accepted")

# Verify persistence
r = _get("/api/v1/evidence/relationships")
for rel in r.json():
    if rel["code"] == "REL-DM-SV-001":
        check("decision persisted", rel["status"] == "accepted")
        break

# Audit log
r = _get("/api/v1/investigations/audit/log")
check("audit log 200", r.status_code == 200)
check("audit has events", len(r.json()) > 0)

# =====================================================================
# 10. MONITORING
# =====================================================================
section("10. Monitoring")
r = _get("/api/v1/monitoring/overview")
check("overview 200", r.status_code == 200)
ov = r.json()
check("overview has entities", ov["entities"]["actors"] == 13)
check("overview has disclaimer", bool(ov.get("disclaimer")))

r = _get("/api/v1/monitoring/sources")
check("sources 200", r.status_code == 200)
check("sources count >= 6", len(r.json()) >= 6)

r = _get("/api/v1/monitoring/relationships")
check("rel breakdown 200", r.status_code == 200)
rb = r.json()
check("has by_status", "by_status" in rb)
check("has by_band", "by_band" in rb)

r = _get("/api/v1/monitoring/timeline")
check("timeline summary 200", r.status_code == 200)
check("timeline total > 0", r.json()["total"] > 0)

# =====================================================================
# 11. REPORTS
# =====================================================================
section("11. Reports")
r = _get("/api/v1/reports/INV-001")
check("generate report 200", r.status_code == 200)
report = r.json()
check("has all sections", all(k in report for k in [
    "investigation", "targets", "summary", "relationships", "evidence",
    "identifiers", "timeline", "infrastructure", "signals", "confidence",
    "analyst_decision", "analyst_notes", "sources", "audit", "disclaimer"
]))
check("targets populated", len(report["targets"]) > 0)
check("relationships populated", len(report["relationships"]) > 0)
check("evidence populated", len(report["evidence"]) > 0)
check("identifiers populated", len(report["identifiers"]) > 0)
check("timeline populated", len(report["timeline"]) > 0)
check("sources populated", len(report["sources"]) > 0)

# JSON export
r = _get("/api/v1/reports/INV-001/export?format=json")
check("JSON export 200", r.status_code == 200)
check("JSON valid", json.loads(r.content)["investigation"]["code"] == "INV-001")

# CSV export
r = _get("/api/v1/reports/INV-001/export?format=csv")
check("CSV export 200", r.status_code == 200)
check("CSV has sections", b"SECTION" in r.content)

# PDF export
r = _get("/api/v1/reports/INV-001/export?format=pdf")
check("PDF export 200", r.status_code == 200)
check("PDF valid header", r.content[:4] == b"%PDF")

# Not found
r = _get("/api/v1/reports/INV-999")
check("report not found", "error" in r.json())

# Invalid format
r = _get("/api/v1/reports/INV-001/export?format=xml")
check("invalid format rejected", r.status_code == 400)

# =====================================================================
# 12. SECURITY HEADERS
# =====================================================================
section("12. Security Headers")
r = _get("/api/v1/actors?limit=1")
check("X-Content-Type-Options", r.headers.get("x-content-type-options") == "nosniff")
check("X-Frame-Options", r.headers.get("x-frame-options") == "DENY")
check("X-XSS-Protection", r.headers.get("x-xss-protection") == "1; mode=block")
check("Referrer-Policy", r.headers.get("referrer-policy") == "strict-origin-when-cross-origin")

# =====================================================================
# SUMMARY
# =====================================================================
print(f"\n{'=' * 60}")
print(f"  TOTAL: {passed} passed, {failed} failed, {passed + failed} checks")
print(f"{'=' * 60}")

if errors:
    print("\n  FAILURES:")
    for err in errors:
        print(f"    - {err}")

client.__exit__(None, None, None)
sys.exit(1 if failed else 0)
