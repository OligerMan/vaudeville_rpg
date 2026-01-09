"""Common bot handlers - /start, /help commands."""

import html
import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.filters.chat_member_updated import (
    JOIN_TRANSITION,
    ChatMemberUpdatedFilter,
)
from aiogram.types import ChatMemberUpdated, Message
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ...db.engine import async_session_factory
from ...db.models.effects import Action, Condition, Effect
from ...db.models.enums import ActionType, AttributeCategory, ConditionType, EffectCategory
from ...db.models.items import Item
from ...db.models.players import Player
from ...db.models.settings import AttributeDefinition, Setting
from ...services.players import PlayerService
from ..utils import format_item_mechanics, log_command, safe_handler, validate_message_user

logger = logging.getLogger(__name__)

router = Router(name="common")


async def is_setting_configured(chat_id: int) -> tuple[bool, Setting | None]:
    """Check if the setting for this chat has been properly configured.

    A setting is considered configured if it has items generated.

    Returns:
        Tuple of (is_configured, setting)
    """
    async with async_session_factory() as session:
        # Get setting for this chat
        stmt = select(Setting).where(Setting.telegram_chat_id == chat_id)
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()

        if not setting:
            return False, None

        # Check if setting has any items
        items_stmt = select(Item).where(Item.setting_id == setting.id).limit(1)
        items_result = await session.execute(items_stmt)
        has_items = items_result.scalar_one_or_none() is not None

        return has_items, setting


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_bot_added_to_chat(event: ChatMemberUpdated, bot: Bot) -> None:
    """Handle when bot is added to a chat.

    Sends a welcome message explaining the game and setup process.
    """
    chat_id = event.chat.id
    logger.info(f"Bot added to chat {chat_id}")

    # Check if user who added bot is an admin
    try:
        member = await bot.get_chat_member(chat_id, event.from_user.id)
        is_admin = member.status in ("creator", "administrator")
    except Exception:
        is_admin = False

    # Check if setting already exists and is configured
    is_configured, setting = await is_setting_configured(chat_id)

    if is_configured:
        # Setting already exists, welcome back
        setting_desc = html.escape(setting.description) if setting.description else "A unique game world"
        await bot.send_message(
            chat_id,
            f"<b>VaudevilleRPG is back!</b>\n\n"
            f"<b>Setting:</b> {html.escape(setting.name)}\n"
            f"<i>{setting_desc}</i>\n\n"
            "Use /help to see available commands.",
        )
    elif is_admin:
        # Admin added the bot, prompt to generate setting
        await bot.send_message(
            chat_id,
            "<b>Thanks for adding VaudevilleRPG!</b>\n\n"
            "I'm a turn-based duel game where players battle using items and abilities.\n\n"
            "<b>Setup Required</b>\n"
            "To start playing, you need to generate a game world.\n"
            "As an admin, run this command:\n\n"
            "<code>/generate_setting &lt;description&gt;</code>\n\n"
            "<i>Example themes:</i>\n"
            " Medieval fantasy kingdom\n"
            " Cyberpunk dystopia\n"
            " Pirate adventure on the high seas\n"
            " Post-apocalyptic wasteland\n\n"
            "Once generated, everyone can duel each other and explore dungeons!",
        )
    else:
        # Non-admin added the bot
        await bot.send_message(
            chat_id,
            "<b>Thanks for adding VaudevilleRPG!</b>\n\n"
            "I'm a turn-based duel game where players battle using items and abilities.\n\n"
            "<b>Setup Required</b>\n"
            "An admin needs to generate a game world first.\n"
            "Ask an admin to run:\n"
            "<code>/generate_setting &lt;description&gt;</code>\n\n"
            "Use /help for more information!",
        )


@router.message(Command("start"))
@safe_handler
@log_command("/start")
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    is_configured, setting = await is_setting_configured(message.chat.id)

    if not is_configured:
        # Game not set up for this chat
        await message.answer(
            "<b>Welcome to VaudevilleRPG!</b>\n\n"
            "A turn-based duel game where you battle with items and abilities.\n\n"
            "<b>Game Not Set Up</b>\n"
            "This chat doesn't have a game world yet.\n\n"
            "An admin needs to generate a setting first:\n"
            "<code>/generate_setting &lt;description&gt;</code>\n\n"
            "<i>Example: /generate_setting A dark fantasy world with undead creatures</i>\n\n"
            "Once the setting is generated, everyone can duel and explore dungeons!"
        )
    else:
        # Game is ready
        setting_desc = html.escape(setting.description) if setting.description else "A unique game world"
        await message.answer(
            f"<b>Welcome to VaudevilleRPG!</b>\n\n"
            f"<b>Setting:</b> {html.escape(setting.name)}\n"
            f"<i>{setting_desc}</i>\n\n"
            "<b>Quick Start:</b>\n"
            " Reply to someone's message and use /challenge to duel them\n"
            " Use /dungeon to fight enemies and earn items\n"
            " Use /profile to see your stats and items\n\n"
            "Use /help for detailed commands and tips!"
        )


