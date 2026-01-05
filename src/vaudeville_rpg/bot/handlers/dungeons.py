"""Dungeon handlers - /dungeon command and dungeon interactions."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from ...db.engine import async_session_factory
from ...db.models.enums import DuelActionType, DungeonDifficulty, ItemSlot
from ...db.models.items import Item
from ...db.models.players import Player
from ...services.dungeons import DungeonService
from ...services.players import PlayerService

router = Router(name="dungeons")


# Callback data prefixes
DUNGEON_START = "dungeon_start:"
DUNGEON_ACTION = "dungeon_action:"
DUNGEON_ABANDON = "dungeon_abandon:"
REWARD_EQUIP = "reward_equip:"
REWARD_REJECT = "reward_reject:"

# Rarity display names
RARITY_NAMES = {1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic", 5: "Legendary"}


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


def format_reward_comparison(
    reward_item: Item, current_item: Item | None, slot_name: str
) -> str:
    """Format reward item comparison with current equipped item."""
    rarity = RARITY_NAMES.get(reward_item.rarity, "Unknown")

    lines = [
        f"<b>Reward: {reward_item.name}</b>",
        f"Rarity: {rarity}",
        f"Slot: {slot_name}",
        f"<i>{reward_item.description}</i>",
        "",
    ]

    if current_item:
        current_rarity = RARITY_NAMES.get(current_item.rarity, "Unknown")
        lines.append(f"<b>Current {slot_name}:</b> {current_item.name} ({current_rarity})")
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
                sp = combat["current_special_points"]
                name = p.get("display_name", "Fighter")
                lines.append(f"  {name}: {hp} HP | {sp} SP")

    return "\n".join(lines)


@router.message(Command("dungeon"))
async def cmd_dungeon(message: Message) -> None:
    """Handle /dungeon command - start or check dungeon status."""
    if not message.from_user:
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
async def callback_start_dungeon(callback: CallbackQuery) -> None:
    """Handle dungeon difficulty selection."""
    if not callback.data or not callback.from_user or not callback.message:
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

        text = format_dungeon_state(dungeon_state)

        await callback.message.edit_text(
            f"{result.message}\n\n{text}\n\nChoose your action:",
            reply_markup=get_dungeon_action_keyboard(result.duel_id, result.dungeon_id),
        )
        await callback.answer()


@router.callback_query(F.data.startswith(DUNGEON_ACTION))
async def callback_dungeon_action(callback: CallbackQuery) -> None:
    """Handle action selection in dungeon combat."""
    if not callback.data or not callback.from_user or not callback.message:
        return

    # Parse: dungeon_action:{dungeon_id}:{duel_id}:{action}
    parts = callback.data.replace(DUNGEON_ACTION, "").split(":")
    if len(parts) != 3:
        return

    dungeon_id = int(parts[0])
    duel_id = int(parts[1])
    action_str = parts[2]

    action_map = {
        "attack": DuelActionType.ATTACK,
        "defense": DuelActionType.DEFENSE,
        "misc": DuelActionType.MISC,
        "skip": DuelActionType.SKIP,
    }
    action_type = action_map.get(action_str)
    if not action_type:
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
                    await duel_service.submit_action(duel_id, p.player_id, bot_action)
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
                    # Get reward item details
                    reward_stmt = select(Item).where(Item.id == dungeon_result.reward_item_id)
                    reward_result = await session.execute(reward_stmt)
                    reward_item = reward_result.scalar_one_or_none()

                    if reward_item:
                        # Get current item in the same slot for comparison
                        current_item = None
                        slot_name = reward_item.slot.value.title()

                        if reward_item.slot == ItemSlot.ATTACK:
                            current_item = player.attack_item
                        elif reward_item.slot == ItemSlot.DEFENSE:
                            current_item = player.defense_item
                        elif reward_item.slot == ItemSlot.MISC:
                            current_item = player.misc_item

                        comparison = format_reward_comparison(reward_item, current_item, slot_name)

                        await callback.message.edit_text(
                            f"{dungeon_result.message}\n\n{comparison}",
                            reply_markup=get_reward_keyboard(reward_item.id, player.id),
                        )
                    else:
                        await callback.message.edit_text(
                            dungeon_result.message,
                            reply_markup=None,
                        )
                else:
                    await callback.message.edit_text(
                        dungeon_result.message,
                        reply_markup=None,
                    )
            elif dungeon_result.dungeon_failed:
                await callback.message.edit_text(
                    dungeon_result.message,
                    reply_markup=None,
                )
            elif dungeon_result.stage_completed:
                # Stage cleared, moving to next
                dungeon_state = await dungeon_service.get_dungeon_state(dungeon_id)
                if dungeon_state:
                    text = format_dungeon_state(dungeon_state)
                    await callback.message.edit_text(
                        f"{dungeon_result.message}\n\n{text}\n\nChoose your action:",
                        reply_markup=get_dungeon_action_keyboard(dungeon_result.duel_id, dungeon_id),
                    )
            await callback.answer()
        else:
            # Duel continues - show updated state
            dungeon_state = await dungeon_service.get_dungeon_state(dungeon_id)
            if dungeon_state:
                text = format_dungeon_state(dungeon_state, duel_state)
                await callback.message.edit_text(
                    f"{text}\n\nChoose your action:",
                    reply_markup=get_dungeon_action_keyboard(duel_id, dungeon_id),
                )
            await callback.answer("Action submitted!")


@router.callback_query(F.data.startswith(DUNGEON_ABANDON))
async def callback_abandon_dungeon(callback: CallbackQuery) -> None:
    """Handle abandon dungeon button."""
    if not callback.data or not callback.from_user or not callback.message:
        return

    dungeon_id = int(callback.data.replace(DUNGEON_ABANDON, ""))

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
async def callback_equip_reward(callback: CallbackQuery) -> None:
    """Handle equip reward button."""
    if not callback.data or not callback.from_user or not callback.message:
        return

    # Parse: reward_equip:{item_id}:{player_id}
    parts = callback.data.replace(REWARD_EQUIP, "").split(":")
    if len(parts) != 2:
        return

    item_id = int(parts[0])
    expected_player_id = int(parts[1])

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
async def callback_reject_reward(callback: CallbackQuery) -> None:
    """Handle reject reward button."""
    if not callback.data or not callback.message:
        return

    await callback.message.edit_text(
        "Reward rejected. Better luck next time!",
        reply_markup=None,
    )
    await callback.answer("Reward rejected.")
