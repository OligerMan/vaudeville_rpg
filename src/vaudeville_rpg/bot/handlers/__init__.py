"""Bot handlers module."""

from .admin import router as admin_router
from .common import router as common_router
from .duels import router as duels_router
from .dungeons import router as dungeons_router

__all__ = ["admin_router", "common_router", "duels_router", "dungeons_router"]
