# AGENTS.md — SHADOWGRAPH Session Learnings

## Architecture

- **Single source of truth for RCS**: The `ConfidenceEngine` computes the authoritative Relationship Confidence Score at seed time (`seed.py`), stores it in the `relationships.confidence` DB column, and all UI surfaces read from there. Never hardcode RCS values in `catalog.py`.
- **Signal dataclass field naming**: Use `signal_type` not `type` in the Signal dataclass (avoids shadowing Python's built-in). The correlation API returns `signal_type`, and tests must match this.
- **Auth dependency placement**: Router-level `dependencies=[Depends(get_current_user)]` is the cleanest way to protect all endpoints in a router. Individual routes don't need per-route auth deps when the whole router is protected.
- **Parameter ordering**: FastAPI dependency-injected params must follow Python rules — params with defaults (`Depends(...)`) must come after params without defaults. Put session deps before user deps.

## Testing

- **Test DB path**: Use unique `DATABASE_URL` paths per test run to avoid SQLite file lock conflicts on Windows. Example: `DATABASE_URL="sqlite:///./data/test_name.db"`.
- **Auth in tests**: All protected endpoint tests need auth headers. Add `AUTH = {"Authorization": f"Bearer {token}"}` after login and use `_get(url, headers=AUTH)` helpers.
- **test_full.py timeline/infra shape**: Timeline and infrastructure endpoints return `{"items": [...], "total": N}` not a plain list. Tests must extract `.get("items", [])` before indexing.
- **test_full.py correlation field**: The correlation API returns `signal_type` not `type` — tests checking signal type must use `s["signal_type"]`.

## Signal Engine

- **Stylometry false positive**: Sharing just `languages: ["en"]` triggers stylometry (Jaccard=1.0). Require ≥2 shared languages to avoid false positives between unrelated actors.
- **Behavior time overlap**: Use `_time_overlap()` with wrapping at 24h, not exact string match on `active_hours_utc`. Values like "21:00-05:00" vs "21:30-05:30" are functionally identical.
- **Handle similarity threshold**: Character n-gram cosine > 0.5 for handle similarity. The old character-overlap ratio approach gave false negatives.

## Windows-Specific

- **ripgrep unavailable**: The vendored ripgrep in the Codebuff client may be missing on Windows. Use `read_files` + manual inspection instead of `code_search` when it fails.
- **Port reuse**: Windows holds ports in TIME_WAIT after process kill. Use `taskkill //F //PID` and wait before rebinding.
- **File locking**: SQLite on Windows doesn't allow concurrent writes. Kill stale Python processes before starting new servers.

## Configuration

- **Secret key**: Auto-generated per-process in LOCAL mode. Production requires explicit `SECRET_KEY` env var.
- **Correlation weights**: Stored in `DEFAULT_CORRELATION_WEIGHTS` in `config.py`. The `jabber: 10` weight was added in Phase 21.
- **Band thresholds**: LOW < 40, MEDIUM 40-69, HIGH ≥ 70. Both correlation and confidence engines use the same thresholds.

## Ingestion Pipeline

- **Entity resolution must return MULTIPLE matches**: When the same identifier exists for multiple actors (e.g., shared PGP), `resolve_entities()` must return a ResolvedEntity for EACH actor. Otherwise the relationship creation step can't detect cross-actor sharing. Use a dict of lists, not a single-match dict.
- **Flush before confidence recomputation**: After creating new relationships in the pipeline, call `session.flush()` BEFORE the confidence engine recompute loop. SQLAlchemy queries go to the DB, not the identity map, so unflushed relationships are invisible.
- **ScoringFactor score type**: The confidence engine produces float scores (e.g., `round(weighted_score, 1)`). The Pydantic `ScoringFactor` schema must use `score: float` not `score: int` to avoid 422 validation errors on the evidence/relationships endpoint.
- **Idempotency via deterministic IDs**: Use `hashlib.sha256(actor_pair_code).hexdigest()[:12]` for relationship codes, NOT source names. Different observations of the same actor pair must produce the same code.
- **Pipeline flow**: RawObservation → extract_entities_from_fields (field_extract, 0.95 confidence) + extract_entities_from_content (content_scan, 0.7-0.9 confidence) → resolve_entities (exact_normalized_match, 0.95) → create_relationships_from_resolved (group by actor, find shared kinds) → ConfidenceEngine recomputation.
