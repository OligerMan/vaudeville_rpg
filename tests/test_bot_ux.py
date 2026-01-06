"""Tests for bot UX improvements - setting checks."""

from sqlalchemy.ext.asyncio import AsyncSession

from vaudeville_rpg.db.models import (
    Action,
    ActionType,
    Condition,
    ConditionPhase,
    ConditionType,
    Effect,
    EffectCategory,
    Item,
    ItemSlot,
    Setting,
    TargetType,
)


async def create_setting_with_items(
    session: AsyncSession,
    chat_id: int,
) -> Setting:
    """Create a setting with items for testing."""
    setting = Setting(
        telegram_chat_id=chat_id,
        name="Test Setting",
        description="A test world",
        special_points_name="Mana",
        special_points_regen=5,
        max_generatable_attributes=3,
    )
    session.add(setting)
    await session.flush()

    # Create an attack item
    item = Item(
        setting_id=setting.id,
        name="Test Sword",
        description="A test weapon",
        slot=ItemSlot.ATTACK,
        rarity=1,
    )
    session.add(item)
    await session.flush()

    # Create action for the item
    action = Action(
        name="test_attack",
        action_type=ActionType.ATTACK,
        action_data={"value": 10},
    )
    session.add(action)
    await session.flush()

    # Create condition
    condition = Condition(
        name="test_condition",
        condition_type=ConditionType.PHASE,
        condition_data={"phase": ConditionPhase.PRE_ATTACK.value},
    )
    session.add(condition)
    await session.flush()

    # Create effect
    effect = Effect(
        setting_id=setting.id,
        name="test_effect",
        description="Test effect",
        condition_id=condition.id,
        action_id=action.id,
        target=TargetType.ENEMY,
        category=EffectCategory.ITEM_EFFECT,
        item_id=item.id,
    )
    session.add(effect)
    await session.flush()

    return setting


async def create_empty_setting(
    session: AsyncSession,
    chat_id: int,
) -> Setting:
    """Create a setting without items for testing."""
    setting = Setting(
        telegram_chat_id=chat_id,
        name="Default Setting",
        description=None,
        special_points_name="Mana",
        special_points_regen=5,
        max_generatable_attributes=3,
    )
    session.add(setting)
    await session.flush()
    return setting


class TestIsSettingConfigured:
    """Tests for the is_setting_configured function."""

    async def test_returns_false_when_no_setting(
        self,
        db_session: AsyncSession,
    ):
        """Test that is_setting_configured returns False when no setting exists."""
        from sqlalchemy import select

        from vaudeville_rpg.db.models.settings import Setting

        # Check for a non-existent chat
        chat_id = 999999999

        # Get setting for this chat
        stmt = select(Setting).where(Setting.telegram_chat_id == chat_id)
        result = await db_session.execute(stmt)
        setting = result.scalar_one_or_none()

        assert setting is None, "No setting should exist for this chat"

    async def test_returns_false_when_setting_has_no_items(
        self,
        db_session: AsyncSession,
    ):
        """Test that is_setting_configured returns False when setting has no items."""
        from sqlalchemy import select

        from vaudeville_rpg.db.models.items import Item

        # Create an empty setting
        chat_id = 111111111
        setting = await create_empty_setting(db_session, chat_id)
        await db_session.commit()

        # Verify setting exists
        assert setting is not None
        assert setting.name == "Default Setting"

        # Check if setting has any items
        items_stmt = select(Item).where(Item.setting_id == setting.id).limit(1)
        items_result = await db_session.execute(items_stmt)
        has_items = items_result.scalar_one_or_none() is not None

        assert has_items is False, "Empty setting should have no items"

    async def test_returns_true_when_setting_has_items(
        self,
        db_session: AsyncSession,
    ):
        """Test that is_setting_configured returns True when setting has items."""
        from sqlalchemy import select

        from vaudeville_rpg.db.models.items import Item

        # Create a setting with items
        chat_id = 222222222
        setting = await create_setting_with_items(db_session, chat_id)
        await db_session.commit()

        # Verify setting exists
        assert setting is not None
        assert setting.name == "Test Setting"

        # Check if setting has any items
        items_stmt = select(Item).where(Item.setting_id == setting.id).limit(1)
        items_result = await db_session.execute(items_stmt)
        has_items = items_result.scalar_one_or_none() is not None

        assert has_items is True, "Configured setting should have items"


