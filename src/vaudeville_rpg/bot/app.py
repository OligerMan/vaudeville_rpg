"""Bot application setup and dispatcher."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from vaudeville_rpg.config import get_settings


def create_bot() -> Bot:
    """Create and configure the Telegram bot instance."""
    settings = get_settings()
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    """Create and configure the dispatcher with routers."""
    from vaudeville_rpg.bot.handlers import common_router, duels_router, dungeons_router

    dp = Dispatcher()
    dp.include_router(common_router)
    dp.include_router(duels_router)
    dp.include_router(dungeons_router)
    return dp
