"""Celery application and registered tasks.

Defines the Celery app and application-specific tasks that can run
either locally (LocalTaskRunner) or distributed (CeleryTaskRunner).

IMPORTANT: Tasks must accept only serialization-safe arguments (strings,
ints, dicts, lists). Never pass SQLAlchemy sessions, model objects, or
non-serializable Python objects.
"""
from __future__ import annotations

import logging
from typing import Any

from celery import Celery

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Celery app configuration
# ---------------------------------------------------------------------------

# Import settings to get Redis URL (only needed in production mode)
try:
    from app.core.config import settings
    broker_url = settings.redis_url or "redis://localhost:6379/0"
except Exception:
    broker_url = "redis://localhost:6379/0"

celery_app = Celery(
    "trilok_trace",
    broker=broker_url,
    backend=broker_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,
    task_time_limit=600,
    task_default_queue="default",
    task_routes={
        "app.workers.tasks.*": {"queue": "default"},
    },
)

# Auto-discover tasks in this package
celery_app.autodiscover_tasks(["app.workers"])


# ---------------------------------------------------------------------------
# Application tasks
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="app.workers.tasks.scan_source", max_retries=3)
def scan_source(self, source_id: str, source_name: str) -> dict[str, Any]:
    """Scan a data source for new artifacts.

    Args:
        source_id: UUID of the source to scan
        source_name: Human-readable source name

    Returns:
        Dict with scan results (counts of new artifacts found)
    """
    log.info("Scanning source: %s (%s)", source_name, source_id)
    try:
        from app.core.database import SessionLocal
        from app.services.monitoring import MonitoringService

        session = SessionLocal()
        try:
            service = MonitoringService(session)
            # In production, this would trigger actual source scanning
            # For now, return the current state
            overview = service.get_overview()
            result = {
                "source_id": source_id,
                "source_name": source_name,
                "status": "completed",
                "entities": overview.get("entities", {}),
            }
            session.commit()
            return result
        finally:
            session.close()
    except Exception as exc:
        log.exception("Source scan failed: %s", source_name)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, name="app.workers.tasks.compute_correlations", max_retries=2)
def compute_correlations(self, actor_a_code: str, actor_b_code: str) -> dict[str, Any]:
    """Compute correlation signals between two actors.

    Args:
        actor_a_code: First actor code
        actor_b_code: Second actor code

    Returns:
        Dict with correlation result
    """
    log.info("Computing correlation: %s <-> %s", actor_a_code, actor_b_code)
    try:
        from app.core.database import SessionLocal
        from app.services.correlation import CorrelationEngine

        session = SessionLocal()
        try:
            engine = CorrelationEngine(session)
            result = engine.correlate(actor_a_code, actor_b_code)
            return {
                "actor_a": result.actor_a,
                "actor_b": result.actor_b,
                "total_score": result.total_score,
                "band": result.band,
                "signal_count": len(result.signals),
                "status": "completed",
            }
        finally:
            session.close()
    except Exception as exc:
        log.exception("Correlation computation failed")
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(bind=True, name="app.workers.tasks.generate_report", max_retries=2)
def generate_report(self, investigation_code: str, export_format: str = "json") -> dict[str, Any]:
    """Generate an investigation report.

    Args:
        investigation_code: Investigation code (e.g., "INV-001")
        export_format: Output format (json, csv, pdf)

    Returns:
        Dict with report metadata
    """
    log.info("Generating report: %s (format=%s)", investigation_code, export_format)
    try:
        from app.core.database import SessionLocal
        from app.services.reporting import ReportService

        session = SessionLocal()
        try:
            service = ReportService(session)
            report = service.generate_report(investigation_code)
            return {
                "investigation_code": investigation_code,
                "format": export_format,
                "sections": len(report),
                "status": "completed",
            }
        finally:
            session.close()
    except Exception as exc:
        log.exception("Report generation failed: %s", investigation_code)
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(bind=True, name="app.workers.tasks.refresh_graph", max_retries=2)
def refresh_graph(self) -> dict[str, Any]:
    """Refresh the graph from relational data.

    Rebuilds the graph (Neo4j or in-process) from the current
    state of the relational database.
    """
    log.info("Refreshing graph from relational data")
    try:
        from app.core.database import SessionLocal
        from app.repositories.graph import GraphRepository

        session = SessionLocal()
        try:
            repo = GraphRepository(session)
            counts = repo.rebuild_graph()
            return {
                "status": "completed",
                "counts": counts,
            }
        finally:
            session.close()
    except Exception as exc:
        log.exception("Graph refresh failed")
        raise self.retry(exc=exc, countdown=60)
