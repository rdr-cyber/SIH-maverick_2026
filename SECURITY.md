# SECURITY — Design (Phase 1)

SHADOWGRAPH is a defensive prototype; its own security posture matters as much as the
intelligence domain rules. No credentials live in source code — everything comes from
environment variables (see `.env.example`).

## 1. Authentication

- **JWT access tokens** (HS256, 15 min) + **rotatable refresh tokens** (7 d, stored server-side,
  revocable). `python-jose`/`PyJWT` with strict claim validation.
- Passwords: **Argon2id** (hash, salt, memory-hard) via `argon2-cffi`. Bootstrap demo accounts
  get hashed secrets from env at startup; `must_change_password` flag for demo accounts.
- Login/refresh/logout events written to `audit_events` (`auth.*`).

## 2. Authorization (RBAC)

| Capability | analyst | senior_analyst | admin |
|------------|:-------:|:--------------:|:-----:|
| Read intelligence, graph, timeline, reports | ✅ | ✅ | ✅ |
| Create investigations, notes, targets | ✅ | ✅ | ✅ |
| **Review relationships** (accept/reject/uncertain) | – | ✅ | ✅ |
| Create actors/evidence manually | – | ✅ | ✅ |
| Trigger scans / RUN INVESTIGATION | – | ✅ | ✅ |
| Manage analysts, audit log, global weights, resync | – | – | ✅ |

Enforced server-side via FastAPI dependency (`require_role`). UI hides unauthorized actions.

## 3. Input validation & injection defense

- Pydantic v2 schemas validate **every** request body/query — strict types, enum checks.
- All SQL via SQLAlchemy **parameterized statements**; all Cypher via the driver's
  **parameter dictionary** (no f-string interpolation into queries, ever).
- Files (reports uploads) restricted by extension/type/size; downloads served via
  authenticated endpoint with `Content-Disposition`.
- Rate limiting: Redis sliding-window per `(ip, route bucket)` and per-user; 120 req/min
  default (configurable). 429 with `Retry-After`.

## 4. Secure headers & transport

- Middleware sets: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, CSP for the SPA.
- HSTS only in `prod`/`demo` behind TLS; dev allows HTTP on localhost.
- CORS restricted to `CORS_ORIGINS` env list (defaults to local dev origins).

## 5. Secrets & configuration

- `.env` gitignored (`.gitignore` present); `docker-compose` reads `${VAR:?}` so missing
  secrets fail fast.
- Different `SECRET_KEY`/DB/Neo4j passwords per environment; rotation documented.
- No secrets in logs: `filter_secrets` logging filter redacts password/token fields.

## 6. Audit logging

- Append-only `audit_events` (no UPDATE/DELETE at the app layer; DB role has no grant).
- Captured: actor (or `is_system`), action (`auth.login`, `rel.accept`, `investigation.create`,
  `scan.tick`, `report.generate`, `alert.acknowledge`, …), resource, before/after JSON,
  IP, user-agent, note. Analysts must provide a note on relationship review.

## 7. Team access & safe error handling

- API errors never leak stack traces: `request_id` returned, trace to server log only
  (safe-error middleware).
- Data-access checks: analysts only see intelligence their role permits; investigation
  participants list enforced for private notes.
- All demo accounts are non-privileged by default (`demo_analyst` = analyst role).

## 8. Container hardening

- Backend runs as non-root; minimal base images (python:3.12-slim; frontend served by
  nginx:alpine). Read-only root FS where practical; separate network for services.
- Neo4j/Postgres ports are **not** published in the demo profile (internal network only);
  developer profile publishes to localhost.

## 9. Threat model summary (for the design review)

| Threat | Mitigation |
|--------|-----------|
| Unauthorized API access | JWT + RBAC dependency on every protected route |
| Credential theft | Argon2id, refresh rotation, rate limit, audit |
| Injection (SQL/Cypher/NoSQL) | Parameterized queries everywhere |
| Data exfiltration via reports | RBAC read, download authN, storage_key validation |
| Secret exposure | .env-gitignore, fail-fast env, no secrets in logs |
| Compromised worker | workers hold no admin powers; tasks validate inputs |
| Insider misuse of correlation | relationship review requires senior analyst; audit trail; no real data in demo |

## 10. Verification in Phase 13

Security test suite: login/refresh/logout flows, RBAC matrix (every route × role),
parameterized-query tests for all repositories, rate-limit 429 behavior, secure-header
presence, audit event creation per critical action, safe-error shape (no stack traces),
`.env` absence in container image, non-root user check, and dependency vulnerability scan
(pip-audit + npm audit) in CI.
