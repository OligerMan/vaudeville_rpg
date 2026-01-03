"""Player service - handles player creation and retrieval."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.players import Player
from ..db.models.settings import Setting


class PlayerService:
    """Service for player operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_player(
        self,
        telegram_user_id: int,
        setting_id: int,
        display_name: str,
    ) -> Player:
        """Get existing player or create new one.

        Args:
            telegram_user_id: Telegram user ID
            setting_id: Setting/chat this player belongs to
            display_name: Display name from Telegram

        Returns:
            Player instance
        """
        # Try to find existing player
        stmt = select(Player).where(
            Player.telegram_user_id == telegram_user_id,
            Player.setting_id == setting_id,
        )
        result = await self.session.execute(stmt)
        player = result.scalar_one_or_none()

        if player:
            # Update display name if changed
            if player.display_name != display_name:
                player.display_name = display_name
            return player

        # Create new player with default stats
        player = Player(
            telegram_user_id=telegram_user_id,
            setting_id=setting_id,
            display_name=display_name,
            max_hp=100,
            max_special_points=50,
            rating=1000,
        )
        self.session.add(player)
        await self.session.flush()
        return player

    async def get_player_by_id(self, player_id: int) -> Player | None:
        """Get player by ID."""
        stmt = select(Player).where(Player.id == player_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_setting(self, telegram_chat_id: int) -> Setting:
        """Get or create setting for a chat.

        Args:
            telegram_chat_id: Telegram chat ID

        Returns:
            Setting instance
        """
        stmt = select(Setting).where(Setting.telegram_chat_id == telegram_chat_id)
        result = await self.session.execute(stmt)
        setting = result.scalar_one_or_none()

        if setting:
            return setting

        # Create default setting for this chat
        setting = Setting(
            telegram_chat_id=telegram_chat_id,
            name="Default Setting",
            special_points_name="Mana",
            special_points_regen=5,
            max_generatable_attributes=3,
        )
        self.session.add(setting)
        await self.session.flush()
        return setting
