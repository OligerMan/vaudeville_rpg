"""Common bot handlers - /start, /help commands."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="common")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    await message.answer(
        "<b>Welcome to VaudevilleRPG!</b>\n\n"
        "A turn-based duel game where you battle with items and abilities.\n\n"
        "Use /help to see available commands."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    await message.answer(
        "<b>Available Commands:</b>\n\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n\n"
        "<i>More commands coming soon...</i>"
    )
