"""Settings service - handles setting management and deletion."""

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.duels import Duel
from ..db.models.dungeons import Dungeon
from ..db.models.items import Item
from ..db.models.players import Player
from ..db.models.settings import Setting


@dataclass
class SettingStats:
    """Statistics about a setting for display purposes."""

    name: str
    item_count: int
    player_count: int
    active_duel_count: int
    dungeon_count: int


class SettingsService:
    """Service for setting management operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_setting(self, telegram_chat_id: int) -> Setting | None:
        """Get setting for a chat if it exists.

        Args:
            telegram_chat_id: Telegram chat ID

        Returns:
            Setting instance or None if not found
        """
        stmt = select(Setting).where(Setting.telegram_chat_id == telegram_chat_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_setting_stats(self, setting: Setting) -> SettingStats:
        """Get statistics about a setting.

        Args:
            setting: Setting to get stats for

        Returns:
            SettingStats with counts of related entities
        """
        # Count items
        item_count_stmt = select(func.count(Item.id)).where(Item.setting_id == setting.id)
        item_result = await self.session.execute(item_count_stmt)
        item_count = item_result.scalar_one()

        # Count players (excluding bots)
        player_count_stmt = select(func.count(Player.id)).where(
            Player.setting_id == setting.id,
            Player.is_bot == False,  # noqa: E712
        )
        player_result = await self.session.execute(player_count_stmt)
        player_count = player_result.scalar_one()

        # Count active duels
        from ..db.models.enums import DuelStatus

        duel_count_stmt = select(func.count(Duel.id)).where(
            Duel.setting_id == setting.id,
            Duel.status.in_([DuelStatus.PENDING, DuelStatus.IN_PROGRESS]),
        )
        duel_result = await self.session.execute(duel_count_stmt)
        active_duel_count = duel_result.scalar_one()

        # Count active dungeons
        from ..db.models.enums import DungeonStatus

        dungeon_count_stmt = select(func.count(Dungeon.id)).where(
            Dungeon.setting_id == setting.id,
            Dungeon.status == DungeonStatus.IN_PROGRESS,
        )
        dungeon_result = await self.session.execute(dungeon_count_stmt)
        dungeon_count = dungeon_result.scalar_one()

        return SettingStats(
            name=setting.name,
            item_count=item_count,
            player_count=player_count,
            active_duel_count=active_duel_count,
            dungeon_count=dungeon_count,
        )

    async def delete_setting(self, setting: Setting) -> None:
        """Delete a setting and all related data.

        This method handles the proper deletion order:
        1. Delete dungeons (no cascade from setting)
        2. Delete duels (no cascade from setting)
        3. Delete setting (cascades to items, players, attributes, effects)

        Args:
            setting: Setting to delete
        """
        # Delete all dungeons for this setting
        dungeon_delete_stmt = delete(Dungeon).where(Dungeon.setting_id == setting.id)
        await self.session.execute(dungeon_delete_stmt)

        # Delete all duels for this setting
        duel_delete_stmt = delete(Duel).where(Duel.setting_id == setting.id)
        await self.session.execute(duel_delete_stmt)

        # Delete the setting (cascades to items, players, attributes, effects)
        await self.session.delete(setting)
        await self.session.flush()