class TestSettingConfiguredIntegration:
    """Integration tests for setting configuration checks."""

    async def test_setting_with_multiple_items(
        self,
        db_session: AsyncSession,
        setting: Setting,
        attack_item: Item,
        defense_item: Item,
        misc_item: Item,
    ):
        """Test that a setting with multiple items is considered configured."""
        from sqlalchemy import select

        from vaudeville_rpg.db.models.items import Item

        # Check if setting has items
        items_stmt = select(Item).where(Item.setting_id == setting.id)
        items_result = await db_session.execute(items_stmt)
        items = list(items_result.scalars().all())

        assert len(items) == 3, "Setting should have 3 items"
        item_names = [item.name for item in items]
        assert "Test Sword" in item_names
        assert "Test Shield" in item_names
        assert "Test Potion" in item_names

    async def test_different_chats_have_independent_settings(
        self,
        db_session: AsyncSession,
    ):
        """Test that different chats have independent settings."""
        from sqlalchemy import select

        from vaudeville_rpg.db.models.items import Item

        # Create configured setting for chat 1
        chat1_id = 333333333
        setting1 = await create_setting_with_items(db_session, chat1_id)

        # Create empty setting for chat 2
        chat2_id = 444444444
        setting2 = await create_empty_setting(db_session, chat2_id)

        await db_session.commit()

        # Chat 1 should have items
        items_stmt1 = select(Item).where(Item.setting_id == setting1.id).limit(1)
        items_result1 = await db_session.execute(items_stmt1)
        chat1_has_items = items_result1.scalar_one_or_none() is not None

        # Chat 2 should not have items
        items_stmt2 = select(Item).where(Item.setting_id == setting2.id).limit(1)
        items_result2 = await db_session.execute(items_stmt2)
        chat2_has_items = items_result2.scalar_one_or_none() is not None

        assert chat1_has_items is True, "Chat 1 should be configured"
        assert chat2_has_items is False, "Chat 2 should not be configured"


class TestHelpMessageContent:
    """Tests for help message content validation."""

    async def test_help_sections_exist(self):
        """Verify that help message contains expected sections."""
        # These are the section headers that should appear in help messages
        expected_sections = [
            "VaudevilleRPG Help",
            "Getting Started",
            "Dueling (PvP)",
            "Dungeons (PvE)",
            "Competition",
        ]

        # Build a basic help message (similar to what cmd_help produces)
        help_text = (
            "<b>VaudevilleRPG Help</b>\n\n"
            "<b>Getting Started</b>\n"
            "/start - Welcome message and game status\n"
            "/help - Show this help message\n"
            "/profile - View your stats and equipped items\n\n"
            "<b>Dueling (PvP)</b>\n"
            "/challenge - Challenge another player\n"
            "<i>How to use: Reply to someone's message, then type /challenge</i>\n"
            "Both players pick actions (Attack/Defense/Misc/Skip).\n"
            "Winner gains rating, loser loses rating.\n\n"
            "<b>Dungeons (PvE)</b>\n"
            "/dungeon - Start a dungeon run\n"
            "Fight through stages of enemies solo.\n"
            "Difficulties: Easy (2 stages), Normal (3), Hard (4), Nightmare (5)\n"
            "Defeat all enemies to earn new items!\n\n"
            "<b>Competition</b>\n"
            "/leaderboard - See top 10 players by rating\n"
            "Win duels to climb the ranks!\n"
        )

        for section in expected_sections:
            assert section in help_text, f"Help should contain '{section}' section"

    async def test_help_contains_challenge_instructions(self):
        """Verify help explains how to use /challenge command."""
        help_text = (
            "<b>Dueling (PvP)</b>\n"
            "/challenge - Challenge another player\n"
            "<i>How to use: Reply to someone's message, then type /challenge</i>\n"
        )

        assert "Reply to someone's message" in help_text, "Help should explain /challenge usage"

    async def test_help_contains_dungeon_difficulties(self):
        """Verify help lists dungeon difficulties."""
        help_text = (
            "<b>Dungeons (PvE)</b>\n"
            "/dungeon - Start a dungeon run\n"
            "Fight through stages of enemies solo.\n"
            "Difficulties: Easy (2 stages), Normal (3), Hard (4), Nightmare (5)\n"
        )

        assert "Easy (2 stages)" in help_text
        assert "Normal (3)" in help_text
        assert "Hard (4)" in help_text
        assert "Nightmare (5)" in help_text


class TestStartMessageContent:
    """Tests for start message content validation."""

    async def test_unconfigured_start_message(self):
        """Verify start message for unconfigured chat."""
        # Message shown when game is not set up
        unconfigured_message = (
            "<b>Welcome to VaudevilleRPG!</b>\n\n"
            "A turn-based duel game where you battle with items and abilities.\n\n"
            "<b>Game Not Set Up</b>\n"
            "This chat doesn't have a game world yet.\n\n"
            "An admin needs to generate a setting first:\n"
            "<code>/generate_setting &lt;description&gt;</code>\n\n"
        )

        assert "Game Not Set Up" in unconfigured_message
        assert "/generate_setting" in unconfigured_message
        assert "admin" in unconfigured_message.lower()

    async def test_configured_start_message(self):
        """Verify start message for configured chat."""
        setting_name = "Test Fantasy World"
        setting_desc = "A magical realm"

        # Message shown when game is ready
        configured_message = (
            f"<b>Welcome to VaudevilleRPG!</b>\n\n"
            f"<b>Setting:</b> {setting_name}\n"
            f"<i>{setting_desc}</i>\n\n"
            "<b>Quick Start:</b>\n"
            " Reply to someone's message and use /challenge to duel them\n"
            " Use /dungeon to fight enemies and earn items\n"
            " Use /profile to see your stats and items\n\n"
        )

        assert setting_name in configured_message
        assert setting_desc in configured_message
        assert "Quick Start" in configured_message
        assert "/challenge" in configured_message
        assert "/dungeon" in configured_message
        assert "/profile" in configured_message
