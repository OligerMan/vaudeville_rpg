"""Entry point for running the VaudevilleRPG bot."""

import asyncio
import logging
import sys

from vaudeville_rpg.bot.app import create_bot, create_dispatcher
from vaudeville_rpg.config import get_settings


async def main() -> None:
    """Start the bot."""
    settings = get_settings()

    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    bot = create_bot()
    dp = create_dispatcher()

    logging.info("Starting VaudevilleRPG bot...")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
