"""Dungeon handlers - /dungeon command and dungeon interactions."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ...db.engine import async_session_factory
from ...db.models.effects import Effect
from ...db.models.enums import ActionType, DuelActionType, DungeonDifficulty, ItemSlot, TargetType
from ...db.models.items import Item
from ...services.dungeons import DungeonService
from ...services.players import PlayerService
from ..utils import (
    log_callback,
    log_command,
    safe_handler,
    validate_callback_message,
    validate_message_user,
)
from .common import is_setting_configured
from .duels import format_turn_result

router = Router(name="dungeons")


# Callback data prefixes
DUNGEON_START = "dungeon_start:"
DUNGEON_ACTION = "dungeon_action:"
DUNGEON_ABANDON = "dungeon_abandon:"
REWARD_EQUIP = "reward_equip:"
REWARD_REJECT = "reward_reject:"

# Rarity display names
RARITY_NAMES = {1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic", 5: "Legendary"}


def format_item_mechanics(item: Item) -> str:
    """Format item mechanics description from its effects.

    Returns a human-readable description of what the item does mechanically.
    Consolidates similar effects (e.g., multiple damage effects are summed).
    """
    if not item.effects:
        return "No special effects"

    # Aggregate effects by type and target
    # Key: (action_type, target, attribute) -> total value
    aggregated: dict[tuple, int] = {}

    for effect in item.effects:
        action = effect.action
        action_data = action.action_data
        target = effect.target

        value = action_data.get("value", 0)
        attribute = action_data.get("attribute", "")

        # Create a key for aggregation
        # For damage/attack, treat them the same
        if action.action_type in (ActionType.ATTACK, ActionType.DAMAGE):
            key = ("damage", target, "")
        else:
            key = (action.action_type.value, target, attribute)

        # Sum values for same effect type
        if key in aggregated:
            aggregated[key] += value
        else:
            aggregated[key] = value

    # Format aggregated effects
    descriptions = []
    for (action_type, target, attribute), value in aggregated.items():
        target_text = "self" if target == TargetType.SELF else "enemy"

        if action_type == "damage":
            descriptions.append(f"Deals {value} damage to {target_text}")
        elif action_type == ActionType.HEAL.value:
            descriptions.append(f"Heals {value} HP")
        elif action_type == ActionType.ADD_STACKS.value:
            attr_display = attribute.replace("_", " ").title()
            descriptions.append(f"Adds {value} {attr_display} to {target_text}")
        elif action_type == ActionType.REMOVE_STACKS.value:
            attr_display = attribute.replace("_", " ").title()
            descriptions.append(f"Removes {value} {attr_display} from {target_text}")
        elif action_type == ActionType.REDUCE_INCOMING_DAMAGE.value:
            descriptions.append(f"Reduces incoming damage by {value}")
        elif action_type == ActionType.SPEND.value:
            attr_display = attribute.replace("_", " ").upper() if attribute else "SP"
            descriptions.append(f"Costs {value} {attr_display}")
        elif action_type == ActionType.MODIFY_CURRENT_MAX.value:
            attr_display = attribute.replace("_", " ").upper() if attribute else "stat"
            if value > 0:
                descriptions.append(f"+{value} max {attr_display}")
            else:
                descriptions.append(f"{value} max {attr_display}")
        else:
            descriptions.append(f"{action_type}: {value}")

    return ", ".join(descriptions) if descriptions else "No special effects"


def get_difficulty_keyboard() -> InlineKeyboardMarkup:
    """Create difficulty selection keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Easy (2 stages)",
                    callback_data=f"{DUNGEON_START}easy",
                ),
                InlineKeyboardButton(
                    text="Normal (3 stages)",
                    callback_data=f"{DUNGEON_START}normal",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Hard (4 stages)",
                    callback_data=f"{DUNGEON_START}hard",
                ),
                InlineKeyboardButton(
                    text="Nightmare (5 stages)",
                    callback_data=f"{DUNGEON_START}nightmare",
                ),
            ],
        ]
    )


