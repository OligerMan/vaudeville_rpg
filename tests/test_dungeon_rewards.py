"""Tests for dungeon rewards and default items."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from vaudeville_rpg.db.models.dungeons import Dungeon
from vaudeville_rpg.db.models.enums import DungeonDifficulty, DungeonStatus, ItemSlot
from vaudeville_rpg.db.models.items import Item
from vaudeville_rpg.db.models.players import Player
from vaudeville_rpg.db.models.settings import Setting
from vaudeville_rpg.services.dungeons import REWARD_RARITY_BY_DIFFICULTY, DungeonService
from vaudeville_rpg.services.players import PlayerService


@pytest.fixture
async def reward_setting(db_session: AsyncSession) -> Setting:
    """Create a setting with items for testing rewards."""
    setting = Setting(
        telegram_chat_id=123456789,
        name="Reward Test Setting",
        special_points_name="Mana",
        special_points_regen=5,
    )
    db_session.add(setting)
    await db_session.flush()

    # Create items with different rarities
    items = [
        Item(
            setting_id=setting.id,
            name="Fist",
            description="Default weapon",
            slot=ItemSlot.ATTACK,
            rarity=1,
        ),
        Item(
            setting_id=setting.id,
            name="Common Sword",
            description="A common sword",
            slot=ItemSlot.ATTACK,
            rarity=1,
        ),
        Item(
            setting_id=setting.id,
            name="Uncommon Blade",
            description="An uncommon blade",
            slot=ItemSlot.ATTACK,
            rarity=2,
        ),
        Item(
            setting_id=setting.id,
            name="Rare Saber",
            description="A rare saber",
            slot=ItemSlot.ATTACK,
            rarity=3,
        ),
        Item(
            setting_id=setting.id,
            name="Common Shield",
            description="A common shield",
            slot=ItemSlot.DEFENSE,
            rarity=1,
        ),
        Item(
            setting_id=setting.id,
            name="Uncommon Armor",
            description="Uncommon armor",
            slot=ItemSlot.DEFENSE,
            rarity=2,
        ),
    ]
    for item in items:
        db_session.add(item)
    await db_session.flush()

    return setting


class TestDefaultFistItem:
    """Tests for default Fist item auto-equip."""

    async def test_new_player_gets_fist_equipped(self, db_session: AsyncSession, reward_setting: Setting) -> None:
        """New players should have Fist auto-equipped."""
        service = PlayerService(db_session)

        player = await service.get_or_create_player(
            telegram_user_id=99999,
            setting_id=reward_setting.id,
            display_name="TestPlayer",
        )

        assert player.attack_item_id is not None

        # Verify it's the Fist
        fist = await db_session.get(Item, player.attack_item_id)
        assert fist is not None
        assert fist.name == "Fist"

    async def test_player_without_fist_item_in_setting(self, db_session: AsyncSession) -> None:
        """Player created in setting without Fist should have None."""
        # Create setting without Fist item
        setting = Setting(
            telegram_chat_id=999999,
            name="Empty Setting",
            special_points_name="Power",
            special_points_regen=3,
        )
        db_session.add(setting)
        await db_session.flush()

        service = PlayerService(db_session)
        player = await service.get_or_create_player(
            telegram_user_id=88888,
            setting_id=setting.id,
            display_name="NoFistPlayer",
        )

        assert player.attack_item_id is None


class TestDungeonRewardRarity:
    """Tests for reward rarity by difficulty."""

    def test_easy_gives_common_only(self) -> None:
        """Easy dungeons should give common items only."""
        min_r, max_r = REWARD_RARITY_BY_DIFFICULTY[DungeonDifficulty.EASY]
        assert min_r == 1
        assert max_r == 1

    def test_normal_gives_common_uncommon(self) -> None:
        """Normal dungeons should give common or uncommon."""
        min_r, max_r = REWARD_RARITY_BY_DIFFICULTY[DungeonDifficulty.NORMAL]
        assert min_r == 1
        assert max_r == 2

    def test_hard_gives_uncommon_rare(self) -> None:
        """Hard dungeons should give uncommon or rare."""
        min_r, max_r = REWARD_RARITY_BY_DIFFICULTY[DungeonDifficulty.HARD]
        assert min_r == 2
        assert max_r == 3

    def test_nightmare_gives_uncommon_rare(self) -> None:
        """Nightmare dungeons should give uncommon or rare."""
        min_r, max_r = REWARD_RARITY_BY_DIFFICULTY[DungeonDifficulty.NIGHTMARE]
        assert min_r == 2
        assert max_r == 3


class TestDungeonRewardGeneration:
    """Tests for reward generation on dungeon completion."""

    async def test_generate_reward_returns_item_in_rarity_range(self, db_session: AsyncSession, reward_setting: Setting) -> None:
        """Reward should be within the rarity range for the difficulty."""
        # Create a player
        player = Player(
            telegram_user_id=12345,
            setting_id=reward_setting.id,
            display_name="RewardTestPlayer",
            max_hp=100,
            max_special_points=50,
            rating=1000,
        )
        db_session.add(player)
        await db_session.flush()

        # Create a completed dungeon
        dungeon = Dungeon(
            player_id=player.id,
            setting_id=reward_setting.id,
            name="Test Dungeon",
            difficulty=DungeonDifficulty.HARD,
            total_stages=4,
            current_stage=4,
            status=DungeonStatus.COMPLETED,
        )
        db_session.add(dungeon)
        await db_session.flush()

        service = DungeonService(db_session)
        reward = await service._generate_reward(dungeon)

        assert reward is not None
        # Hard difficulty: rarity 2-3
        assert reward.rarity >= 2
        assert reward.rarity <= 3

    async def test_generate_reward_easy_only_common(self, db_session: AsyncSession, reward_setting: Setting) -> None:
        """Easy dungeon reward should only be common."""
        player = Player(
            telegram_user_id=12346,
            setting_id=reward_setting.id,
            display_name="EasyRewardPlayer",
            max_hp=100,
            max_special_points=50,
            rating=1000,
        )
        db_session.add(player)
        await db_session.flush()

        dungeon = Dungeon(
            player_id=player.id,
            setting_id=reward_setting.id,
            name="Easy Dungeon",
            difficulty=DungeonDifficulty.EASY,
            total_stages=2,
            current_stage=2,
            status=DungeonStatus.COMPLETED,
        )
        db_session.add(dungeon)
        await db_session.flush()

        service = DungeonService(db_session)

        # Generate multiple rewards to test randomness stays in range
        for _ in range(10):
            reward = await service._generate_reward(dungeon)
            assert reward is not None
            assert reward.rarity == 1  # Common only for easy

    async def test_generate_reward_returns_none_when_no_items(self, db_session: AsyncSession) -> None:
        """Should return None when no items in rarity range exist."""
        # Create setting without any items
        setting = Setting(
            telegram_chat_id=777777,
            name="Empty Setting",
            special_points_name="Power",
            special_points_regen=3,
        )
        db_session.add(setting)
        await db_session.flush()

        player = Player(
            telegram_user_id=77777,
            setting_id=setting.id,
            display_name="NoItemPlayer",
            max_hp=100,
            max_special_points=50,
            rating=1000,
        )
        db_session.add(player)
        await db_session.flush()

        dungeon = Dungeon(
            player_id=player.id,
            setting_id=setting.id,
            name="Empty Dungeon",
            difficulty=DungeonDifficulty.NORMAL,
            total_stages=3,
            current_stage=3,
            status=DungeonStatus.COMPLETED,
        )
        db_session.add(dungeon)
        await db_session.flush()

        service = DungeonService(db_session)
        reward = await service._generate_reward(dungeon)

        assert reward is None


class TestDungeonResultRewardField:
    """Tests for DungeonResult reward_item_id field."""

    async def test_dungeon_result_has_reward_field(self) -> None:
        """DungeonResult should have reward_item_id field."""
        from vaudeville_rpg.services.dungeons import DungeonResult

        result = DungeonResult(
            success=True,
            message="Test",
            dungeon_completed=True,
            reward_item_id=42,
        )

        assert result.reward_item_id == 42

    async def test_dungeon_result_reward_field_defaults_none(self) -> None:
        """DungeonResult.reward_item_id should default to None."""
        from vaudeville_rpg.services.dungeons import DungeonResult

        result = DungeonResult(success=True, message="Test")

        assert result.reward_item_id is None
