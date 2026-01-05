"""Tests for SettingsService."""

import pytest

from vaudeville_rpg.db.models.enums import (
    ItemSlot,
)
from vaudeville_rpg.db.models.items import Item
from vaudeville_rpg.db.models.players import Player
from vaudeville_rpg.db.models.settings import Setting


class TestSettingsService:
    """Tests for SettingsService."""

    @pytest.fixture
    def setting(self) -> Setting:
        """Create a test setting."""
        return Setting(
            id=1,
            telegram_chat_id=123456789,
            name="Test Fantasy Setting",
            description="A magical test world",
            special_points_name="Mana",
            special_points_regen=5,
        )

    @pytest.fixture
    def player(self, setting: Setting) -> Player:
        """Create a test player."""
        return Player(
            id=1,
            telegram_user_id=111111,
            setting_id=setting.id,
            display_name="Test Player",
            max_hp=100,
            max_special_points=50,
            rating=1000,
            is_bot=False,
        )

    @pytest.fixture
    def bot_player(self, setting: Setting) -> Player:
        """Create a test bot player."""
        return Player(
            id=2,
            telegram_user_id=222222,
            setting_id=setting.id,
            display_name="Bot Enemy",
            max_hp=80,
            max_special_points=40,
            rating=1000,
            is_bot=True,
        )

    @pytest.fixture
    def item(self, setting: Setting) -> Item:
        """Create a test item."""
        return Item(
            id=1,
            setting_id=setting.id,
            name="Test Sword",
            description="A test weapon",
            slot=ItemSlot.ATTACK,
            rarity=1,
        )


class TestGetSetting:
    """Tests for get_setting method."""

    def test_get_setting_returns_none_when_not_found(self) -> None:
        """Test that get_setting returns None when setting doesn't exist."""
        # This is a placeholder for actual async database test
        # In production, we'd use pytest-asyncio and test fixtures
        pass


class TestGetSettingStats:
    """Tests for get_setting_stats method."""

    def test_setting_stats_dataclass_fields(self) -> None:
        """Test that SettingStats has all required fields."""
        from vaudeville_rpg.services.settings import SettingStats

        stats = SettingStats(
            name="Test Setting",
            item_count=5,
            player_count=3,
            active_duel_count=1,
            dungeon_count=2,
        )

        assert stats.name == "Test Setting"
        assert stats.item_count == 5
        assert stats.player_count == 3
        assert stats.active_duel_count == 1
        assert stats.dungeon_count == 2


class TestAdminConfig:
    """Tests for admin user ID parsing."""

    def test_get_admin_user_ids_empty(self) -> None:
        """Test parsing empty admin user IDs."""
        from vaudeville_rpg.config import Settings

        # Create settings with no admin_user_ids
        settings = Settings(
            bot_token="test_token",
            database_url="postgresql+asyncpg://test:test@localhost/test",
            admin_user_ids=None,
        )

        assert settings.get_admin_user_ids() == []

    def test_get_admin_user_ids_single(self) -> None:
        """Test parsing single admin user ID."""
        from vaudeville_rpg.config import Settings

        settings = Settings(
            bot_token="test_token",
            database_url="postgresql+asyncpg://test:test@localhost/test",
            admin_user_ids="123456",
        )

        assert settings.get_admin_user_ids() == [123456]

    def test_get_admin_user_ids_multiple(self) -> None:
        """Test parsing multiple admin user IDs."""
        from vaudeville_rpg.config import Settings

        settings = Settings(
            bot_token="test_token",
            database_url="postgresql+asyncpg://test:test@localhost/test",
            admin_user_ids="123456, 789012, 345678",
        )

        assert settings.get_admin_user_ids() == [123456, 789012, 345678]

    def test_get_admin_user_ids_with_whitespace(self) -> None:
        """Test parsing admin user IDs with extra whitespace."""
        from vaudeville_rpg.config import Settings

        settings = Settings(
            bot_token="test_token",
            database_url="postgresql+asyncpg://test:test@localhost/test",
            admin_user_ids="  123456  ,  789012  ",
        )

        assert settings.get_admin_user_ids() == [123456, 789012]

    def test_get_admin_user_ids_empty_string(self) -> None:
        """Test parsing empty string admin user IDs."""
        from vaudeville_rpg.config import Settings

        settings = Settings(
            bot_token="test_token",
            database_url="postgresql+asyncpg://test:test@localhost/test",
            admin_user_ids="",
        )

        assert settings.get_admin_user_ids() == []

    def test_get_admin_user_ids_ignores_empty_entries(self) -> None:
        """Test that empty entries are ignored."""
        from vaudeville_rpg.config import Settings

        settings = Settings(
            bot_token="test_token",
            database_url="postgresql+asyncpg://test:test@localhost/test",
            admin_user_ids="123456,,789012,",
        )

        assert settings.get_admin_user_ids() == [123456, 789012]