def get_dungeon_action_keyboard(duel_id: int, dungeon_id: int) -> InlineKeyboardMarkup:
    """Create action selection keyboard for dungeon combat."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Attack",
                    callback_data=f"{DUNGEON_ACTION}{dungeon_id}:{duel_id}:attack",
                ),
                InlineKeyboardButton(
                    text="Defense",
                    callback_data=f"{DUNGEON_ACTION}{dungeon_id}:{duel_id}:defense",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Misc",
                    callback_data=f"{DUNGEON_ACTION}{dungeon_id}:{duel_id}:misc",
                ),
                InlineKeyboardButton(
                    text="Skip",
                    callback_data=f"{DUNGEON_ACTION}{dungeon_id}:{duel_id}:skip",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Abandon Dungeon",
                    callback_data=f"{DUNGEON_ABANDON}{dungeon_id}",
                ),
            ],
        ]
    )


def get_reward_keyboard(reward_item_id: int, player_id: int) -> InlineKeyboardMarkup:
    """Create equip/reject keyboard for dungeon reward."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Equip",
                    callback_data=f"{REWARD_EQUIP}{reward_item_id}:{player_id}",
                ),
                InlineKeyboardButton(
                    text="Reject",
                    callback_data=f"{REWARD_REJECT}{reward_item_id}",
                ),
            ]
        ]
    )


def format_reward_comparison(reward_item: Item, current_item: Item | None, slot_name: str) -> str:
    """Format reward item comparison with current equipped item."""
    rarity = RARITY_NAMES.get(reward_item.rarity, "Unknown")

    # Get mechanics description for reward item
    reward_mechanics = format_item_mechanics(reward_item)

    lines = [
        f"<b>Reward: {reward_item.name}</b>",
        f"Rarity: {rarity}",
        f"Slot: {slot_name}",
        f"Effects: {reward_mechanics}",
        "",
    ]

    if current_item:
        current_rarity = RARITY_NAMES.get(current_item.rarity, "Unknown")
        current_mechanics = format_item_mechanics(current_item)
        lines.append(f"<b>Current {slot_name}:</b> {current_item.name} ({current_rarity})")
        lines.append(f"Effects: {current_mechanics}")
    else:
        lines.append(f"<b>Current {slot_name}:</b> None")

    return "\n".join(lines)


def format_dungeon_state(dungeon_state: dict, duel_state: dict | None = None) -> str:
    """Format dungeon state for display."""
    lines = [
        f"<b>{dungeon_state['name']}</b> ({dungeon_state['difficulty']})",
        f"Stage {dungeon_state['current_stage']}/{dungeon_state['total_stages']}",
    ]

    if dungeon_state.get("current_enemy"):
        enemy = dungeon_state["current_enemy"]
        lines.append(f"\nEnemy: <b>{enemy['name']}</b>")

    if duel_state:
        lines.append(f"\n<b>Turn {duel_state['current_turn']}</b>")

        for p in duel_state["participants"]:
            combat = p.get("combat_state")
            if combat:
                hp = combat["current_hp"]
                max_hp = combat["max_hp"]
                sp = combat["current_special_points"]
                max_sp = combat["max_special_points"]
                name = p.get("display_name", "Fighter")
                lines.append(f"  {name}: {hp}/{max_hp} HP | {sp}/{max_sp} SP")

    return "\n".join(lines)


@router.message(Command("dungeon"))
@safe_handler
@log_command("/dungeon")
async def cmd_dungeon(message: Message) -> None:
    """Handle /dungeon command - start or check dungeon status."""
    if not validate_message_user(message):
        await message.answer("Could not identify user. Please try again.")
        return

    # Check if game is set up for this chat
    is_configured, _ = await is_setting_configured(message.chat.id)
    if not is_configured:
        await message.answer(
            "<b>Game Not Set Up</b>\n\n"
            "This chat doesn't have a game world yet.\n"
            "An admin needs to run:\n"
            "<code>/generate_setting &lt;description&gt;</code>\n\n"
            "Once the setting is generated, you can explore dungeons!"
        )
        return

    async with async_session_factory() as session:
        player_service = PlayerService(session)
        dungeon_service = DungeonService(session)

        setting = await player_service.get_or_create_setting(message.chat.id)
        player = await player_service.get_or_create_player(
            telegram_user_id=message.from_user.id,
            setting_id=setting.id,
            display_name=message.from_user.full_name,
        )

        # Check if player is already in a dungeon
        active_dungeon = await dungeon_service.get_active_dungeon(player.id)

        if active_dungeon:
            # Show current dungeon state
            dungeon_state = await dungeon_service.get_dungeon_state(active_dungeon.id)

            if not dungeon_state:
                await message.answer("Error loading dungeon state.")
                return

            # Get duel state if there's an active duel
            duel_state = None
            if dungeon_state.get("current_duel_id"):
                from ...services.duels import DuelService

                duel_service = DuelService(session)
                duel_state = await duel_service.get_duel_state(dungeon_state["current_duel_id"])

            text = format_dungeon_state(dungeon_state, duel_state)

            if dungeon_state.get("current_duel_id"):
                await message.answer(
                    f"{text}\n\nChoose your action:",
                    reply_markup=get_dungeon_action_keyboard(dungeon_state["current_duel_id"], active_dungeon.id),
                )
            else:
                await message.answer(text)
        else:
            # Offer to start a new dungeon
            await message.answer(
                "Select dungeon difficulty:",
                reply_markup=get_difficulty_keyboard(),
            )


