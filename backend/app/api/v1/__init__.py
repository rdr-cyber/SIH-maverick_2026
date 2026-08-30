"""v1 API router."""
from fastapi import APIRouter

from . import actors, confidence, correlation, evidence, graph, health, infrastructure, investigations, monitoring, reports, timeline

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(actors.router)
api_router.include_router(evidence.router)
api_router.include_router(graph.router)
api_router.include_router(infrastructure.router)
api_router.include_router(timeline.router)
api_router.include_router(correlation.router)
api_router.include_router(confidence.router)
api_router.include_router(investigations.router)
api_router.include_router(monitoring.router)
api_router.include_router(reports.router)

__all__ = ["api_router"]
