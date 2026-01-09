"""Admin handlers - setting generation and management."""

import html

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import delete, select

from ...config import get_settings
from ...db.engine import async_session_factory
from ...db.models.admin import PendingGeneration
from ...llm.setting_factory import SettingFactory
from ...services.settings import SettingsService
from ..utils import (
    log_callback,
    log_command,
    safe_handler,
    validate_callback_message,
    validate_message_user,
)

router = Router(name="admin")


# Callback data prefixes
CONFIRM_GENERATE = "admin_gen_confirm:"
CANCEL_GENERATE = "admin_gen_cancel:"


async def is_admin(user_id: int, chat_id: int, bot: Bot) -> bool:
    """Check if user is an admin (bot owner or chat admin).

    Args:
        user_id: Telegram user ID
        chat_id: Telegram chat ID
        bot: Bot instance for API calls

    Returns:
        True if user is admin, False otherwise
    """
    settings = get_settings()

    # Check if user is in bot owner list
    admin_ids = settings.get_admin_user_ids()
    if user_id in admin_ids:
        return True

    # Check if user is chat admin
    try:
        chat_admins = await bot.get_chat_administrators(chat_id)
        return any(admin.user.id == user_id for admin in chat_admins)
    except Exception:
        # If we can't check chat admins (e.g., private chat), only allow bot owners
        return False


def get_confirm_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Create confirmation keyboard for setting replacement."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Replace Setting",
                    callback_data=f"{CONFIRM_GENERATE}{chat_id}",
                ),
                InlineKeyboardButton(
                    text="Cancel",
                    callback_data=f"{CANCEL_GENERATE}{chat_id}",
                ),
            ]
        ]
    )


@router.message(Command("generate_setting"))
@safe_handler
@log_command("/generate_setting")
async def cmd_generate_setting(message: Message, bot: Bot) -> None:
    """Handle /generate_setting command - generate a new game setting.

    Usage: /generate_setting <description>
    Example: /generate_setting A dark fantasy world with necromancy and holy magic
    """
    if not validate_message_user(message):
        await message.answer("Could not identify user.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id

    # Check admin permission
    if not await is_admin(user_id, chat_id, bot):
        await message.answer("Only chat administrators can use this command.")
        return

    # Check if LLM is configured
    settings = get_settings()
    if not settings.llm_api_key:
        await message.answer("LLM not configured. Set LLM_API_KEY in environment to enable content generation.")
        return

    # Parse description from command arguments
    if not message.text:
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "<b>Usage:</b> /generate_setting &lt;description&gt;\n\n"
            "<b>Example:</b>\n"
            "/generate_setting A dark fantasy world where necromancers battle holy knights",
            parse_mode="HTML",
        )
        return

    description = parts[1].strip()
    if len(description) < 20:
        await message.answer("Please provide a more detailed description (at least 20 characters).")
        return

    # Check if setting already exists
    async with async_session_factory() as session:
        settings_service = SettingsService(session)
        existing = await settings_service.get_setting(chat_id)

        if existing:
            # Get stats and show confirmation
            stats = await settings_service.get_setting_stats(existing)

            # Store pending description in database
            pending = PendingGeneration(
                chat_id=chat_id,
                user_id=message.from_user.id,
                description=description,
            )
            # Delete any existing pending for this chat
            await session.execute(delete(PendingGeneration).where(PendingGeneration.chat_id == chat_id))
            session.add(pending)
            await session.commit()

            warning_text = (
                f"<b>Warning: A setting already exists in this chat!</b>\n\n"
                f'Current setting: "{html.escape(stats.name[:50])}"\n'
                f"- {stats.item_count} items\n"
                f"- {stats.player_count} players\n"
            )

            if stats.active_duel_count > 0:
                warning_text += f"- {stats.active_duel_count} active duels\n"
            if stats.dungeon_count > 0:
                warning_text += f"- {stats.dungeon_count} active dungeons\n"

            warning_text += "\n<b>Generating a new setting will DELETE all existing data.</b>"

            await message.answer(
                warning_text,
                reply_markup=get_confirm_keyboard(chat_id),
                parse_mode="HTML",
            )
        else:
            # No existing setting, start generation immediately
            await _start_generation(message, chat_id, description)