@router.message(Command("help"))
@safe_handler
@log_command("/help")
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    is_configured, _ = await is_setting_configured(message.chat.id)

    # Base help message
    help_text = (
        "<b>VaudevilleRPG Help</b>\n\n"
        "<b>Getting Started</b>\n"
        "/start - Welcome message and game status\n"
        "/help - Show this help message\n"
        "/profile - View your stats and equipped items\n"
        "/setting - View game world info and attributes\n\n"
    )

    if not is_configured:
        # Show admin setup info
        help_text += (
            "<b>Admin Setup (Required First!)</b>\n"
            "<code>/generate_setting &lt;description&gt;</code>\n"
            "Creates a unique game world with items and abilities.\n"
            "<i>Example: /generate_setting Steampunk Victorian London</i>\n\n"
        )

    # Dueling section
    help_text += (
        "<b>Dueling (PvP)</b>\n"
        "/challenge - Challenge another player\n"
        "<i>How to use: Reply to someone's message, then type /challenge</i>\n"
        "Both players pick actions (Attack/Defense/Misc/Skip).\n"
        "Winner gains rating, loser loses rating.\n\n"
    )

    # Dungeon section
    help_text += (
        "<b>Dungeons (PvE)</b>\n"
        "/dungeon - Start a dungeon run\n"
        "Fight through stages of enemies solo.\n"
        "Difficulties: Easy (2 stages), Normal (3), Hard (4), Nightmare (5)\n"
        "Defeat all enemies to earn new items!\n\n"
    )

    # Competition section
    help_text += "<b>Competition</b>\n/leaderboard - See top 10 players by rating\nWin duels to climb the ranks!\n"

    await message.answer(help_text)


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

        # Load equipped items with effects for mechanics display
        attack_item = None
        defense_item = None
        misc_item = None

        if player.attack_item_id:
            stmt = (
                select(Item)
                .where(Item.id == player.attack_item_id)
                .options(selectinload(Item.effects).selectinload(Effect.action))
            )
            result = await session.execute(stmt)
            attack_item = result.scalar_one_or_none()

        if player.defense_item_id:
            stmt = (
                select(Item)
                .where(Item.id == player.defense_item_id)
                .options(selectinload(Item.effects).selectinload(Effect.action))
            )
            result = await session.execute(stmt)
            defense_item = result.scalar_one_or_none()

        if player.misc_item_id:
            stmt = (
                select(Item)
                .where(Item.id == player.misc_item_id)
                .options(selectinload(Item.effects).selectinload(Effect.action))
            )
            result = await session.execute(stmt)
            misc_item = result.scalar_one_or_none()

        # Format profile (escape HTML in user/LLM-generated content)
        lines = [
            f"<b>{html.escape(player.display_name)}</b>",
            "",
            f"Rating: <b>{player.rating}</b> (#{rank})",
            f"HP: {player.max_hp}",
            f"SP: {player.max_special_points}",
            "",
            "<b>Equipped Items:</b>",
        ]

        # Format each item with mechanics
        if attack_item:
            mechanics = format_item_mechanics(attack_item)
            lines.append(f"  Attack: {html.escape(attack_item.name)}")
            lines.append(f"    <i>{html.escape(mechanics)}</i>")
        else:
            lines.append("  Attack: None")

        if defense_item:
            mechanics = format_item_mechanics(defense_item)
            lines.append(f"  Defense: {html.escape(defense_item.name)}")
            lines.append(f"    <i>{html.escape(mechanics)}</i>")
        else:
            lines.append("  Defense: None")

        if misc_item:
            mechanics = format_item_mechanics(misc_item)
            lines.append(f"  Misc: {html.escape(misc_item.name)}")
            lines.append(f"    <i>{html.escape(mechanics)}</i>")
        else:
            lines.append("  Misc: None")

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

            lines.append(f"{i}.{medal} <b>{html.escape(player.display_name)}</b> - {player.rating}")

        await message.answer("\n".join(lines))


def _format_phase(phase: str) -> str:
    """Format phase name for display."""
    phase_names = {
        "pre_move": "before turn",
        "post_move": "after turn",
        "pre_attack": "before attack",
        "post_attack": "after attack",
        "pre_damage": "before damage",
        "post_damage": "after damage",
    }
    return phase_names.get(phase, phase)


def _format_action(action: Action, target: str) -> str:
    """Format action for display."""
    value = action.action_data.get("value", 0)
    attribute = action.action_data.get("attribute", "")
    per_stack = action.action_data.get("per_stack", False)

    target_str = "self" if target == "self" else "enemy"
    per_stack_str = " per stack" if per_stack else ""

    if action.action_type == ActionType.DAMAGE:
        return f"deals {value}{per_stack_str} damage to {target_str}"
    elif action.action_type == ActionType.HEAL:
        return f"heals {value}{per_stack_str} HP"
    elif action.action_type == ActionType.ADD_STACKS:
        return f"adds {value} {attribute} to {target_str}"
    elif action.action_type == ActionType.REMOVE_STACKS:
        return f"removes {value} {attribute}"
    elif action.action_type == ActionType.REDUCE_INCOMING_DAMAGE:
        return f"reduces damage by {value}{per_stack_str}"
    else:
        return f"{action.action_type.value}: {value}"


