"""Duel handlers - /challenge, accept/decline, action selection."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ...db.engine import async_session_factory
from ...db.models.enums import DuelActionType
from ...services.duels import DuelService
from ...services.players import PlayerService

router = Router(name="duels")


# Callback data prefixes
ACCEPT_DUEL = "duel_accept:"
DECLINE_DUEL = "duel_decline:"
ACTION_PREFIX = "duel_action:"


def get_challenge_keyboard(duel_id: int) -> InlineKeyboardMarkup:
    """Create accept/decline keyboard for a duel challenge."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚔️ Accept",
                    callback_data=f"{ACCEPT_DUEL}{duel_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Decline",
                    callback_data=f"{DECLINE_DUEL}{duel_id}",
                ),
            ]
        ]
    )


def get_action_keyboard(duel_id: int) -> InlineKeyboardMarkup:
    """Create action selection keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚔️ Attack",
                    callback_data=f"{ACTION_PREFIX}{duel_id}:attack",
                ),
                InlineKeyboardButton(
                    text="🛡️ Defense",
                    callback_data=f"{ACTION_PREFIX}{duel_id}:defense",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✨ Misc",
                    callback_data=f"{ACTION_PREFIX}{duel_id}:misc",
                ),
                InlineKeyboardButton(
                    text="⏭️ Skip",
                    callback_data=f"{ACTION_PREFIX}{duel_id}:skip",
                ),
            ],
        ]
    )


def format_duel_state(duel_state: dict) -> str:
    """Format duel state for display."""
    lines = [f"<b>⚔️ Duel - Turn {duel_state['current_turn']}</b>\n"]

    for p in duel_state["participants"]:
        combat = p.get("combat_state")
        if combat:
            hp = combat["current_hp"]
            sp = combat["current_special_points"]
            stacks = combat.get("attribute_stacks", {})
            ready = "✅" if p["is_ready"] else "⏳"

            lines.append(f"{ready} <b>{p.get('display_name', 'Player')}</b>")
            lines.append(f"   ❤️ {hp} HP | 💙 {sp} SP")

            if stacks:
                stack_str = ", ".join(f"{k}: {v}" for k, v in stacks.items())
                lines.append(f"   📊 {stack_str}")

    return "\n".join(lines)


def format_turn_result(turn_result) -> str:
    """Format turn result for display."""
    if not turn_result:
        return ""

    lines = [f"\n<b>📜 Turn {turn_result.turn_number} Results:</b>"]

    for effect in turn_result.effects_applied:
        lines.append(f"• {effect.description}")

    if turn_result.is_duel_over:
        lines.append("\n<b>🏆 Duel Complete!</b>")

    return "\n".join(lines)


@router.message(Command("challenge"))
async def cmd_challenge(message: Message) -> None:
    """Handle /challenge command - initiate a duel."""
    if not message.reply_to_message:
        await message.answer("Reply to a user's message with /challenge to challenge them to a duel!")
        return

    challenger = message.from_user
    challenged = message.reply_to_message.from_user

    if not challenger or not challenged:
        await message.answer("Could not identify users.")
        return

    if challenger.id == challenged.id:
        await message.answer("You can't challenge yourself!")
        return

    if challenged.is_bot:
        await message.answer("You can't challenge a bot!")
        return

    async with async_session_factory() as session:
        player_service = PlayerService(session)
        duel_service = DuelService(session)

        # Get or create setting for this chat
        setting = await player_service.get_or_create_setting(message.chat.id)

        # Get or create players
        challenger_player = await player_service.get_or_create_player(
            telegram_user_id=challenger.id,
            setting_id=setting.id,
            display_name=challenger.full_name,
        )
        challenged_player = await player_service.get_or_create_player(
            telegram_user_id=challenged.id,
            setting_id=setting.id,
            display_name=challenged.full_name,
        )

        # Create the duel challenge
        result = await duel_service.create_challenge(
            setting_id=setting.id,
            challenger_id=challenger_player.id,
            challenged_id=challenged_player.id,
        )

        if not result.success:
            await message.answer(f"❌ {result.message}")
            await session.rollback()
            return

        await session.commit()

        await message.answer(
            f"⚔️ <b>{challenger.full_name}</b> challenges <b>{challenged.full_name}</b> to a duel!\n\n"
            f"{challenged.full_name}, do you accept?",
            reply_markup=get_challenge_keyboard(result.duel_id),
        )


@router.callback_query(F.data.startswith(ACCEPT_DUEL))
async def callback_accept_duel(callback: CallbackQuery) -> None:
    """Handle accept duel button."""
    if not callback.data or not callback.from_user:
        return

    duel_id = int(callback.data.replace(ACCEPT_DUEL, ""))

    async with async_session_factory() as session:
        player_service = PlayerService(session)
        duel_service = DuelService(session)

        # Get the duel
        duel = await duel_service.get_pending_duel(duel_id)
        if not duel:
            await callback.answer("This duel is no longer available.", show_alert=True)
            await callback.message.edit_reply_markup(reply_markup=None)
            return

        # Get setting and player
        setting = await player_service.get_or_create_setting(callback.message.chat.id)
        player = await player_service.get_or_create_player(
            telegram_user_id=callback.from_user.id,
            setting_id=setting.id,
            display_name=callback.from_user.full_name,
        )

        # Try to accept
        result = await duel_service.accept_challenge(duel_id, player.id)

        if not result.success:
            await callback.answer(result.message, show_alert=True)
            return

        await session.commit()

        # Get challenger and challenged names
        challenger_name = ""
        challenged_name = ""
        for p in duel.participants:
            if p.turn_order == 1:
                challenger_name = p.player.display_name
            else:
                challenged_name = p.player.display_name

        # Update message to show duel started
        await callback.message.edit_text(
            f"⚔️ <b>Duel Started!</b>\n\n{challenger_name} vs {challenged_name}\n\nBoth players, choose your action!",
            reply_markup=get_action_keyboard(duel_id),
        )
        await callback.answer("Duel accepted! Choose your action.")


@router.callback_query(F.data.startswith(DECLINE_DUEL))
async def callback_decline_duel(callback: CallbackQuery) -> None:
    """Handle decline duel button."""
    if not callback.data or not callback.from_user:
        return

    duel_id = int(callback.data.replace(DECLINE_DUEL, ""))

    async with async_session_factory() as session:
        player_service = PlayerService(session)
        duel_service = DuelService(session)

        # Get the duel
        duel = await duel_service.get_pending_duel(duel_id)
        if not duel:
            await callback.answer("This duel is no longer available.", show_alert=True)
            await callback.message.edit_reply_markup(reply_markup=None)
            return

        # Get setting and player
        setting = await player_service.get_or_create_setting(callback.message.chat.id)
        player = await player_service.get_or_create_player(
            telegram_user_id=callback.from_user.id,
            setting_id=setting.id,
            display_name=callback.from_user.full_name,
        )

        # Try to decline
        result = await duel_service.decline_challenge(duel_id, player.id)

        if not result.success:
            await callback.answer(result.message, show_alert=True)
            return

        await session.commit()

        await callback.message.edit_text(
            f"❌ {callback.from_user.full_name} declined the duel challenge.",
            reply_markup=None,
        )
        await callback.answer("Duel declined.")


@router.callback_query(F.data.startswith(ACTION_PREFIX))
async def callback_duel_action(callback: CallbackQuery) -> None:
    """Handle action selection button."""
    if not callback.data or not callback.from_user:
        return

    # Parse callback data: duel_action:{duel_id}:{action}
    parts = callback.data.replace(ACTION_PREFIX, "").split(":")
    if len(parts) != 2:
        return

    duel_id = int(parts[0])
    action_str = parts[1]

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
        duel_service = DuelService(session)

        # Get the duel
        duel = await duel_service.get_active_duel(duel_id)
        if not duel:
            await callback.answer("This duel is no longer active.", show_alert=True)
            await callback.message.edit_reply_markup(reply_markup=None)
            return

        # Get setting and player
        setting = await player_service.get_or_create_setting(callback.message.chat.id)
        player = await player_service.get_or_create_player(
            telegram_user_id=callback.from_user.id,
            setting_id=setting.id,
            display_name=callback.from_user.full_name,
        )

        # Check if this player is in the duel
        is_participant = any(p.player_id == player.id for p in duel.participants)
        if not is_participant:
            await callback.answer("You are not in this duel!", show_alert=True)
            return

        # Submit the action
        result = await duel_service.submit_action(duel_id, player.id, action_type)

        if not result.success:
            await callback.answer(result.message, show_alert=True)
            return

        await session.commit()

        # Check if turn was resolved
        if result.turn_result:
            # Get updated duel state
            duel_state = await duel_service.get_duel_state(duel_id)

            # Format the result
            state_text = format_duel_state(duel_state) if duel_state else ""
            result_text = format_turn_result(result.turn_result)

            if result.turn_result.is_duel_over:
                # Find winner name
                winner_name = "Unknown"
                if duel_state:
                    for p in duel_state["participants"]:
                        if p["participant_id"] == result.turn_result.winner_participant_id:
                            winner_name = p.get("display_name", "Unknown")
                            break

                await callback.message.edit_text(
                    f"{state_text}{result_text}\n\n🏆 <b>{winner_name} wins!</b>",
                    reply_markup=None,
                )
            else:
                # Continue to next turn
                await callback.message.edit_text(
                    f"{state_text}{result_text}\n\nChoose your action for turn {duel_state['current_turn']}!",
                    reply_markup=get_action_keyboard(duel_id),
                )

            await callback.answer("Turn resolved!")
        else:
            # Waiting for opponent
            await callback.answer("Action submitted! Waiting for opponent...")
