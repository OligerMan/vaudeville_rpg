"""Bot utilities - error handling, logging, and validation helpers."""

import functools
import logging
from typing import Any, Callable

from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

logger = logging.getLogger("vaudeville_rpg.bot")


def safe_handler(func: Callable) -> Callable:
    """Decorator to wrap handlers with error handling.

    Catches all exceptions, logs them, and sends a user-friendly error message.
    Works with both Message and CallbackQuery handlers.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Find the message or callback in args
        update: Message | CallbackQuery | None = None
        for arg in args:
            if isinstance(arg, (Message, CallbackQuery)):
                update = arg
                break

        try:
            return await func(*args, **kwargs)
        except TelegramBadRequest as e:
            # Handle "query is too old" - this happens when user clicks old buttons
            if "query is too old" in str(e).lower():
                logger.debug(f"Ignoring old callback query in {func.__name__}")
                return None
            # Re-raise other TelegramBadRequest errors to be handled below
            raise
        except Exception as e:
            # Log the error with full context
            user_id = None
            chat_id = None

            if isinstance(update, Message):
                user_id = update.from_user.id if update.from_user else None
                chat_id = update.chat.id
            elif isinstance(update, CallbackQuery):
                user_id = update.from_user.id
                chat_id = update.message.chat.id if update.message else None

            logger.exception(
                f"Handler error in {func.__name__}: {e}",
                extra={
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "handler": func.__name__,
                },
            )

            # Send user-friendly error message
            error_msg = "Something went wrong. Please try again later."

            try:
                if isinstance(update, Message):
                    await update.reply(error_msg)
                elif isinstance(update, CallbackQuery):
                    await update.answer(error_msg, show_alert=True)
            except TelegramBadRequest as tg_err:
                # If we can't answer because query is too old, just ignore
                if "query is too old" not in str(tg_err).lower():
                    logger.exception("Failed to send error message to user")
            except Exception:
                # If we can't even send the error message, just log it
                logger.exception("Failed to send error message to user")

            return None

    return wrapper


def log_command(command: str) -> Callable:
    """Decorator to log command usage.

    Args:
        command: The command name (e.g., "/start", "/dungeon")
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find the message in args
            for arg in args:
                if isinstance(arg, Message):
                    user_id = arg.from_user.id if arg.from_user else None
                    chat_id = arg.chat.id
                    username = arg.from_user.username if arg.from_user else None

                    logger.info(f"Command {command} from user {user_id} (@{username}) in chat {chat_id}")
                    break

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def log_callback(action: str) -> Callable:
    """Decorator to log callback query actions.

    Args:
        action: Description of the action (e.g., "accept_duel", "select_difficulty")
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find the callback query in args
            for arg in args:
                if isinstance(arg, CallbackQuery):
                    user_id = arg.from_user.id
                    chat_id = arg.message.chat.id if arg.message else None
                    username = arg.from_user.username

                    logger.info(f"Callback {action} from user {user_id} (@{username}) in chat {chat_id}")
                    break

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def validate_message_user(message: Message) -> bool:
    """Check if message has valid from_user.

    Args:
        message: The Telegram message

    Returns:
        True if from_user exists and has valid id
    """
    return message.from_user is not None and message.from_user.id is not None


def validate_callback_message(callback: CallbackQuery) -> bool:
    """Check if callback query has valid message.

    Args:
        callback: The Telegram callback query

    Returns:
        True if message exists
    """
    return callback.message is not None


def validate_reply_message(message: Message) -> bool:
    """Check if message is a valid reply with target user.

    Args:
        message: The Telegram message

    Returns:
        True if reply_to_message exists with valid from_user
    """
    return (
        message.reply_to_message is not None
        and message.reply_to_message.from_user is not None
        and message.reply_to_message.from_user.id is not None
    )


def get_display_name(user: types.User | None) -> str:
    """Get display name for a Telegram user.

    Args:
        user: The Telegram user

    Returns:
        Display name (full name or username or "Unknown")
    """
    if user is None:
        return "Unknown"

    if user.full_name:
        return user.full_name
    if user.username:
        return f"@{user.username}"
    return f"User {user.id}"


def format_item_mechanics(item: Any) -> str:
    """Format item mechanics description from its effects.

    Returns a human-readable description of what the item does mechanically.
    Consolidates similar effects (e.g., multiple damage effects are summed).

    Args:
        item: Item with effects relationship loaded

    Returns:
        Formatted mechanics description string
    """
    # Import here to avoid circular imports
    from ..db.models.enums import ActionType, TargetType

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
