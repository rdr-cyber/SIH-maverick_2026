"""HTTP layer. Routers stay thin: validate, delegate to a service, map errors."""
from .v1 import api_router

__all__ = ["api_router"]
