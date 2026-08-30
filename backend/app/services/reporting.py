"""Investigation Report service.

Assembles a complete investigation report from real database records.
Every section comes from the actual investigation, actors, relationships,
evidence, timeline, infrastructure, and audit trail.

Exports: JSON, CSV, PDF.

IMPORTANT: All data comes from the database. No fabricated content.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.identity import Actor, Identifier, Persona, Source
from app.models.intel import Evidence, Relationship, TimelineEvent
from app.models.ops import Analyst, AuditEvent, Investigation

log = logging.getLogger(__name__)


class ReportService:
    """Assembles investigation reports from real data."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def generate_report(self, investigation_code: str) -> dict[str, Any] | None:
        """Generate a complete investigation report."""
        inv = self.session.execute(
            select(Investigation).where(Investigation.code == investigation_code)
        ).scalar_one_or_none()
        if not inv:
            return None

        # Resolve lead analyst
        lead = self.session.get(Analyst, inv.lead_analyst_id) if inv.lead_analyst_id else None

        # Resolve target actors
        target_actors = self._resolve_targets(inv.targets or [])
        target_codes = [a["code"] for a in target_actors]

        # Get relationships involving targets
        relationships = self._get_target_relationships(target_codes)
        rel_ids = [r["id"] for r in relationships]

        # Get evidence for those relationships
        evidence = self._get_evidence_for_relationships(rel_ids)

        # Get identifiers for target actors
        identifiers = self._get_identifiers_for_actors(target_codes)

        # Get timeline events for target actors
        timeline = self._get_timeline_for_actors(target_codes)

        # Get infrastructure for target actors
        infrastructure = self._get_infrastructure_for_actors(target_codes)

        # Get signals (from relationship scoring factors)
        signals = self._extract_signals(relationships)

        # Get confidence scores
        confidence = self._get_confidence(relationships)

        # Get analyst notes
        notes = self._get_analyst_notes(inv)

        # Get audit trail
        audit = self._get_audit_trail(inv)

        # Get source information
        sources = self._get_sources_for_targets(target_codes)

        report = {
            "report_type": "investigation",
            "generated_at": datetime.utcnow().isoformat(),
            "disclaimer": (
                "This report is generated from database records. "
                "Relationship Confidence Scores are decision heuristics, "
                "NOT probabilities of identity. Every inference requires "
                "human review."
            ),
            "investigation": {
                "code": inv.code,
                "title": inv.title,
                "description": inv.description,
                "status": inv.status,
                "lead_analyst": lead.username if lead else "unknown",
                "created_at": inv.created_at.isoformat() if inv.created_at else "",
                "updated_at": inv.updated_at.isoformat() if inv.updated_at else "",
            },
            "targets": target_actors,
            "summary": self._build_summary(inv, target_actors, relationships, evidence),
            "identifiers": identifiers,
            "relationships": relationships,
            "evidence": evidence,
            "timeline": timeline,
            "infrastructure": infrastructure,
            "signals": signals,
            "confidence": confidence,
            "analyst_decision": self._get_analyst_decisions(relationships),
            "analyst_notes": notes,
            "sources": sources,
            "audit": audit,
        }
        return report

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _resolve_targets(self, target_codes: list[str]) -> list[dict]:
        actors = []
        for code in target_codes:
            actor = self.session.execute(
                select(Actor).where(Actor.code == code)
            ).scalar_one_or_none()
            if actor:
                persona_count = self.session.execute(
                    select(func.count(Persona.id)).where(Persona.actor_id == actor.id)
                ).scalar() or 0
                id_count = self.session.execute(
                    select(func.count(Identifier.id)).where(Identifier.actor_id == actor.id)
                ).scalar() or 0
                actors.append({
                    "code": actor.code,
                    "display_name": actor.display_name,
                    "status": actor.status,
                    "risk_level": actor.risk_level,
                    "category": actor.category,
                    "attribution_confidence": actor.attribution_confidence,
                    "summary": actor.summary,
                    "persona_count": persona_count,
                    "identifier_count": id_count,
                    "first_seen": actor.first_seen.isoformat() if actor.first_seen else None,
                    "last_seen": actor.last_seen.isoformat() if actor.last_seen else None,
                })
        return actors

    def _get_target_relationships(self, target_codes: list[str]) -> list[dict]:
        if not target_codes:
            return []

        # Get actor IDs
        actor_ids = set()
        actor_map = {}
        for code in target_codes:
            actor = self.session.execute(
                select(Actor).where(Actor.code == code)
            ).scalar_one_or_none()
            if actor:
                actor_ids.add(actor.id)
                actor_map[actor.id] = code

        if not actor_ids:
            return []

        stmt = select(Relationship).where(
            Relationship.from_id.in_(actor_ids) | Relationship.to_id.in_(actor_ids)
        )
        rels = list(self.session.execute(stmt).scalars().all())

        results = []
        for rel in rels:
            from_code = actor_map.get(rel.from_id, rel.from_id)
            to_code = actor_map.get(rel.to_id, rel.to_id)
            results.append({
                "id": rel.id,
                "code": rel.code,
                "kind": rel.kind,
                "from_actor": from_code,
                "to_actor": to_code,
                "confidence": rel.confidence,
                "band": rel.band,
                "status": rel.status,
                "scoring_factors": rel.scoring_factors or [],
                "explanation": rel.explanation,
                "hypothesis_label": rel.hypothesis_label,
                "reviewed_by": rel.reviewed_by,
                "review_note": rel.review_note,
                "first_seen": rel.first_seen.isoformat() if rel.first_seen else None,
                "last_seen": rel.last_seen.isoformat() if rel.last_seen else None,
            })
        return results

    def _get_evidence_for_relationships(self, rel_ids: list[str]) -> list[dict]:
        if not rel_ids:
            return []
        stmt = select(Evidence).where(Evidence.relationship_id.in_(rel_ids))
        items = list(self.session.execute(stmt).scalars().all())
        return [
            {
                "code": e.code,
                "kind": e.kind,
                "title": e.title,
                "description": e.description,
                "strength": e.strength,
                "evidence_class": e.evidence_class,
                "score_contribution": e.score_contribution,
                "details": e.details or {},
            }
            for e in items
        ]

    def _get_identifiers_for_actors(self, target_codes: list[str]) -> list[dict]:
        if not target_codes:
            return []
        actor_ids = set()
        actor_map = {}
        for code in target_codes:
            actor = self.session.execute(
                select(Actor).where(Actor.code == code)
            ).scalar_one_or_none()
            if actor:
                actor_ids.add(actor.id)
                actor_map[actor.id] = code
        if not actor_ids:
            return []

        stmt = select(Identifier).where(Identifier.actor_id.in_(actor_ids))
        ids = list(self.session.execute(stmt).scalars().all())
        return [
            {
                "actor": actor_map.get(i.actor_id, i.actor_id),
                "kind": i.kind,
                "value": i.value,
                "label": i.label,
                "first_seen": i.first_seen.isoformat() if i.first_seen else None,
                "last_seen": i.last_seen.isoformat() if i.last_seen else None,
            }
            for i in ids
        ]

    def _get_timeline_for_actors(self, target_codes: list[str]) -> list[dict]:
        if not target_codes:
            return []
        actor_ids = set()
        actor_map = {}
        for code in target_codes:
            actor = self.session.execute(
                select(Actor).where(Actor.code == code)
            ).scalar_one_or_none()
            if actor:
                actor_ids.add(actor.id)
                actor_map[actor.id] = code
        if not actor_ids:
            return []

        stmt = (
            select(TimelineEvent)
            .where(TimelineEvent.actor_id.in_(actor_ids))
            .order_by(TimelineEvent.occurred_at)
        )
        events = list(self.session.execute(stmt).scalars().all())
        return [
            {
                "occurred_at": e.occurred_at.isoformat(),
                "kind": e.kind,
                "actor": actor_map.get(e.actor_id, e.actor_id),
                "title": e.title,
                "detail": e.detail,
            }
            for e in events
        ]

    def _get_infrastructure_for_actors(self, target_codes: list[str]) -> list[dict]:
        if not target_codes:
            return []
        actor_ids = set()
        actor_map = {}
        for code in target_codes:
            actor = self.session.execute(
                select(Actor).where(Actor.code == code)
            ).scalar_one_or_none()
            if actor:
                actor_ids.add(actor.id)
                actor_map[actor.id] = code
        if not actor_ids:
            return []

        # Infrastructure = onion_service and domain identifiers
        stmt = (
            select(Identifier)
            .where(Identifier.actor_id.in_(actor_ids))
            .where(Identifier.kind.in_(["onion_service", "domain"]))
        )
        items = list(self.session.execute(stmt).scalars().all())
        return [
            {
                "actor": actor_map.get(i.actor_id, i.actor_id),
                "kind": i.kind,
                "value": i.value,
                "label": i.label,
                "first_seen": i.first_seen.isoformat() if i.first_seen else None,
            }
            for i in items
        ]

    def _extract_signals(self, relationships: list[dict]) -> list[dict]:
        signals = []
        for rel in relationships:
            for factor in rel.get("scoring_factors", []):
                signals.append({
                    "relationship": rel["code"],
                    "signal": factor.get("signal", ""),
                    "weight": factor.get("weight", 0),
                    "score": factor.get("score", 0),
                    "note": factor.get("note", ""),
                })
        return signals

    def _get_confidence(self, relationships: list[dict]) -> list[dict]:
        return [
            {
                "relationship": rel["code"],
                "from_actor": rel["from_actor"],
                "to_actor": rel["to_actor"],
                "confidence": rel["confidence"],
                "band": rel["band"],
                "status": rel["status"],
            }
            for rel in relationships
        ]

    def _get_analyst_decisions(self, relationships: list[dict]) -> list[dict]:
        return [
            {
                "relationship": rel["code"],
                "from_actor": rel["from_actor"],
                "to_actor": rel["to_actor"],
                "decision": rel["status"],
                "reviewed_by": rel.get("reviewed_by"),
                "review_note": rel.get("review_note"),
            }
            for rel in relationships
            if rel["status"] in ("accepted", "rejected", "uncertain")
        ]

    def _get_analyst_notes(self, inv: Investigation) -> list[dict]:
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.resource_type == "investigations")
            .where(AuditEvent.resource_id == inv.id)
            .where(AuditEvent.action == "investigation_note_added")
            .order_by(AuditEvent.occurred_at)
        )
        events = list(self.session.execute(stmt).scalars().all())
        notes = []
        for e in events:
            analyst = self.session.get(Analyst, e.analyst_id) if e.analyst_id else None
            notes.append({
                "analyst": analyst.username if analyst else "unknown",
                "note": e.note or "",
                "occurred_at": e.occurred_at.isoformat(),
            })
        return notes

    def _get_audit_trail(self, inv: Investigation) -> list[dict]:
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.resource_type == "investigations")
            .where(AuditEvent.resource_id == inv.id)
            .order_by(AuditEvent.occurred_at)
        )
        events = list(self.session.execute(stmt).scalars().all())
        result = []
        for e in events:
            analyst = self.session.get(Analyst, e.analyst_id) if e.analyst_id else None
            result.append({
                "action": e.action,
                "analyst": analyst.username if analyst else "system",
                "before": e.before_json,
                "after": e.after_json,
                "note": e.note,
                "occurred_at": e.occurred_at.isoformat(),
            })
        return result

    def _get_sources_for_targets(self, target_codes: list[str]) -> list[dict]:
        if not target_codes:
            return []
        stmt = select(Source).order_by(Source.name)
        sources = list(self.session.execute(stmt).scalars().all())
        return [
            {
                "name": s.name,
                "kind": s.kind,
                "reliability": s.reliability,
                "last_scanned_at": s.last_scanned_at.isoformat() if s.last_scanned_at else None,
            }
            for s in sources
        ]

    def _build_summary(
        self,
        inv: Investigation,
        targets: list[dict],
        relationships: list[dict],
        evidence: list[dict],
    ) -> str:
        target_names = [t["code"] for t in targets]
        rel_count = len(relationships)
        ev_count = len(evidence)
        accepted = sum(1 for r in relationships if r["status"] == "accepted")
        rejected = sum(1 for r in relationships if r["status"] == "rejected")
        pending = sum(1 for r in relationships if r["status"] == "pending")

        parts = [
            f"Investigation '{inv.title}' ({inv.code}) targets {', '.join(target_names)}.",
            f"Status: {inv.status}.",
            f"Found {rel_count} relationship(s) with {ev_count} evidence items.",
        ]
        if accepted:
            parts.append(f"{accepted} accepted.")
        if rejected:
            parts.append(f"{rejected} rejected.")
        if pending:
            parts.append(f"{pending} pending analyst review.")
        return " ".join(parts)