@router.callback_query(F.data.startswith(DUNGEON_START))
@safe_handler
@log_callback("start_dungeon")
async def callback_start_dungeon(callback: CallbackQuery) -> None:
    """Handle dungeon difficulty selection."""
    if not callback.data or not callback.from_user or not validate_callback_message(callback):
        await callback.answer("Invalid request.", show_alert=True)
        return

    difficulty_str = callback.data.replace(DUNGEON_START, "")
    difficulty_map = {
        "easy": DungeonDifficulty.EASY,
        "normal": DungeonDifficulty.NORMAL,
        "hard": DungeonDifficulty.HARD,
        "nightmare": DungeonDifficulty.NIGHTMARE,
    }
    difficulty = difficulty_map.get(difficulty_str)
    if not difficulty:
        await callback.answer("Invalid difficulty.", show_alert=True)
        return

    async with async_session_factory() as session:
        player_service = PlayerService(session)
        dungeon_service = DungeonService(session)

        setting = await player_service.get_or_create_setting(callback.message.chat.id)
        player = await player_service.get_or_create_player(
            telegram_user_id=callback.from_user.id,
            setting_id=setting.id,
            display_name=callback.from_user.full_name,
        )

        result = await dungeon_service.start_dungeon(player.id, setting.id, difficulty)

        if not result.success:
            await callback.answer(result.message, show_alert=True)
            return

        await session.commit()

        # Get dungeon state
        dungeon_state = await dungeon_service.get_dungeon_state(result.dungeon_id)
        if not dungeon_state:
            await callback.answer("Error loading dungeon.", show_alert=True)
            return

        # Get duel state to show HP/SP
        duel_state = None
        if result.duel_id:
            from ...services.duels import DuelService

            duel_service = DuelService(session)
            duel_state = await duel_service.get_duel_state(result.duel_id)

        text = format_dungeon_state(dungeon_state, duel_state)

        await callback.message.edit_text(
            f"{result.message}\n\n{text}\n\nChoose your action:",
            reply_markup=get_dungeon_action_keyboard(result.duel_id, result.dungeon_id),
        )
        await callback.answer()


