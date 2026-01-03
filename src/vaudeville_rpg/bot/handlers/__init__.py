"""Bot handlers module."""

from .common import router as common_router
from .duels import router as duels_router

__all__ = ["common_router", "duels_router"]
