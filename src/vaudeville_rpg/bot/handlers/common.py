"""Common bot handlers - /start, /help commands."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select

from ...db.engine import async_session_factory
from ...db.models.players import Player
from ...services.players import PlayerService
from ..utils import log_command, safe_handler, validate_message_user

router = Router(name="common")


@router.message(Command("start"))
@safe_handler
@log_command("/start")
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    await message.answer(
        "<b>Welcome to VaudevilleRPG!</b>\n\n"
        "A turn-based duel game where you battle with items and abilities.\n\n"
        "Use /help to see available commands."
    )


@router.message(Command("help"))
@safe_handler
@log_command("/help")
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    await message.answer(
        "<b>Available Commands:</b>\n\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/profile - Show your player stats\n"
        "/leaderboard - Show top players\n"
        "/challenge - Reply to a user to challenge them\n"
        "/dungeon - Start a PvE dungeon run\n"
    )


@router.message(Command("profile"))
@safe_handler
@log_command("/profile")
async def cmd_profile(message: Message) -> None:
    """Handle /profile command - show player stats."""
    if not validate_message_user(message):
        await message.answer("Could not identify user. Please try again.")
        return

    async with async_session_factory() as session:
        player_service = PlayerService(session)

        setting = await player_service.get_or_create_setting(message.chat.id)
        player = await player_service.get_or_create_player(
            telegram_user_id=message.from_user.id,
            setting_id=setting.id,
            display_name=message.from_user.full_name,
        )

        # Get player's rank
        rank_stmt = (
            select(func.count())
            .select_from(Player)
            .where(
                Player.setting_id == setting.id,
                Player.is_bot == False,  # noqa: E712
                Player.rating > player.rating,
            )
        )
        result = await session.execute(rank_stmt)
        rank = result.scalar() + 1

        # Format profile
        lines = [
            f"<b>{player.display_name}</b>",
            "",
            f"Rating: <b>{player.rating}</b> (#{rank})",
            f"HP: {player.max_hp}",
            f"SP: {player.max_special_points}",
            "",
            "<b>Equipped Items:</b>",
            f"  Attack: {player.attack_item.name if player.attack_item else 'None'}",
            f"  Defense: {player.defense_item.name if player.defense_item else 'None'}",
            f"  Misc: {player.misc_item.name if player.misc_item else 'None'}",
        ]

        await message.answer("\n".join(lines))


@router.message(Command("leaderboard"))
@safe_handler
@log_command("/leaderboard")
async def cmd_leaderboard(message: Message) -> None:
    """Handle /leaderboard command - show top players."""
    async with async_session_factory() as session:
        player_service = PlayerService(session)

        setting = await player_service.get_or_create_setting(message.chat.id)

        # Get top 10 players by rating
        stmt = (
            select(Player)
            .where(
                Player.setting_id == setting.id,
                Player.is_bot == False,  # noqa: E712
            )
            .order_by(Player.rating.desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        players = result.scalars().all()

        if not players:
            await message.answer("No players yet! Be the first to duel.")
            return

        lines = ["<b>Leaderboard</b>", ""]
        for i, player in enumerate(players, 1):
            medal = ""
            if i == 1:
                medal = " "
            elif i == 2:
                medal = " "
            elif i == 3:
                medal = " "

            lines.append(f"{i}.{medal} <b>{player.display_name}</b> - {player.rating}")

        await message.answer("\n".join(lines))