@router.callback_query(F.data.startswith(DUNGEON_ACTION))
@safe_handler
@log_callback("dungeon_action")
async def callback_dungeon_action(callback: CallbackQuery) -> None:
    """Handle action selection in dungeon combat."""
    if not callback.data or not callback.from_user or not validate_callback_message(callback):
        await callback.answer("Invalid request.", show_alert=True)
        return

    # Parse: dungeon_action:{dungeon_id}:{duel_id}:{action}
    parts = callback.data.replace(DUNGEON_ACTION, "").split(":")
    if len(parts) != 3:
        await callback.answer("Invalid action format.", show_alert=True)
        return

    try:
        dungeon_id = int(parts[0])
        duel_id = int(parts[1])
    except ValueError:
        await callback.answer("Invalid IDs.", show_alert=True)
        return

    action_str = parts[2]

    action_map = {
        "attack": DuelActionType.ATTACK,
        "defense": DuelActionType.DEFENSE,
        "misc": DuelActionType.MISC,
        "skip": DuelActionType.SKIP,
    }
    action_type = action_map.get(action_str)
    if not action_type:
        await callback.answer("Invalid action.", show_alert=True)
        return

    async with async_session_factory() as session:
        player_service = PlayerService(session)
        dungeon_service = DungeonService(session)

        from ...services.duels import DuelService

        duel_service = DuelService(session)

        setting = await player_service.get_or_create_setting(callback.message.chat.id)
        player = await player_service.get_or_create_player(
            telegram_user_id=callback.from_user.id,
            setting_id=setting.id,
            display_name=callback.from_user.full_name,
        )

        # Submit player's action
        result = await duel_service.submit_action(duel_id, player.id, action_type)

        if not result.success:
            await callback.answer(result.message, show_alert=True)
            return

        # For PvE, we need to also submit the bot's action
        # Get the duel to find the bot participant
        turn_result = None
        duel = await duel_service.get_active_duel(duel_id)
        if duel:
            for p in duel.participants:
                if p.player.is_bot and not p.is_ready:
                    # Bot chooses attack most of the time
                    import random

                    bot_actions = [
                        DuelActionType.ATTACK,
                        DuelActionType.ATTACK,
                        DuelActionType.DEFENSE,
                        DuelActionType.MISC,
                    ]
                    bot_action = random.choice(bot_actions)
                    bot_result = await duel_service.submit_action(duel_id, p.player_id, bot_action)
                    # Capture turn result if both players submitted
                    if bot_result.turn_result:
                        turn_result = bot_result.turn_result
                    break

        await session.commit()

        # Check if turn was resolved and get result
        duel_state = await duel_service.get_duel_state(duel_id)

        # Check if duel is over
        if duel_state and duel_state.get("winner_participant_id"):
            # Duel ended - check if player won
            player_won = False
            for p in duel_state["participants"]:
                if p["participant_id"] == duel_state["winner_participant_id"] and not p.get("is_bot", True):
                    player_won = True
                    break

            # Handle dungeon progress
            dungeon_result = await dungeon_service.on_duel_completed(dungeon_id, player.id, player_won)
            await session.commit()

            if dungeon_result.dungeon_completed:
                # Check if there's a reward
                if dungeon_result.reward_item_id:
                    # Get reward item details with effects and actions loaded
                    reward_stmt = (
                        select(Item)
                        .where(Item.id == dungeon_result.reward_item_id)
                        .options(selectinload(Item.effects).selectinload(Effect.action))
                    )
                    reward_result = await session.execute(reward_stmt)
                    reward_item = reward_result.scalar_one_or_none()

                    if reward_item:
                        # Get current item in the same slot for comparison (with effects loaded)
                        current_item = None
                        current_item_id = None
                        slot_name = reward_item.slot.value.title()

                        if reward_item.slot == ItemSlot.ATTACK:
                            current_item_id = player.attack_item_id
                        elif reward_item.slot == ItemSlot.DEFENSE:
                            current_item_id = player.defense_item_id
                        elif reward_item.slot == ItemSlot.MISC:
                            current_item_id = player.misc_item_id

                        if current_item_id:
                            # Load current item with effects and actions
                            current_stmt = (
                                select(Item)
                                .where(Item.id == current_item_id)
                                .options(selectinload(Item.effects).selectinload(Effect.action))
                            )
                            current_result = await session.execute(current_stmt)
                            current_item = current_result.scalar_one_or_none()

                        comparison = format_reward_comparison(reward_item, current_item, slot_name)

                        # Build message with turn result
                        result_text = dungeon_result.message
                        if turn_result:
                            result_text += format_turn_result(turn_result)

                        await callback.message.edit_text(
                            f"{result_text}\n\n{comparison}",
                            reply_markup=get_reward_keyboard(reward_item.id, player.id),
                        )
                    else:
                        result_text = dungeon_result.message
                        if turn_result:
                            result_text += format_turn_result(turn_result)
                        await callback.message.edit_text(
                            result_text,
                            reply_markup=None,
                        )
                else:
                    result_text = dungeon_result.message
                    if turn_result:
                        result_text += format_turn_result(turn_result)
                    await callback.message.edit_text(
                        result_text,
                        reply_markup=None,
                    )
            elif dungeon_result.dungeon_failed:
                result_text = dungeon_result.message
                if turn_result:
                    result_text += format_turn_result(turn_result)
                await callback.message.edit_text(
                    result_text,
                    reply_markup=None,
                )
            elif dungeon_result.stage_completed:
                # Stage cleared, moving to next
                dungeon_state = await dungeon_service.get_dungeon_state(dungeon_id)
                if dungeon_state:
                    # Get duel state for next stage to show HP/SP
                    next_duel_state = None
                    if dungeon_result.duel_id:
                        next_duel_state = await duel_service.get_duel_state(dungeon_result.duel_id)

                    text = format_dungeon_state(dungeon_state, next_duel_state)
                    result_text = dungeon_result.message
                    if turn_result:
                        result_text += format_turn_result(turn_result)
                    await callback.message.edit_text(
                        f"{result_text}\n\n{text}\n\nChoose your action:",
                        reply_markup=get_dungeon_action_keyboard(dungeon_result.duel_id, dungeon_id),
                    )
            await callback.answer()
        else:
            # Duel continues - show updated state
            dungeon_state = await dungeon_service.get_dungeon_state(dungeon_id)
            if dungeon_state:
                text = format_dungeon_state(dungeon_state, duel_state)
                # Add turn result if available
                if turn_result:
                    text += format_turn_result(turn_result)
                await callback.message.edit_text(
                    f"{text}\n\nChoose your action:",
                    reply_markup=get_dungeon_action_keyboard(duel_id, dungeon_id),
                )
            await callback.answer("Action submitted!")