# ------------------------------------------------------------------
# Export formatters
# ------------------------------------------------------------------

def export_json(report: dict[str, Any]) -> str:
    """Export report as formatted JSON string."""
    return json.dumps(report, indent=2, default=str)


def export_csv(report: dict[str, Any]) -> str:
    """Export report as CSV — one section per logical group."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    # Section: Investigation
    writer.writerow(["SECTION", "Investigation"])
    writer.writerow(["Code", report["investigation"]["code"]])
    writer.writerow(["Title", report["investigation"]["title"]])
    writer.writerow(["Status", report["investigation"]["status"]])
    writer.writerow(["Lead Analyst", report["investigation"]["lead_analyst"]])
    writer.writerow(["Description", report["investigation"].get("description", "")])
    writer.writerow([])

    # Section: Targets
    writer.writerow(["SECTION", "Targets"])
    writer.writerow(["Code", "Display Name", "Risk Level", "Category", "Status", "Confidence", "First Seen", "Last Seen"])
    for t in report["targets"]:
        writer.writerow([
            t["code"], t["display_name"], t["risk_level"], t["category"],
            t["status"], t["attribution_confidence"],
            t.get("first_seen", ""), t.get("last_seen", ""),
        ])
    writer.writerow([])

    # Section: Relationships
    writer.writerow(["SECTION", "Relationships"])
    writer.writerow(["Code", "Kind", "From", "To", "Confidence", "Band", "Status", "Hypothesis"])
    for r in report["relationships"]:
        writer.writerow([
            r["code"], r["kind"], r["from_actor"], r["to_actor"],
            r["confidence"], r["band"], r["status"],
            r.get("hypothesis_label", ""),
        ])
    writer.writerow([])

    # Section: Evidence
    writer.writerow(["SECTION", "Evidence"])
    writer.writerow(["Code", "Kind", "Title", "Strength", "Class", "Score", "Description"])
    for e in report["evidence"]:
        writer.writerow([
            e["code"], e["kind"], e["title"], e["strength"],
            e["evidence_class"], e["score_contribution"], e["description"],
        ])
    writer.writerow([])

    # Section: Identifiers
    writer.writerow(["SECTION", "Identifiers"])
    writer.writerow(["Actor", "Kind", "Value", "Label"])
    for i in report["identifiers"]:
        writer.writerow([i["actor"], i["kind"], i["value"], i.get("label", "")])
    writer.writerow([])

    # Section: Timeline
    writer.writerow(["SECTION", "Timeline"])
    writer.writerow(["Date", "Actor", "Kind", "Title", "Detail"])
    for t in report["timeline"]:
        writer.writerow([t["occurred_at"], t["actor"], t["kind"], t["title"], t.get("detail", "")])
    writer.writerow([])

    # Section: Confidence
    writer.writerow(["SECTION", "Confidence Scores"])
    writer.writerow(["Relationship", "From", "To", "Score", "Band", "Status"])
    for c in report["confidence"]:
        writer.writerow([c["relationship"], c["from_actor"], c["to_actor"], c["confidence"], c["band"], c["status"]])
    writer.writerow([])

    # Section: Analyst Decisions
    writer.writerow(["SECTION", "Analyst Decisions"])
    writer.writerow(["Relationship", "From", "To", "Decision", "Reviewed By", "Note"])
    for d in report["analyst_decision"]:
        writer.writerow([d["relationship"], d["from_actor"], d["to_actor"], d["decision"], d.get("reviewed_by", ""), d.get("review_note", "")])
    writer.writerow([])

    # Section: Sources
    writer.writerow(["SECTION", "Sources"])
    writer.writerow(["Name", "Kind", "Reliability", "Last Scanned"])
    for s in report["sources"]:
        writer.writerow([s["name"], s["kind"], s["reliability"], s.get("last_scanned_at", "")])

    return buf.getvalue()



# ------------------------------------------------------------------
# PDF export
# ------------------------------------------------------------------

def _sanitize_pdf_text(text: str) -> str:
    """Replace Unicode chars that Helvetica cannot render in fpdf2."""
    replacements = {
        chr(0x2026): '...',   # ellipsis
        chr(0x2014): ' - ',   # em dash
        chr(0x2013): '-',     # en dash
        chr(0x2018): "'",    # left single quote
        chr(0x2019): "'",    # right single quote
        chr(0x201c): '"',    # left double quote
        chr(0x201d): '"',    # right double quote
        chr(0x2022): '*',     # bullet
        chr(0x2192): '->',    # right arrow
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    result = []
    for ch in text:
        try:
            ch.encode('latin-1')
            result.append(ch)
        except UnicodeEncodeError:
            result.append('?')
    return ''.join(result)


class _SafePDF:
    """Thin wrapper around FPDF that sanitizes text for Helvetica."""

    def __init__(self):
        from fpdf import FPDF
        self._pdf = FPDF()
        self._pdf.set_auto_page_break(auto=True, margin=15)

    def __getattr__(self, name):
        return getattr(self._pdf, name)

    def multi_cell(self, w, h, text, **kwargs):
        return self._pdf.multi_cell(w, h, _sanitize_pdf_text(str(text)), **kwargs)


def export_pdf(report: dict[str, Any]) -> bytes:
    """Export report as PDF using fpdf2."""
    pdf = _SafePDF()

    # Title page
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(0, 12, 'SHADOWGRAPH Investigation Report', new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(5)
    pdf.set_font('Helvetica', '', 12)
    inv = report['investigation']
    pdf.cell(0, 8, f"Investigation: {inv['title']} ({inv['code']})", new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.cell(0, 8, f"Status: {inv['status']}  |  Lead: {inv['lead_analyst']}", new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.cell(0, 8, f"Generated: {report['generated_at'][:19]}", new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(5)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.multi_cell(0, 5, report['disclaimer'], new_x='LMARGIN')

    # Summary
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Summary', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(0, 6, report['summary'], new_x='LMARGIN')

    # Targets
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Targets', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    for t in report['targets']:
        pdf.multi_cell(0, 6, f"- {t['code']} ({t['display_name']}): {t['risk_level']} risk, {t['category']}", new_x='LMARGIN')
        if t.get('summary'):
            pdf.set_font('Helvetica', 'I', 9)
            pdf.multi_cell(0, 5, t['summary'][:200], new_x='LMARGIN')
            pdf.set_font('Helvetica', '', 10)

    # Relationships
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Relationships', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    for r in report['relationships']:
        pdf.multi_cell(0, 6, f"- {r['code']}: {r['from_actor']} <-> {r['to_actor']} (RCS={r['confidence']}, band={r['band']}, status={r['status']})", new_x='LMARGIN')
        if r.get('hypothesis_label'):
            pdf.set_font('Helvetica', 'I', 9)
            pdf.multi_cell(0, 5, f"Hypothesis: {r['hypothesis_label']}", new_x='LMARGIN')
            pdf.set_font('Helvetica', '', 10)
        if r.get('explanation'):
            pdf.set_font('Helvetica', '', 9)
            pdf.multi_cell(0, 5, r['explanation'][:300], new_x='LMARGIN')
            pdf.set_font('Helvetica', '', 10)

    # Evidence
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Evidence', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    for e in report['evidence']:
        pdf.multi_cell(0, 6, f"- [{e['evidence_class']}] {e['title']}: +{e['score_contribution']} ({e['strength']})", new_x='LMARGIN')
        pdf.set_font('Helvetica', '', 9)
        pdf.multi_cell(0, 5, e['description'], new_x='LMARGIN')
        pdf.set_font('Helvetica', '', 10)

    # Timeline
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Timeline', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    for t in report['timeline']:
        date_str = t['occurred_at'][:10]
        pdf.multi_cell(0, 6, f"- {date_str} [{t['actor']}] {t['kind']}: {t['title']}", new_x='LMARGIN')
        if t.get('detail'):
            pdf.set_font('Helvetica', '', 9)
            pdf.multi_cell(0, 5, t['detail'], new_x='LMARGIN')
            pdf.set_font('Helvetica', '', 10)

    # Confidence
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Confidence Scores', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    for c in report['confidence']:
        pdf.multi_cell(0, 6, f"- {c['from_actor']} <-> {c['to_actor']}: RCS={c['confidence']}, band={c['band']}, status={c['status']}", new_x='LMARGIN')

    # Analyst Decisions
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Analyst Decisions', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    for d in report['analyst_decision']:
        pdf.multi_cell(0, 6, f"- {d['from_actor']} <-> {d['to_actor']}: {d['decision']} by {d.get('reviewed_by', 'unknown')}", new_x='LMARGIN')
        if d.get('review_note'):
            pdf.set_font('Helvetica', '', 9)
            pdf.multi_cell(0, 5, d['review_note'], new_x='LMARGIN')
            pdf.set_font('Helvetica', '', 10)

    # Analyst Notes
    if report['analyst_notes']:
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, 'Analyst Notes', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 10)
        for n in report['analyst_notes']:
            pdf.multi_cell(0, 6, f"- [{n['analyst']}] {n['occurred_at'][:19]}", new_x='LMARGIN')
            pdf.set_font('Helvetica', '', 9)
            pdf.multi_cell(0, 5, n['note'], new_x='LMARGIN')
            pdf.set_font('Helvetica', '', 10)

    # Sources
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Sources', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    for s in report['sources']:
        pdf.multi_cell(0, 6, f"- {s['name']} ({s['kind']}): reliability={s['reliability']}", new_x='LMARGIN')

    # Audit trail
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Audit Trail', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    for a in report['audit']:
        pdf.multi_cell(0, 6, f"- [{a['analyst']}] {a['action']} @ {a['occurred_at'][:19]}", new_x='LMARGIN')
        if a.get('note'):
            pdf.set_font('Helvetica', '', 9)
            pdf.multi_cell(0, 5, a['note'], new_x='LMARGIN')
            pdf.set_font('Helvetica', '', 10)

    # Footer disclaimer
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, 'Disclaimer', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(0, 6, report['disclaimer'], new_x='LMARGIN')

    return bytes(pdf._pdf.output())
