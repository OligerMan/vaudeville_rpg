"""Bot handlers module."""

from .common import router as common_router
from .duels import router as duels_router
from .dungeons import router as dungeons_router

__all__ = ["common_router", "duels_router", "dungeons_router"]
