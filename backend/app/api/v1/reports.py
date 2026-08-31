"""Report API endpoints.

Generate investigation reports from real data and export in multiple formats.

Every export comes from the actual investigation record — no fabricated content.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.api.auth import get_current_user
from app.api.deps import DbSession
from app.services.reporting import ReportService, export_csv, export_json, export_pdf

router = APIRouter(
    dependencies=[Depends(get_current_user)],prefix="/reports", tags=["reports"])


@router.get("/{code}", summary="Generate investigation report")
def get_report(session: DbSession, code: str) -> dict:
    """Generate a complete investigation report from real data."""
    svc = ReportService(session)
    report = svc.generate_report(code)
    if not report:
        return {"error": "not_found", "code": code}
    return report


@router.get("/{code}/export", summary="Export report in specified format")
def export_report(
    session: DbSession,
    code: str,
    format: str = Query("json", description="Export format: json, csv, pdf"),
) -> Response:
    """Export investigation report as JSON, CSV, or PDF."""
    svc = ReportService(session)
    report = svc.generate_report(code)
    if not report:
        return Response(
            content='{"error": "not_found"}',
            media_type="application/json",
            status_code=404,
        )

    if format == "json":
        return Response(
            content=export_json(report),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{code}-report.json"'},
        )
    elif format == "csv":
        return Response(
            content=export_csv(report),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{code}-report.csv"'},
        )
    elif format == "pdf":
        pdf_bytes = export_pdf(report)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{code}-report.pdf"'},
        )
    else:
        return Response(
            content=f'{{"error": "unsupported format: {format}"}}',
            media_type="application/json",
            status_code=400,
        )
