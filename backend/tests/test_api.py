"""Smoke tests for every v1 endpoint.

Run: python -m pytest tests/test_api.py -v
Or:  python tests/test_api.py          (standalone)
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend/ is on sys.path when run standalone
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from fastapi.testclient import TestClient

from app.main import create_app

app = create_app()
client = TestClient(app, raise_server_exceptions=False)
# Trigger lifespan (creates tables + seeds data)
client.__enter__()


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _check(label: str, ok: bool, detail: str = "") -> None:
    icon = "PASS" if ok else "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{icon}] {label}{suffix}")
    assert ok, f"FAILED: {label} — {detail}"


# =========================================================================
# 1. Root
# =========================================================================
def test_root():
    _section("1. GET /")
    r = client.get("/")
    _check("status 200", r.status_code == 200, str(r.status_code))
    body = r.json()
    _check("has name", body.get("name") == "SHADOWGRAPH", str(body))
    _check("has version", "version" in body, str(body))
    _check("has docs link", body.get("docs") == "/docs", str(body))
    _check("has api prefix", body.get("api") == "/api/v1", str(body))


# =========================================================================
# 2. Health
# =========================================================================
def test_health():
    _section("2. GET /api/v1/health")
    r = client.get("/api/v1/health")
    _check("status 200", r.status_code == 200, str(r.status_code))
    body = r.json()
    _check("status=ok", body.get("status") == "ok", str(body.get("status")))
    _check("app name", body.get("app") == "SHADOWGRAPH")
    _check("version", body.get("version") == "0.1.0")

    adapters = body.get("adapters", {})
    _check("app_mode=local", adapters.get("app_mode") == "local")
    _check("database=sqlite", adapters.get("database") == "sqlite")
    _check("graph_backend=inprocess", adapters.get("graph_backend") == "inprocess")
    _check("task_backend=local", adapters.get("task_backend") == "local")

    checks = body.get("checks", {})
    _check("database check ok", "ok" in checks.get("database", ""), checks.get("database"))
    _check("graph check ok", "ok" in checks.get("graph", ""), checks.get("graph"))
    _check("tasks check ok", "ok" in checks.get("tasks", ""), checks.get("tasks"))


# =========================================================================
# 3. List actors (default)
# =========================================================================
def test_list_actors():
    _section("3. GET /api/v1/actors (default)")
    r = client.get("/api/v1/actors")
    _check("status 200", r.status_code == 200, str(r.status_code))
    body = r.json()
    _check("has items", isinstance(body.get("items"), list))
    _check("has total", isinstance(body.get("total"), int))
    _check("total > 0", body.get("total", 0) > 0, str(body.get("total")))
    _check("items not empty", len(body.get("items", [])) > 0)

    first = body["items"][0]
    _check("item has id", "id" in first)
    _check("item has code", "code" in first)
    _check("item has display_name", "display_name" in first)
    _check("item has risk_level", "risk_level" in first)
    _check("item has category", "category" in first)
    _check("item has attribution_confidence", "attribution_confidence" in first)
    _check("item has persona_count", "persona_count" in first)
    _check("item has identifier_count", "identifier_count" in first)


# =========================================================================
# 4. List actors with search
# =========================================================================
def test_list_actors_search():
    _section("4. GET /api/v1/actors?q=darkmerchant")
    r = client.get("/api/v1/actors", params={"q": "darkmerchant"})
    _check("status 200", r.status_code == 200)
    body = r.json()
    _check("found results", body["total"] >= 1, str(body["total"]))
    codes = [item["code"] for item in body["items"]]
    _check("darkmerchant in results", "darkmerchant" in codes, str(codes))


# =========================================================================
# 5. List actors with filters
# =========================================================================
def test_list_actors_filters():
    _section("5. GET /api/v1/actors (filters)")

    # Risk level filter
    r = client.get("/api/v1/actors", params={"risk_level": "critical"})
    _check("risk_level=critical status 200", r.status_code == 200)
    body = r.json()
    for item in body["items"]:
        _check(f"  {item['code']} is critical", item["risk_level"] == "critical")

    # Category filter
    r = client.get("/api/v1/actors", params={"category": "narcotics"})
    _check("category=narcotics status 200", r.status_code == 200)
    body = r.json()
    for item in body["items"]:
        _check(f"  {item['code']} is narcotics", item["category"] == "narcotics")

    # Status filter
    r = client.get("/api/v1/actors", params={"status": "dormant"})
    _check("status=dormant status 200", r.status_code == 200)
    body = r.json()
    for item in body["items"]:
        _check(f"  {item['code']} is dormant", item["status"] == "dormant")


# =========================================================================
# 6. List actors with sorting
# =========================================================================
def test_list_actors_sorting():
    _section("6. GET /api/v1/actors (sorting)")

    # Sort by risk ascending
    r = client.get("/api/v1/actors", params={"sort": "risk", "order": "asc"})
    _check("sort risk asc status 200", r.status_code == 200)
    body = r.json()
    risk_order = {"low": 1, "moderate": 2, "high": 3, "critical": 4}
    risks = [risk_order.get(i["risk_level"], 0) for i in body["items"]]
    _check("risk ascending", risks == sorted(risks), str(risks))

    # Sort by confidence descending
    r = client.get("/api/v1/actors", params={"sort": "confidence", "order": "desc"})
    _check("sort confidence desc status 200", r.status_code == 200)
    body = r.json()
    confs = [i["attribution_confidence"] for i in body["items"]]
    _check("confidence descending", confs == sorted(confs, reverse=True), str(confs))


# =========================================================================
# 7. List actors with pagination
# =========================================================================
def test_list_actors_pagination():
    _section("7. GET /api/v1/actors (pagination)")
    r = client.get("/api/v1/actors", params={"limit": 3, "offset": 0})
    _check("limit=3 status 200", r.status_code == 200)
    body = r.json()
    _check("items <= 3", len(body["items"]) <= 3, str(len(body["items"])))
    _check("limit=3", body["limit"] == 3)
    _check("offset=0", body["offset"] == 0)

    # Second page
    r2 = client.get("/api/v1/actors", params={"limit": 3, "offset": 3})
    _check("page 2 status 200", r2.status_code == 200)
    body2 = r2.json()
    ids1 = [i["id"] for i in body["items"]]
    ids2 = [i["id"] for i in body2["items"]]
    _check("no overlap", len(set(ids1) & set(ids2)) == 0)


# =========================================================================
# 8. Stats
# =========================================================================
def test_stats():
    _section("8. GET /api/v1/actors/stats")
    r = client.get("/api/v1/actors/stats")
    _check("status 200", r.status_code == 200)
    body = r.json()
    _check("total_actors > 0", body.get("total_actors", 0) > 0)
    _check("total_personas > 0", body.get("total_personas", 0) > 0)
    _check("total_identifiers > 0", body.get("total_identifiers", 0) > 0)
    _check("total_sources > 0", body.get("total_sources", 0) > 0)
    _check("by_risk_level is dict", isinstance(body.get("by_risk_level"), dict))
    _check("by_category is dict", isinstance(body.get("by_category"), dict))
    _check("by_status is dict", isinstance(body.get("by_status"), dict))
    _check("identifiers_by_kind is dict", isinstance(body.get("identifiers_by_kind"), dict))


# =========================================================================
# 9. Get actor by code
# =========================================================================
def test_get_actor_by_code():
    _section("9. GET /api/v1/actors/{code}")
    r = client.get("/api/v1/actors/darkmerchant")
    _check("status 200", r.status_code == 200)
    body = r.json()
    _check("code=darkmerchant", body.get("code") == "darkmerchant")
    _check("has display_name", body.get("display_name") == "darkmerchant")
    _check("has personas", isinstance(body.get("personas"), list))
    _check("personas not empty", len(body.get("personas", [])) > 0)
    _check("has identifiers", isinstance(body.get("identifiers"), list))
    _check("has summary", isinstance(body.get("summary"), str))
    _check("has attributes", isinstance(body.get("attributes"), dict))

    # Check persona structure
    persona = body["personas"][0]
    _check("persona has name", "name" in persona)
    _check("persona has platform", "platform" in persona)
    _check("persona has identifiers", isinstance(persona.get("identifiers"), list))


# =========================================================================
# 10. Get actor by UUID
# =========================================================================
def test_get_actor_by_uuid():
    _section("10. GET /api/v1/actors/{uuid}")
    # First get a known actor to extract its UUID
    r = client.get("/api/v1/actors/darkmerchant")
    actor_id = r.json()["id"]
    r2 = client.get(f"/api/v1/actors/{actor_id}")
    _check("status 200 by UUID", r2.status_code == 200)
    _check("same code", r2.json().get("code") == "darkmerchant")


# =========================================================================
# 11. Get actor 404
# =========================================================================
def test_get_actor_404():
    _section("11. GET /api/v1/actors/{nonexistent}")
    r = client.get("/api/v1/actors/nonexistent_actor_xyz")
    _check("status 404", r.status_code == 404, str(r.status_code))
    body = r.json()
    _check("has detail", "detail" in body)
    _check("has code=actor_not_found", body.get("code") == "actor_not_found")


# =========================================================================
# 12. Shadow vendor search (correlation demo pair)
# =========================================================================
def test_shadow_vendor_search():
    _section("12. Correlation demo pair: shadow_vendor search")
    r = client.get("/api/v1/actors", params={"q": "shadow_vendor"})
    _check("status 200", r.status_code == 200)
    body = r.json()
    codes = [i["code"] for i in body["items"]]
    _check("shadow_vendor found", "shadow_vendor" in codes, str(codes))


# =========================================================================
# 13. Search by PGP fingerprint
# =========================================================================
def test_search_by_identifier():
    _section("13. Search by identifier value (PGP fingerprint)")
    r = client.get("/api/v1/actors", params={"q": "9F2A4C81D3E5B7091A62F84C5D30E7B29C41A8F6"})
    _check("status 200", r.status_code == 200)
    body = r.json()
    _check("found via PGP search", body["total"] >= 1, str(body["total"]))
    codes = [i["code"] for i in body["items"]]
    _check("darkmerchant or shadow_vendor in results",
           "darkmerchant" in codes or "shadow_vendor" in codes, str(codes))


# =========================================================================
# 14. OpenAPI schema
# =========================================================================
def test_openapi():
    _section("14. GET /openapi.json")
    r = client.get("/openapi.json")
    _check("status 200", r.status_code == 200)
    body = r.json()
    _check("has paths", "paths" in body)
    paths = list(body["paths"].keys())
    _check("has /api/v1/health", "/api/v1/health" in paths, str(paths))
    _check("has /api/v1/actors", "/api/v1/actors" in paths, str(paths))
    _check("has /api/v1/actors/stats", "/api/v1/actors/stats" in paths, str(paths))
    _check("has /api/v1/actors/{actor_ref}", any("actor_ref" in p for p in paths), str(paths))


# =========================================================================
# Summary
# =========================================================================
if __name__ == "__main__":
    tests = [
        test_root,
        test_health,
        test_list_actors,
        test_list_actors_search,
        test_list_actors_filters,
        test_list_actors_sorting,
        test_list_actors_pagination,
        test_stats,
        test_get_actor_by_code,
        test_get_actor_by_uuid,
        test_get_actor_404,
        test_shadow_vendor_search,
        test_search_by_identifier,
        test_openapi,
    ]

    passed = 0
    failed = 0
    errors: list[str] = []

    for fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            failed += 1
            errors.append(str(e))
        except Exception as e:
            failed += 1
            errors.append(f"{fn.__name__}: {type(e).__name__}: {e}")

    print(f"\n{'=' * 60}")
    print(f"  SUMMARY: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'=' * 60}")

    if errors:
        print("\n  FAILURES:")
        for err in errors:
            print(f"    - {err}")

    client.__exit__(None, None, None)
    print()
    sys.exit(1 if failed else 0)
