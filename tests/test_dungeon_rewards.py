"""Tests for dungeon rewards and default items."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from vaudeville_rpg.bot.handlers.dungeons import format_item_mechanics
from vaudeville_rpg.db.models.dungeons import Dungeon
from vaudeville_rpg.db.models.enums import ActionType, DungeonDifficulty, DungeonStatus, ItemSlot, TargetType
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


def _create_mock_effect(action_type: ActionType, value: int, target: TargetType, attribute: str | None = None) -> MagicMock:
    """Create a mock effect with the given action type, value, and target."""
    effect = MagicMock()
    effect.target = target
    effect.action = MagicMock()
    effect.action.action_type = action_type
    effect.action.action_data = {"value": value}
    if attribute:
        effect.action.action_data["attribute"] = attribute
    return effect


def _create_mock_item_with_effects(effects: list[MagicMock]) -> MagicMock:
    """Create a mock item with the given effects."""
    item = MagicMock()
    item.effects = effects
    return item


class TestFormatItemMechanics:
    """Tests for format_item_mechanics function."""

    def test_no_effects_returns_no_special_effects(self) -> None:
        """Item with no effects should return 'No special effects'."""
        item = _create_mock_item_with_effects([])
        result = format_item_mechanics(item)
        assert result == "No special effects"

    def test_attack_action_formats_correctly(self) -> None:
        """Attack action should format as 'Deals X damage to target'."""
        effect = _create_mock_effect(ActionType.ATTACK, 15, TargetType.ENEMY)
        item = _create_mock_item_with_effects([effect])
        result = format_item_mechanics(item)
        assert result == "Deals 15 damage to enemy"

    def test_damage_action_formats_correctly(self) -> None:
        """Damage action should format as 'Deals X damage to target'."""
        effect = _create_mock_effect(ActionType.DAMAGE, 10, TargetType.ENEMY)
        item = _create_mock_item_with_effects([effect])
        result = format_item_mechanics(item)
        assert result == "Deals 10 damage to enemy"

    def test_heal_action_formats_correctly(self) -> None:
        """Heal action should format as 'Heals X HP'."""
        effect = _create_mock_effect(ActionType.HEAL, 20, TargetType.SELF)
        item = _create_mock_item_with_effects([effect])
        result = format_item_mechanics(item)
        assert result == "Heals 20 HP"

    def test_add_stacks_action_formats_correctly(self) -> None:
        """Add stacks action should format with attribute name."""
        effect = _create_mock_effect(ActionType.ADD_STACKS, 3, TargetType.ENEMY, "poison")
        item = _create_mock_item_with_effects([effect])
        result = format_item_mechanics(item)
        assert result == "Adds 3 Poison to enemy"

    def test_add_stacks_to_self_formats_correctly(self) -> None:
        """Add stacks to self should show 'self' as target."""
        effect = _create_mock_effect(ActionType.ADD_STACKS, 5, TargetType.SELF, "armor")
        item = _create_mock_item_with_effects([effect])
        result = format_item_mechanics(item)
        assert result == "Adds 5 Armor to self"

    def test_remove_stacks_action_formats_correctly(self) -> None:
        """Remove stacks action should format with attribute name."""
        effect = _create_mock_effect(ActionType.REMOVE_STACKS, 2, TargetType.ENEMY, "armor")
        item = _create_mock_item_with_effects([effect])
        result = format_item_mechanics(item)
        assert result == "Removes 2 Armor from enemy"

    def test_reduce_incoming_damage_formats_correctly(self) -> None:
        """Reduce incoming damage action should format correctly."""
        effect = _create_mock_effect(ActionType.REDUCE_INCOMING_DAMAGE, 5, TargetType.SELF)
        item = _create_mock_item_with_effects([effect])
        result = format_item_mechanics(item)
        assert result == "Reduces incoming damage by 5"

    def test_spend_action_formats_correctly(self) -> None:
        """Spend action should format as 'Costs X SP'."""
        effect = _create_mock_effect(ActionType.SPEND, 10, TargetType.SELF)
        item = _create_mock_item_with_effects([effect])
        result = format_item_mechanics(item)
        assert result == "Costs 10 SP"

    def test_multiple_effects_joined_with_comma(self) -> None:
        """Multiple effects should be joined with comma."""
        effects = [
            _create_mock_effect(ActionType.ATTACK, 15, TargetType.ENEMY),
            _create_mock_effect(ActionType.ADD_STACKS, 3, TargetType.ENEMY, "poison"),
        ]
        item = _create_mock_item_with_effects(effects)
        result = format_item_mechanics(item)
        assert result == "Deals 15 damage to enemy, Adds 3 Poison to enemy"

    def test_underscore_in_attribute_converted_to_space(self) -> None:
        """Underscores in attribute names should be converted to spaces."""
        effect = _create_mock_effect(ActionType.ADD_STACKS, 2, TargetType.SELF, "holy_defense")
        item = _create_mock_item_with_effects([effect])
        result = format_item_mechanics(item)
        assert result == "Adds 2 Holy Defense to self"

    def test_duplicate_damage_effects_are_consolidated(self) -> None:
        """Multiple damage effects to same target should be summed."""
        effects = [
            _create_mock_effect(ActionType.ATTACK, 10, TargetType.ENEMY),
            _create_mock_effect(ActionType.ATTACK, 10, TargetType.ENEMY),
            _create_mock_effect(ActionType.ADD_STACKS, 1, TargetType.ENEMY, "desert_dryness"),
        ]
        item = _create_mock_item_with_effects(effects)
        result = format_item_mechanics(item)
        assert result == "Deals 20 damage to enemy, Adds 1 Desert Dryness to enemy"

    def test_attack_and_damage_types_consolidated(self) -> None:
        """ATTACK and DAMAGE action types should be treated as same for consolidation."""
        effects = [
            _create_mock_effect(ActionType.ATTACK, 10, TargetType.ENEMY),
            _create_mock_effect(ActionType.DAMAGE, 5, TargetType.ENEMY),
        ]
        item = _create_mock_item_with_effects(effects)
        result = format_item_mechanics(item)
        assert result == "Deals 15 damage to enemy"

    def test_same_stacks_different_targets_not_consolidated(self) -> None:
        """Stacks to different targets should not be consolidated."""
        effects = [
            _create_mock_effect(ActionType.ADD_STACKS, 3, TargetType.ENEMY, "poison"),
            _create_mock_effect(ActionType.ADD_STACKS, 2, TargetType.SELF, "poison"),
        ]
        item = _create_mock_item_with_effects(effects)
        result = format_item_mechanics(item)
        assert "Adds 3 Poison to enemy" in result
        assert "Adds 2 Poison to self" in result
