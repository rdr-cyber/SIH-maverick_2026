# SIH Pitch — SHADOWGRAPH

**Problem Statement 26151 · Dark Web Threat Actor De-anonymization · NTRO**
**Theme:** Blockchain & Cybersecurity · Category: Software

## One-liner
> SHADOWGRAPH connects clues across marketplaces, explains evidence with a living graph,
> and gives investigators defensible — never overclaiming — attribution hypotheses.

## The problem
Threat actors move between marketplaces, forums, wallets, keys, and infrastructure.
Investigators drown in disconnected fragments: a handle here, a PGP key there, a domain in
this archive, a wallet in that index. Manual correlation is slow, error-prone, and
unfalsifiable — analysts can't easily prove *why* two personas look related, and lookalikes
(fake accounts, copycats, shared hosting) actively mislead.

## The SIH response
A single platform that:
1. **Ingests** authorized/synthetic intelligence (with provenance on every fact),
2. **Correlates** across PGP, wallets, handles, infrastructure, writing style, and behavior,
3. **Explains** every hypothesis with evidence IDs, scoring factors, and human-readable WHY,
4. **Guards** truth with human-in-the-loop review and a strict "hypothesis ≠ verdict" vocabulary,
5. **Demonstrates** the whole thing offline, on a deterministic synthetic ecosystem, in five
   minutes, with a false-positive case on stage.

## Innovations / technical differentiators
- **Explainable evidence graph** — every rendered edge is real backend state; clicking an edge
  shows the full evidence chain and its **Relationship Confidence Score** (never "probability").
- **Modular multi-signal correlation engine** with configurable weights — PGP 30 · Wallet 25 ·
  Handle 15 · Infrastructure 15 · Stylometry 10 · Behavior 5.
- **Stylometric & behavioral profiling** with reliability gates and honest limitation notes.
- **Intelligence taxonomy** enforced end-to-end: OBSERVED FACT → DERIVED SIGNAL →
  CORRELATION → ANALYST HYPOTHESIS.
- **False-positive engineered in** — Beta's `shadow_vend0r` lookalike *must not* merge; the demo
  shows the system refusing a plausible-sounding link.
- **True three-tier architecture** — Postgres as system of record, Neo4j as correlation index,
  Redis-backed workers for autonomous monitoring; everything containerized, everything audited.
- **Offline & reproducible** — seeded synthetic dataset, no live dark web, no runtime egress.

## Impact (framed for judges)
- **For defenders:** faster, evidenced attribution; less tunnel-vision on single signals;
  reporting that stands up to review.
- **For policy/ethics:** by construction it never claims real-world identity — only personas,
  evidence, and hypotheses — keeping intelligence defensible and lawful.
- **For the ecosystem:** an open-architecture, ethics-bounded blueprint that any intelligence
  unit could extend with *their own authorized connectors.

## Ethics & safety (the board we stand on)
- Synthetic-only demo dataset; no real systems, Tor, credentials, or people touched.
- Connector boundary rejects non-authorized sources.
- Every inference requires senior-analyst review; every action is audit-logged.
- Terminology discipline: **Relationship Confidence Score**, not probability.

## The 5-minute story
Disappear → Reappear → Detect → Correlate (PGP → wallet → style → behavior) → Graph connects →
Timeline shows migration → Evidence explains WHY → Confidence → HIGH → Analyst reviews →
Report exports. Plus: the lookalike that *doesn't* merge.

## Team roles (for the presentation)
- **Architect** — 3-tier design, Neo4j/Postgres split, autonomy
- **Cybersecurity strategist** — threat model, RBAC, offline guarantee, ethics
- **Product designer** — intelligence UX, evidence graph, timeline, report flow
- **Lead engineer (us)** — implementation, pipeline, demo mode, testing

## Demo safety nets
`DEMO.md` §6: embedded no-Docker mode, API-first demo, pre-generated exports.

## Call to action
"Fund and field it with your authorized data connectors — the engine, the graph, the
explainability, and the guards are already built."