@router.callback_query(F.data.startswith(DUNGEON_ABANDON))
@safe_handler
@log_callback("abandon_dungeon")
async def callback_abandon_dungeon(callback: CallbackQuery) -> None:
    """Handle abandon dungeon button."""
    if not callback.data or not callback.from_user or not validate_callback_message(callback):
        await callback.answer("Invalid request.", show_alert=True)
        return

    try:
        dungeon_id = int(callback.data.replace(DUNGEON_ABANDON, ""))
    except ValueError:
        await callback.answer("Invalid dungeon ID.", show_alert=True)
        return

    async with async_session_factory() as session:
        player_service = PlayerService(session)
        dungeon_service = DungeonService(session)

        setting = await player_service.get_or_create_setting(callback.message.chat.id)
        player = await player_service.get_or_create_player(
            telegram_user_id=callback.from_user.id,
            setting_id=setting.id,
            display_name=callback.from_user.full_name,
        )

        result = await dungeon_service.abandon_dungeon(dungeon_id, player.id)

        if not result.success:
            await callback.answer(result.message, show_alert=True)
            return

        await session.commit()

        await callback.message.edit_text(
            result.message,
            reply_markup=None,
        )
        await callback.answer("Dungeon abandoned.")


@router.callback_query(F.data.startswith(REWARD_EQUIP))
@safe_handler
@log_callback("equip_reward")
async def callback_equip_reward(callback: CallbackQuery) -> None:
    """Handle equip reward button."""
    if not callback.data or not callback.from_user or not validate_callback_message(callback):
        await callback.answer("Invalid request.", show_alert=True)
        return

    # Parse: reward_equip:{item_id}:{player_id}
    parts = callback.data.replace(REWARD_EQUIP, "").split(":")
    if len(parts) != 2:
        await callback.answer("Invalid format.", show_alert=True)
        return

    try:
        item_id = int(parts[0])
        expected_player_id = int(parts[1])
    except ValueError:
        await callback.answer("Invalid IDs.", show_alert=True)
        return

    async with async_session_factory() as session:
        player_service = PlayerService(session)

        setting = await player_service.get_or_create_setting(callback.message.chat.id)
        player = await player_service.get_or_create_player(
            telegram_user_id=callback.from_user.id,
            setting_id=setting.id,
            display_name=callback.from_user.full_name,
        )

        # Verify this is the correct player
        if player.id != expected_player_id:
            await callback.answer("This reward is not for you!", show_alert=True)
            return

        # Get the reward item
        item_stmt = select(Item).where(Item.id == item_id)
        item_result = await session.execute(item_stmt)
        reward_item = item_result.scalar_one_or_none()

        if not reward_item:
            await callback.answer("Item not found!", show_alert=True)
            return

        # Equip the item in the appropriate slot
        if reward_item.slot == ItemSlot.ATTACK:
            player.attack_item_id = reward_item.id
        elif reward_item.slot == ItemSlot.DEFENSE:
            player.defense_item_id = reward_item.id
        elif reward_item.slot == ItemSlot.MISC:
            player.misc_item_id = reward_item.id

        await session.commit()

        await callback.message.edit_text(
            f"Equipped <b>{reward_item.name}</b>!",
            reply_markup=None,
        )
        await callback.answer("Item equipped!")


@router.callback_query(F.data.startswith(REWARD_REJECT))
@safe_handler
@log_callback("reject_reward")
async def callback_reject_reward(callback: CallbackQuery) -> None:
    """Handle reject reward button."""
    if not callback.data or not validate_callback_message(callback):
        await callback.answer("Invalid request.", show_alert=True)
        return

    await callback.message.edit_text(
        "Reward rejected. Better luck next time!",
        reply_markup=None,
    )
    await callback.answer("Reward rejected.")
