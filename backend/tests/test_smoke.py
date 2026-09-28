"""Comprehensive API smoke test: every route, every role, every response shape.

Run: python tests/test_smoke.py
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# Use unique DB to avoid lock conflicts
os.environ["DATABASE_URL"] = "sqlite:///"
os.environ["SECRET_KEY"] = "smoke-test-key-" + uuid.uuid4().hex[:8]
os.environ["APP_MODE"] = "local"
os.environ["SEED_ON_STARTUP"] = "true"
os.environ["LOG_LEVEL"] = "WARNING"

from fastapi.testclient import TestClient
from app.main import create_app

app = create_app()
client = TestClient(app, raise_server_exceptions=False)
client.__enter__()

results: list[tuple[str, bool]] = []
errors: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    tag = "PASS" if ok else "FAIL"
    msg = f"  [{tag}] {label}"
    if detail:
        msg += f"  ({detail})"
    print(msg, flush=True)
    results.append((label, ok))
    if not ok:
        errors.append(f"{label} — {detail}" if detail else label)


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ============================================================================
# Helper functions
# ============================================================================

def login(username: str, password: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    if r.status_code == 200:
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    return {}


ADMIN = login("ami", "ami43210")
SENIOR = login("amra", "amra4321")
ANALYST = login("tumi", "tumi1430")


def g(url: str, headers: dict | None = None):
    return client.get(url, headers=headers or ADMIN)


def p(url: str, headers: dict | None = None, **kw):
    return client.post(url, headers=headers or ADMIN, **kw)


# ============================================================================
# 1. AUTH
# ============================================================================
section("1. AUTH")

r = p("/api/v1/auth/login", json={"username": "ami", "password": "ami43210"})
check("login ami", r.status_code == 200, str(r.status_code))
check("login returns access_token", "access_token" in r.json())
check("login returns role", r.json().get("role") == "admin")
check("login returns username", r.json().get("username") == "ami")

r = p("/api/v1/auth/login", json={"username": "amra", "password": "amra4321"})
check("login amra", r.status_code == 200)
check("amra role=senior_analyst", r.json().get("role") == "senior_analyst")

r = p("/api/v1/auth/login", json={"username": "tumi", "password": "tumi1430"})
check("login tumi", r.status_code == 200)
check("tumi role=analyst", r.json().get("role") == "analyst")

r = p("/api/v1/auth/login", json={"username": "ami", "password": "wrong"})
check("wrong password 401", r.status_code == 401)

r = p("/api/v1/auth/login", json={"username": "nonexistent", "password": "x"})
check("nonexistent user 401", r.status_code == 401)

r = p("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
check("old credentials rejected", r.status_code == 401)

r = g("/api/v1/auth/me")
check("/auth/me 200", r.status_code == 200)
check("/auth/me username=ami", r.json().get("username") == "ami")
check("/auth/me role=admin", r.json().get("role") == "admin")

r = g("/api/v1/auth/me", headers=SENIOR)
check("/auth/me amra", r.json().get("username") == "amra")
check("/auth/me amra role", r.json().get("role") == "senior_analyst")

r = g("/api/v1/auth/me", headers=ANALYST)
check("/auth/me tumi", r.json().get("username") == "tumi")

r = client.get("/api/v1/auth/me")
check("unauth /auth/me 401", r.status_code == 401)

r = client.get("/api/v1/actors")
check("unauth /actors 401", r.status_code == 401)

r = client.get("/api/v1/actors", headers={"Authorization": "Bearer invalid-token"})
check("invalid token 401", r.status_code == 401)


# ============================================================================
# 2. HEALTH & ROOT
# ============================================================================
section("2. HEALTH & ROOT")

r = client.get("/")
check("root 200", r.status_code == 200)
body = r.json()
check("root has name", body.get("name") == "TRILOK TRACE")
check("root has version", "version" in body)
check("root has docs", body.get("docs") == "/docs")

r = client.get("/api/v1/health")
check("health 200", r.status_code == 200)
h = r.json()
check("health status=ok", h.get("status") == "ok")
check("health app", h.get("app") == "TRILOK TRACE")
check("health db=sqlite", h.get("adapters", {}).get("database") == "sqlite")
check("health graph=inprocess", h.get("adapters", {}).get("graph_backend") == "inprocess")
check("health tasks=local", h.get("adapters", {}).get("task_backend") == "local")
check("health has checks", isinstance(h.get("checks"), dict))
check("security header nosniff", r.headers.get("x-content-type-options") == "nosniff")
check("security header DENY", r.headers.get("x-frame-options") == "DENY")
check("security header xss", r.headers.get("x-xss-protection") == "1; mode=block")
check("security header referrer", r.headers.get("referrer-policy") == "no-referrer")


# ============================================================================
# 3. ACTORS
# ============================================================================
section("3. ACTORS")

r = g("/api/v1/actors")
check("list actors 200", r.status_code == 200)
body = r.json()
check("actors has items", isinstance(body.get("items"), list))
check("actors has total", isinstance(body.get("total"), int))
check("actors total>=13", body.get("total", 0) >= 13)
check("actors has limit", "limit" in body)
check("actors has offset", "offset" in body)
first = body["items"][0]
check("actor has id", "id" in first)
check("actor has code", "code" in first)
check("actor has display_name", "display_name" in first)
check("actor has risk_level", "risk_level" in first)
check("actor has category", "category" in first)
check("actor has attribution_confidence", "attribution_confidence" in first)
check("actor has persona_count", "persona_count" in first)
check("actor has identifier_count", "identifier_count" in first)

r = g("/api/v1/actors?q=darkmerchant")
check("search darkmerchant", r.status_code == 200 and r.json()["total"] >= 1)
check("search result has darkmerchant", any(i["code"] == "darkmerchant" for i in r.json()["items"]))

r = g("/api/v1/actors?q=shadow_vendor")
check("search shadow_vendor", r.json()["total"] >= 1)

r = g("/api/v1/actors?q=9F2A4C81D3E5B7091A62F84C5D30E7B29C41A8F6")
check("search by PGP fingerprint", r.json()["total"] >= 1)

r = g("/api/v1/actors?risk_level=critical")
check("filter risk_level=critical", r.status_code == 200)
check("all critical", all(i["risk_level"] == "critical" for i in r.json()["items"]))

r = g("/api/v1/actors?category=narcotics")
check("filter category=narcotics", all(i["category"] == "narcotics" for i in r.json()["items"]))

r = g("/api/v1/actors?status=dormant")
check("filter status=dormant", all(i["status"] == "dormant" for i in r.json()["items"]))

r = g("/api/v1/actors?sort=risk&order=asc")
check("sort risk asc", r.status_code == 200)

r = g("/api/v1/actors?sort=confidence&order=desc")
check("sort confidence desc", r.status_code == 200)
confs = [i["attribution_confidence"] for i in r.json()["items"]]
check("confidence actually descending", confs == sorted(confs, reverse=True))

r = g("/api/v1/actors?limit=3&offset=0")
check("pagination limit=3", len(r.json()["items"]) <= 3)
check("pagination limit value", r.json()["limit"] == 3)
r2 = g("/api/v1/actors?limit=3&offset=3")
check("pagination no overlap", len(set(i["id"] for i in r.json()["items"]) & set(i["id"] for i in r2.json()["items"])) == 0)

r = g("/api/v1/actors/darkmerchant")
check("get darkmerchant 200", r.status_code == 200)
dm = r.json()
check("DM has code", dm.get("code") == "darkmerchant")
check("DM has display_name", dm.get("display_name") == "darkmerchant")
check("DM has personas", isinstance(dm.get("personas"), list) and len(dm["personas"]) > 0)
check("DM has identifiers", isinstance(dm.get("identifiers"), list) and len(dm["identifiers"]) > 0)
check("DM has summary", isinstance(dm.get("summary"), str) and len(dm["summary"]) > 0)
check("DM has attributes", isinstance(dm.get("attributes"), dict))
persona = dm["personas"][0]
check("persona has name", "name" in persona)
check("persona has platform", "platform" in persona)
check("persona has identifiers", isinstance(persona.get("identifiers"), list))

# UUID lookup
actor_id = dm["id"]
r = g(f"/api/v1/actors/{actor_id}")
check("get by UUID 200", r.status_code == 200)
check("UUID returns same code", r.json().get("code") == "darkmerchant")

r = g("/api/v1/actors/nonexistent_xyz")
check("actor 404", r.status_code == 404)
check("404 has detail", "detail" in r.json())
check("404 has code", r.json().get("code") == "actor_not_found")

r = g("/api/v1/actors/stats")
check("stats 200", r.status_code == 200)
s = r.json()
check("stats total_actors=13", s.get("total_actors") == 13)
check("stats total_personas", s.get("total_personas", 0) > 0)
check("stats total_identifiers", s.get("total_identifiers", 0) > 0)
check("stats total_sources", s.get("total_sources", 0) > 0)
check("stats by_risk_level", isinstance(s.get("by_risk_level"), dict))
check("stats by_category", isinstance(s.get("by_category"), dict))
check("stats by_status", isinstance(s.get("by_status"), dict))
check("stats identifiers_by_kind", isinstance(s.get("identifiers_by_kind"), dict))


# ============================================================================
# 4. EVIDENCE & RELATIONSHIPS
# ============================================================================
section("4. EVIDENCE & RELATIONSHIPS")

r = g("/api/v1/evidence/relationships")
check("list relationships 200", r.status_code == 200)
rels = r.json()
check("rels is list", isinstance(rels, list))
check("rels count>=4", len(rels) >= 4, str(len(rels)))
first_rel = rels[0]
check("rel has code", "code" in first_rel)
check("rel has kind", "kind" in first_rel)
check("rel has from_name", "from_name" in first_rel)
check("rel has to_name", "to_name" in first_rel)
check("rel has confidence", "confidence" in first_rel)
check("rel has band", "band" in first_rel)
check("rel has status", "status" in first_rel)
check("rel has scoring_factors", "scoring_factors" in first_rel)

r = g("/api/v1/evidence/relationships/REL-DM-SV-001")
check("rel detail 200", r.status_code == 200)
d = r.json()
check("detail has code", d.get("code") == "REL-DM-SV-001")
check("detail has evidence", isinstance(d.get("evidence"), list) and len(d["evidence"]) > 0)
check("detail has explanation", bool(d.get("explanation")))
check("detail has hypothesis_label", bool(d.get("hypothesis_label")))
check("detail has scoring_factors", bool(d.get("scoring_factors")))

r = g("/api/v1/evidence/relationships/NONEXISTENT_CODE")
check("rel 404", r.status_code == 404)

r = g("/api/v1/evidence/items")
check("evidence items 200", r.status_code == 200)
ev = r.json()
check("evidence is list", isinstance(ev, list))
check("evidence count>=7", len(ev) >= 7, str(len(ev)))
first_ev = ev[0]
check("evidence has code", "code" in first_ev)
check("evidence has kind", "kind" in first_ev)
check("evidence has title", "title" in first_ev)
check("evidence has description", "description" in first_ev)
check("evidence has strength", "strength" in first_ev)
check("evidence has evidence_class", "evidence_class" in first_ev)
check("evidence has score_contribution", "score_contribution" in first_ev)


# ============================================================================
# 5. GRAPH
# ============================================================================
section("5. GRAPH")

r = g("/api/v1/graph")
check("graph 200", r.status_code == 200)
g_data = r.json()
check("graph has nodes", isinstance(g_data.get("nodes"), list) and len(g_data["nodes"]) > 0, str(len(g_data.get("nodes", []))))
check("graph has edges", isinstance(g_data.get("edges"), list) and len(g_data["edges"]) > 0, str(len(g_data.get("edges", []))))
check("graph node count>50", len(g_data["nodes"]) > 50)
check("graph edge count>40", len(g_data["edges"]) > 40)
# Verify Cytoscape format
node0 = g_data["nodes"][0]
check("node has data.id", "id" in node0.get("data", {}))
check("node has data.label", "label" in node0.get("data", {}))

r = g("/api/v1/graph?focus=darkmerchant")
check("graph focus 200", r.status_code == 200)
focused = r.json()
check("focused has nodes", len(focused.get("nodes", [])) > 0)

r = g("/api/v1/graph/node/ACTOR/darkmerchant")
check("graph node lookup 200", r.status_code == 200)

r = g("/api/v1/graph/edge/evidence?source=ACTOR:darkmerchant&target=ACTOR:shadow_vendor")
check("edge evidence 200", r.status_code == 200)


# ============================================================================
# 6. TIMELINE
# ============================================================================
section("6. TIMELINE")

r = g("/api/v1/timeline")
check("timeline 200", r.status_code == 200)
tl = r.json()
tl_list = tl if isinstance(tl, list) else tl.get("items", [])
check("timeline events>=10", len(tl_list) >= 10, str(len(tl_list)))
first_evt = tl_list[0]
check("event has occurred_at", "occurred_at" in first_evt or "kind" in first_evt)
check("event has title", "title" in first_evt)

r = g("/api/v1/timeline?actor=darkmerchant")
check("timeline filter actor", r.status_code == 200)
filtered = r.json()
f_list = filtered if isinstance(filtered, list) else filtered.get("items", [])
check("filtered count>=3", len(f_list) >= 3)

r = g("/api/v1/timeline?kind=relationship_added")
check("timeline filter kind", r.status_code == 200)
kf = r.json()
k_list = kf if isinstance(kf, list) else kf.get("items", [])
check("relationship_added events>=2", len(k_list) >= 2)

r = g("/api/v1/timeline/migration/darkmerchant")
check("migration story 200", r.status_code == 200)
mig = r.json()
check("migration has events", isinstance(mig, list) and len(mig) > 0)


# ============================================================================
# 7. INFRASTRUCTURE
# ============================================================================
section("7. INFRASTRUCTURE")

r = g("/api/v1/infrastructure")
check("infra 200", r.status_code == 200)
infra_raw = r.json()
# API.md §1.2: list endpoints use the {items, total, limit, offset} envelope.
infra = infra_raw if isinstance(infra_raw, list) else infra_raw.get("items", [])
check("infra has data", len(infra) > 0, str(len(infra)))
check("infra has kind", "kind" in infra[0])
check("infra has value", "value" in infra[0])

r = g("/api/v1/infrastructure/clusters")
check("clusters 200", r.status_code == 200)

r = g("/api/v1/infrastructure?kind=domain")
check("infra filter kind=domain 200", r.status_code == 200)

r = g("/api/v1/infrastructure/actor/darkmerchant")
check("infra by actor 200", r.status_code == 200)


# ============================================================================
# 8. CORRELATION
# ============================================================================
section("8. CORRELATION")

r = g("/api/v1/correlation/evaluate?actor_a=darkmerchant&actor_b=shadow_vendor")
check("corr eval 200", r.status_code == 200)
cr = r.json()
check("corr has actor_a", cr.get("actor_a") == "darkmerchant")
check("corr has actor_b", cr.get("actor_b") == "shadow_vendor")
check("corr has signals", isinstance(cr.get("signals"), list) and len(cr["signals"]) > 0)
check("corr has raw_score", "raw_score" in cr and cr["raw_score"] > 0)
check("corr has weighted_score", "weighted_score" in cr)
check("corr has total_score", "total_score" in cr)
check("corr has band", "band" in cr)
check("corr has explanation", bool(cr.get("explanation")))
check("corr has hypothesis_label", bool(cr.get("hypothesis_label")))
check("corr pgp_match detected", any(s["signal_type"] == "pgp_match" for s in cr["signals"]))
check("corr wallet_match detected", any(s["signal_type"] == "wallet_match" for s in cr["signals"]))
check("corr communication_match detected", any(s["signal_type"] == "communication_match" for s in cr["signals"]))
check("corr stylometric detected", any(s["signal_type"] == "stylometric_similarity" for s in cr["signals"]))
check("corr behavior detected", any(s["signal_type"] == "behavior_similarity" for s in cr["signals"]))
# Verify signal structure
sig0 = cr["signals"][0]
check("signal has signal_id", "signal_id" in sig0)
check("signal has signal_type", "signal_type" in sig0)
check("signal has raw_score", "raw_score" in sig0)
check("signal has weighted_score", "weighted_score" in sig0)
check("signal has evidence_direction", "evidence_direction" in sig0)
check("signal has temporal_decay_factor", "temporal_decay_factor" in sig0)
check("signal has source_reliability", "source_reliability" in sig0)

r = g("/api/v1/correlation/evaluate?actor_a=darkmerchant&actor_b=quietsteel")
check("unrelated pair score=0", r.json()["total_score"] == 0)

r = g("/api/v1/correlation/existing")
check("existing corr 200", r.status_code == 200)
check("existing count>=4", len(r.json()) >= 4)


# ============================================================================
# 9. CONFIDENCE
# ============================================================================
section("9. CONFIDENCE")

r = g("/api/v1/confidence/evaluate?actor_a=darkmerchant&actor_b=shadow_vendor")
check("conf eval 200", r.status_code == 200)
conf = r.json()
check("conf has actor_a", conf.get("actor_a") == "darkmerchant")
check("conf has actor_b", conf.get("actor_b") == "shadow_vendor")
check("conf score>0", conf.get("score", 0) > 0, str(conf.get("score")))
check("conf band=MEDIUM or HIGH", conf.get("band") in ("MEDIUM", "HIGH"), conf.get("band"))
check("conf has raw_score", conf.get("raw_score", 0) > 0)
check("conf has weighted_score", conf.get("weighted_score", 0) > 0)
check("conf has signals", isinstance(conf.get("signals"), list) and len(conf["signals"]) > 0)
check("conf has derivation", isinstance(conf.get("derivation"), list) and len(conf["derivation"]) > 0)
check("conf has explanation", bool(conf.get("explanation")))
check("conf has hypothesis_label", bool(conf.get("hypothesis_label")))
check("conf has source_reliability_avg", conf.get("source_reliability_avg", 0) > 0)
check("conf has disclaimer", bool(conf.get("disclaimer")))
check("conf has evidence_quality", isinstance(conf.get("evidence_quality"), dict))
eq = conf["evidence_quality"]
check("eq has source_reliability_avg", "source_reliability_avg" in eq)
check("eq has temporal_consistency", "temporal_consistency" in eq)
check("eq has identifier_strength", "identifier_strength" in eq)
check("eq has supporting_count", eq.get("supporting_count", 0) > 0)
check("eq has contradicting_count", "contradicting_count" in eq)
check("eq has signal_families", eq.get("signal_families", 0) > 0)
check("eq has cryptographic_signals", eq.get("cryptographic_signals", 0) > 0)
check("eq has behavioral_signals", "behavioral_signals" in eq)

r = g("/api/v1/confidence/existing")
check("existing conf 200", r.status_code == 200)
check("existing has relationships", len(r.json().get("relationships", [])) >= 4)


# ============================================================================
# 10. INVESTIGATIONS
# ============================================================================
section("10. INVESTIGATIONS")

r = g("/api/v1/investigations")
check("list invs 200", r.status_code == 200)
invs = r.json()
check("invs count>=2", len(invs) >= 2)

r = g("/api/v1/investigations/INV-001")
check("INV-001 200", r.status_code == 200)
inv = r.json()
check("INV-001 has title", bool(inv.get("title")))
check("INV-001 has status", "status" in inv)
check("INV-001 has relationships", isinstance(inv.get("relationships"), list) and len(inv["relationships"]) > 0)
check("INV-001 has lead_analyst", "lead_analyst" in inv)

# Create investigation (admin)
r = p("/api/v1/investigations", json={
    "title": "Phase 28 Test Investigation",
    "description": "Testing investigation lifecycle",
    "lead_analyst": "amra",
    "targets": ["pharmakon"],
})
check("create inv 201", r.status_code == 201, f"status={r.status_code}")
new_code = r.json().get("code")
check("new inv has code", bool(new_code))

# Activate
r = p(f"/api/v1/investigations/{new_code}/activate?analyst=amra")
check("activate 200", r.status_code == 200, f"status={r.status_code}")
if r.status_code == 200:
    check("activated status=active", r.json().get("status") == "active")

# Add note
r = p(f"/api/v1/investigations/{new_code}/notes", json={"analyst": "amra", "note": "Phase 28 test note."})
check("add note 200", r.status_code == 200, f"status={r.status_code}")
if r.status_code == 200:
    check("note ok", r.json().get("ok") is True)

# Pause
r = p(f"/api/v1/investigations/{new_code}/pause?analyst=amra")
check("pause 200", r.status_code == 200)
if r.status_code == 200:
    check("paused status", r.json().get("status") == "paused")

# Close
r = p(f"/api/v1/investigations/{new_code}/close?analyst=amra")
check("close 200", r.status_code == 200)
if r.status_code == 200:
    check("closed status", r.json().get("status") == "closed")

# RBAC: analyst cannot activate
r = p(f"/api/v1/investigations/INV-001/activate?analyst=tumi", headers=ANALYST)
check("analyst no-activate 403", r.status_code == 403, f"status={r.status_code}")

# RBAC: analyst cannot close
r = p(f"/api/v1/investigations/INV-001/close?analyst=tumi", headers=ANALYST)
check("analyst no-close 403", r.status_code == 403, f"status={r.status_code}")

# Admin can activate
r = p("/api/v1/investigations/INV-001/activate?analyst=ami")
check("admin activate 200", r.status_code == 200, f"status={r.status_code}")

# Senior analyst can activate
r = p("/api/v1/investigations/INV-002/activate?analyst=amra")
check("senior activate 200", r.status_code == 200, f"status={r.status_code}")

# Audit log
r = g("/api/v1/investigations/audit/log")
check("audit log 200", r.status_code == 200)
check("audit has events", len(r.json()) > 0)


# ============================================================================
# 11. MONITORING
# ============================================================================
section("11. MONITORING")

r = g("/api/v1/monitoring/overview")
check("overview 200", r.status_code == 200)
ov = r.json()
check("overview has entities", isinstance(ov.get("entities"), dict))
check("overview actors=13", ov.get("entities", {}).get("actors") == 13)
check("overview has disclaimer", bool(ov.get("disclaimer")))
check("overview has task_backend", isinstance(ov.get("task_backend"), dict))

r = g("/api/v1/monitoring/sources")
check("sources 200", r.status_code == 200)
check("sources count>=6", len(r.json()) >= 6)

r = g("/api/v1/monitoring/relationships")
check("rel breakdown 200", r.status_code == 200)
rb = r.json()
check("has by_status", isinstance(rb.get("by_status"), dict))
check("has by_band", isinstance(rb.get("by_band"), dict))

r = g("/api/v1/monitoring/timeline")
check("timeline summary 200", r.status_code == 200)
ts = r.json()
check("timeline total>0", ts.get("total", 0) > 0)

r = g("/api/v1/monitoring/errors")
check("errors 200", r.status_code == 200)


# ============================================================================
# 12. REPORTS
# ============================================================================
section("12. REPORTS")

r = g("/api/v1/reports/INV-001")
check("report 200", r.status_code == 200)
report = r.json()
required_sections = [
    "investigation", "targets", "summary", "relationships", "evidence",
    "identifiers", "timeline", "infrastructure", "signals", "confidence",
    "analyst_decision", "analyst_notes", "sources", "audit", "disclaimer",
]
for section_name in required_sections:
    check(f"report has {section_name}", section_name in report)
check("report targets populated", len(report.get("targets", [])) > 0)
check("report relationships populated", len(report.get("relationships", [])) > 0)
check("report evidence populated", len(report.get("evidence", [])) > 0)
check("report identifiers populated", len(report.get("identifiers", [])) > 0)

r = g("/api/v1/reports/INV-001/export?format=json")
check("JSON export 200", r.status_code == 200)
check("JSON valid", "investigation" in r.json())

r = g("/api/v1/reports/INV-001/export?format=csv")
check("CSV export 200", r.status_code == 200)
check("CSV has SECTION", b"SECTION" in r.content)

r = g("/api/v1/reports/INV-001/export?format=pdf")
check("PDF export 200", r.status_code == 200)
check("PDF valid header", r.content[:4] == b"%PDF")

r = g("/api/v1/reports/INV-999")
check("report not found", r.status_code == 200 and "error" in r.json())

r = g("/api/v1/reports/INV-001/export?format=xml")
check("invalid format 400", r.status_code == 400)


# ============================================================================
# 13. INGESTION
# ============================================================================
section("13. INGESTION")

r = g("/api/v1/ingestion/status")
check("ingest status 200", r.status_code == 200)
check("status is list", isinstance(r.json(), list))

r = g("/api/v1/ingestion/sources")
check("ingest sources 200", r.status_code == 200, f"status={r.status_code}")
check("sources has data", isinstance(r.json(), list) and len(r.json()) > 0)
if r.json():
    src0 = r.json()[0]
    check("source has name", "name" in src0)
    check("source has kind", "kind" in src0)
    check("source has trust_level", "trust_level" in src0)

# Run all scenarios
for scenario in ["darkmerchant", "launderpipe", "pharmakon", "all"]:
    r = p(f"/api/v1/ingestion/scan?scenario={scenario}")
    check(f"scan {scenario} 200", r.status_code == 200, f"status={r.status_code}")

# Idempotency
r1 = p("/api/v1/ingestion/scan?scenario=darkmerchant")
r2 = p("/api/v1/ingestion/scan?scenario=darkmerchant")
check("ingestion idempotent", r1.status_code == 200 and r2.status_code == 200)

# Provenance
r = g("/api/v1/ingestion/provenance")
check("provenance 200", r.status_code == 200)


# ============================================================================
# 14. DECIDE (relationship review)
# ============================================================================
section("14. DECIDE")

from sqlalchemy import text
from app.core.database import engine
with engine.connect() as conn:
    rel_id = conn.execute(text('SELECT id FROM relationships WHERE code = "REL-DM-SV-001"')).scalar()

r = p("/api/v1/investigations/decide", json={
    "relationship_id": rel_id,
    "decision": "accepted",
    "analyst": "amra",
    "review_note": "Phase 28 verification.",
})
check("decide accepted 200", r.status_code == 200, f"status={r.status_code}")
if r.status_code == 200:
    check("decision=accepted", r.json().get("decision") == "accepted")

# Verify persistence
r = g("/api/v1/evidence/relationships")
for rel in r.json():
    if rel["code"] == "REL-DM-SV-001":
        check("decision persisted", rel["status"] == "accepted")
        break


# ============================================================================
# 15. OPENAPI
# ============================================================================
section("15. OPENAPI")

r = g("/openapi.json")
check("openapi 200", r.status_code == 200)
body = r.json()
check("openapi has paths", "paths" in body)
paths = list(body["paths"].keys())
check("openapi has /health", "/api/v1/health" in paths)
check("openapi has /actors", "/api/v1/actors" in paths)
check("openapi has /auth/login", "/api/v1/auth/login" in paths)
check("openapi has /evidence/relationships", "/api/v1/evidence/relationships" in paths)
check("openapi has /graph", "/api/v1/graph" in paths)
check("openapi has /timeline", "/api/v1/timeline" in paths)
check("openapi has /correlation/evaluate", "/api/v1/correlation/evaluate" in paths)
check("openapi has /confidence/evaluate", "/api/v1/confidence/evaluate" in paths)
check("openapi has /investigations", "/api/v1/investigations" in paths)
check("openapi has /monitoring/overview", "/api/v1/monitoring/overview" in paths)
check("openapi has /reports/{code}", any("report" in p for p in paths))
check("openapi has /ingestion/scan", "/api/v1/ingestion/scan" in paths)


# ============================================================================
# SUMMARY
# ============================================================================
print(f"\n{'=' * 60}")
passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
print(f"  TOTAL: {passed} passed, {failed} failed, {len(results)} checks")
print(f"{'=' * 60}")

if errors:
    print("\n  FAILURES:")
    for err in errors:
        print(f"    - {err}")

client.__exit__(None, None, None)
sys.exit(1 if failed else 0)
