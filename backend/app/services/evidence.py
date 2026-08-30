"""Evidence and relationship business logic.

Services own domain rules and DTO mapping. The evidence service answers
the product's core question: WHY ARE THESE TWO PERSONAS CONNECTED?

Every response carries:
- The relationship with confidence, band, and status
- Evidence items with their class (OBSERVED_FACT, DERIVED_SIGNAL, etc.)
- Score contributions showing exactly how the RCS was computed
- Human-readable explanations
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.repositories.evidence import EvidenceRepository
from app.schemas.evidence import (
    EvidenceOut,
    RelationshipDetail,
    RelationshipOut,
    ScoringFactor,
)


class RelationshipNotFound(LookupError):
    """Raised when a relationship code does not resolve."""

    def __init__(self, code: str) -> None:
        super().__init__(f"No relationship matching '{code}'")
        self.code = code


def _to_relationship_out(rel: Any, from_name: str, to_name: str) -> RelationshipOut:
    return RelationshipOut(
        id=rel.id,
        code=rel.code,
        kind=rel.kind,
        from_type=rel.from_type,
        from_id=rel.from_id,
        to_type=rel.to_type,
        to_id=rel.to_id,
        confidence=rel.confidence,
        band=rel.band,
        status=rel.status,
        explanation=rel.explanation,
        hypothesis_label=rel.hypothesis_label,
        reviewed_by=rel.reviewed_by,
        reviewed_at=rel.reviewed_at,
        review_note=rel.review_note,
        engine_ref=rel.engine_ref,
        first_seen=rel.first_seen,
        last_seen=rel.last_seen,
        from_name=from_name,
        to_name=to_name,
        scoring_factors=[
            ScoringFactor(**f) for f in (rel.scoring_factors or [])
        ],
    )


def _to_evidence_out(ev: Any) -> EvidenceOut:
    return EvidenceOut(
        id=ev.id,
        code=ev.code,
        kind=ev.kind,
        title=ev.title,
        description=ev.description,
        strength=ev.strength,
        evidence_class=ev.evidence_class,
        score_contribution=ev.score_contribution,
        details=ev.details or {},
        status=ev.status,
    )


class EvidenceService:
    """Business logic for relationships and evidence."""

    def __init__(self, session: Session) -> None:
        self.repo = EvidenceRepository(session)

    def list_relationships(
        self,
        *,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        min_confidence: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RelationshipOut]:
        rows, _total = self.repo.list_relationships(
            kind=kind,
            status=status,
            min_confidence=min_confidence,
            limit=limit,
            offset=offset,
        )
        return [_to_relationship_out(r["relationship"], r["from_name"], r["to_name"]) for r in rows]

    def get_relationship_detail(self, code: str) -> RelationshipDetail:
        """Get a relationship with its full evidence chain — the WHY panel."""
        result = self.repo.get_relationship_with_evidence(code)
        if result is None:
            raise RelationshipNotFound(code)

        rel = result["relationship"]
        evidence = [_to_evidence_out(e) for e in result["evidence"]]

        # Compute total score from evidence
        total_from_evidence = sum(e.score_contribution for e in evidence)

        return RelationshipDetail(
            id=rel.id,
            code=rel.code,
            kind=rel.kind,
            from_type=rel.from_type,
            from_id=rel.from_id,
            to_type=rel.to_type,
            to_id=rel.to_id,
            confidence=rel.confidence,
            band=rel.band,
            status=rel.status,
            explanation=rel.explanation,
            hypothesis_label=rel.hypothesis_label,
            reviewed_by=rel.reviewed_by,
            reviewed_at=rel.reviewed_at,
            review_note=rel.review_note,
            engine_ref=rel.engine_ref,
            first_seen=rel.first_seen,
            last_seen=rel.last_seen,
            from_name=result["from_name"],
            to_name=result["to_name"],
            scoring_factors=[
                ScoringFactor(**f) for f in (rel.scoring_factors or [])
            ],
            evidence=evidence,
            total_evidence_score=total_from_evidence,
        )

    def list_evidence(
        self,
        *,
        relationship_id: Optional[str] = None,
        kind: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EvidenceOut]:
        items = self.repo.list_all_evidence(
            relationship_id=relationship_id,
            kind=kind,
            limit=limit,
            offset=offset,
        )
        return [_to_evidence_out(e) for e in items]