async def _get_attribute_mechanics(
    session, setting_id: int, conditions_cache: dict
) -> dict[str, list[str]]:
    """Get world rule mechanics grouped by attribute."""
    # Load world rules with their actions
    stmt = (
        select(Effect)
        .where(
            Effect.setting_id == setting_id,
            Effect.category == EffectCategory.WORLD_RULE,
        )
        .options(selectinload(Effect.action))
    )
    result = await session.execute(stmt)
    world_rules = result.scalars().all()

    # Group mechanics by attribute
    attr_mechanics: dict[str, list[str]] = {}

    for rule in world_rules:
        # Get condition to find which attribute this rule is for
        if rule.condition_id not in conditions_cache:
            cond_stmt = select(Condition).where(Condition.id == rule.condition_id)
            cond_result = await session.execute(cond_stmt)
            conditions_cache[rule.condition_id] = cond_result.scalar_one_or_none()

        condition = conditions_cache[rule.condition_id]
        if not condition:
            continue

        # Find the attribute and phase from condition
        attribute_name = None
        phase = None

        if condition.condition_type == ConditionType.AND:
            # Composite condition - look up sub-conditions
            sub_ids = condition.condition_data.get("condition_ids", [])
            for sub_id in sub_ids:
                if sub_id not in conditions_cache:
                    sub_stmt = select(Condition).where(Condition.id == sub_id)
                    sub_result = await session.execute(sub_stmt)
                    conditions_cache[sub_id] = sub_result.scalar_one_or_none()

                sub_cond = conditions_cache[sub_id]
                if not sub_cond:
                    continue

                if sub_cond.condition_type == ConditionType.HAS_STACKS:
                    attribute_name = sub_cond.condition_data.get("attribute")
                elif sub_cond.condition_type == ConditionType.PHASE:
                    phase = sub_cond.condition_data.get("phase")

        if not attribute_name or not phase:
            continue

        # Format the mechanic
        action_str = _format_action(rule.action, rule.target.value)
        phase_str = _format_phase(phase)
        mechanic = f"{action_str} {phase_str}"

        if attribute_name not in attr_mechanics:
            attr_mechanics[attribute_name] = []
        attr_mechanics[attribute_name].append(mechanic)

    return attr_mechanics


@router.message(Command("setting"))
@safe_handler
@log_command("/setting")
async def cmd_setting(message: Message) -> None:
    """Handle /setting command - show current game world info."""
    async with async_session_factory() as session:
        # Check if setting is configured
        is_configured, setting = await is_setting_configured(message.chat.id)

        if not is_configured or not setting:
            await message.answer(
                "<b>Game Not Set Up</b>\n\n"
                "This chat doesn't have a game world yet.\n"
                "An admin needs to run:\n"
                "<code>/generate_setting &lt;description&gt;</code>\n\n"
                "Example: <code>/generate_setting A world of knights and dragons</code>"
            )
            return

        # Load attributes for this setting
        stmt = (
            select(AttributeDefinition)
            .where(AttributeDefinition.setting_id == setting.id)
            .order_by(AttributeDefinition.category, AttributeDefinition.name)
        )
        result = await session.execute(stmt)
        attributes = result.scalars().all()

        # Get world rule mechanics grouped by attribute
        conditions_cache: dict[int, Condition | None] = {}
        attr_mechanics = await _get_attribute_mechanics(session, setting.id, conditions_cache)

        # Format setting info (escape HTML in user/LLM-generated content)
        lines = [
            f"<b>{html.escape(setting.name)}</b>",
            "",
        ]

        if setting.description:
            # Truncate description if too long
            desc = setting.description
            if len(desc) > 300:
                desc = desc[:297] + "..."
            lines.append(f"<i>{html.escape(desc)}</i>")
            lines.append("")

        # Special points info
        lines.append(f"<b>Special Points:</b> {html.escape(setting.special_points_name)}")
        lines.append(f"  Regenerates {setting.special_points_regen} per turn")
        lines.append("")

        # Generatable attributes with mechanics
        gen_attrs = [a for a in attributes if a.category == AttributeCategory.GENERATABLE]
        if gen_attrs:
            lines.append("<b>Attributes:</b>")
            for attr in gen_attrs:
                max_info = f" (max: {attr.max_stacks})" if attr.max_stacks else ""
                lines.append(f"  <b>{html.escape(attr.display_name)}</b>{max_info}")

                # Show mechanics from world rules
                mechanics = attr_mechanics.get(attr.name, [])
                if mechanics:
                    lines.append(f"    {html.escape('; '.join(mechanics))}")

        await message.answer("\n".join(lines))