async def _start_generation(message: Message, chat_id: int, description: str) -> None:
    """Start the setting generation process."""
    # Send initial message
    status_msg = await message.answer(
        "Generating setting... This may take a minute.\n\nStep 1/5: Generating setting description and attributes..."
    )

    async with async_session_factory() as session:
        try:
            factory = SettingFactory(session)
            result = await factory.create_setting(
                telegram_chat_id=chat_id,
                user_prompt=description,
                validate=True,
                retry_on_validation_fail=True,
                max_retries=5,
            )

            if result.success:
                await session.commit()

                setting_name = html.escape(result.setting.name[:80]) if result.setting else "Unknown"
                success_text = (
                    "<b>Setting generated successfully!</b>\n\n"
                    f"<b>Name:</b> {setting_name}\n"
                    f"<b>Attributes:</b> {result.attributes_created}\n"
                    f"<b>World Rules:</b> {result.world_rules_created}\n"
                    f"<b>Items:</b> {result.items_created}\n\n"
                    "Players can now use /challenge to start duels!"
                )

                await status_msg.edit_text(success_text, parse_mode="HTML")
            else:
                await session.rollback()
                await status_msg.edit_text(
                    f"<b>Generation failed:</b>\n{html.escape(result.message)}",
                    parse_mode="HTML",
                )

        except Exception as e:
            await session.rollback()
            await status_msg.edit_text(
                f"<b>Error during generation:</b>\n{html.escape(str(e)[:200])}",
                parse_mode="HTML",
            )


@router.callback_query(F.data.startswith(CONFIRM_GENERATE))
@safe_handler
@log_callback("confirm_generate")
async def callback_confirm_generate(callback: CallbackQuery) -> None:
    """Handle confirmation to replace existing setting."""
    if not callback.data or not callback.from_user or not validate_callback_message(callback):
        await callback.answer("Invalid request.", show_alert=True)
        return

    try:
        chat_id = int(callback.data.replace(CONFIRM_GENERATE, ""))
    except ValueError:
        await callback.answer("Invalid chat ID.", show_alert=True)
        return

    # Verify the user is still an admin
    if not await is_admin(callback.from_user.id, chat_id, callback.bot):
        await callback.answer("You are not authorized to do this.", show_alert=True)
        return

    # Answer callback immediately to prevent timeout (generation takes a long time)
    await callback.answer("Starting generation...")

    # Get pending description from database
    async with async_session_factory() as session:
        stmt = select(PendingGeneration).where(PendingGeneration.chat_id == chat_id)
        result = await session.execute(stmt)
        pending = result.scalar_one_or_none()

        if not pending:
            await callback.answer("Generation request expired. Please try again.", show_alert=True)
            await callback.message.edit_text("Generation request expired.")
            return

        # Check if expired
        if pending.is_expired():
            await session.execute(delete(PendingGeneration).where(PendingGeneration.chat_id == chat_id))
            await session.commit()
            await callback.answer("Generation request expired. Please try again.", show_alert=True)
            await callback.message.edit_text("Generation request expired.")
            return

        description = pending.description

        # Delete pending record
        await session.execute(delete(PendingGeneration).where(PendingGeneration.chat_id == chat_id))

        # Delete existing setting
        settings_service = SettingsService(session)
        existing = await settings_service.get_setting(chat_id)

        if existing:
            await settings_service.delete_setting(existing)

        await session.commit()

    # Update message to show generation started
    await callback.message.edit_text(
        "Generating setting... This may take a minute.\n\nStep 1/5: Generating setting description and attributes..."
    )

    # Start generation
    async with async_session_factory() as session:
        try:
            factory = SettingFactory(session)
            result = await factory.create_setting(
                telegram_chat_id=chat_id,
                user_prompt=description,
                validate=True,
                retry_on_validation_fail=True,
                max_retries=5,
            )

            if result.success:
                await session.commit()

                setting_name = html.escape(result.setting.name[:80]) if result.setting else "Unknown"
                success_text = (
                    "<b>Setting generated successfully!</b>\n\n"
                    f"<b>Name:</b> {setting_name}\n"
                    f"<b>Attributes:</b> {result.attributes_created}\n"
                    f"<b>World Rules:</b> {result.world_rules_created}\n"
                    f"<b>Items:</b> {result.items_created}\n\n"
                    "Players can now use /challenge to start duels!"
                )

                await callback.message.edit_text(success_text, parse_mode="HTML")
            else:
                await session.rollback()
                await callback.message.edit_text(
                    f"<b>Generation failed:</b>\n{html.escape(result.message)}",
                    parse_mode="HTML",
                )

        except Exception as e:
            await session.rollback()
            await callback.message.edit_text(
                f"<b>Error during generation:</b>\n{html.escape(str(e)[:200])}",
                parse_mode="HTML",
            )


@router.callback_query(F.data.startswith(CANCEL_GENERATE))
@safe_handler
@log_callback("cancel_generate")
async def callback_cancel_generate(callback: CallbackQuery) -> None:
    """Handle cancellation of setting generation."""
    if not callback.data or not validate_callback_message(callback):
        await callback.answer("Invalid request.", show_alert=True)
        return

    try:
        chat_id = int(callback.data.replace(CANCEL_GENERATE, ""))
    except ValueError:
        await callback.answer("Invalid chat ID.", show_alert=True)
        return

    # Remove pending description from database
    async with async_session_factory() as session:
        await session.execute(delete(PendingGeneration).where(PendingGeneration.chat_id == chat_id))
        await session.commit()

    await callback.message.edit_text("Setting generation cancelled.")
    await callback.answer()
