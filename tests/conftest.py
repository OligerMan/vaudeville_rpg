"""Shared fixtures for integration tests."""

import pytest
from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from vaudeville_rpg.db.models import (
    Action,
    ActionType,
    AttributeCategory,
    AttributeDefinition,
    Base,
    Condition,
    ConditionPhase,
    ConditionType,
    Effect,
    EffectCategory,
    Item,
    ItemSlot,
    Player,
    Setting,
    TargetType,
)


@pytest.fixture
async def async_engine():
    """Create async SQLite in-memory engine for testing."""
    # Replace JSONB with JSON for SQLite compatibility
    # This must be done before creating the engine

    # Patch JSONB to use JSON for SQLite
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Enable foreign keys for SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def db_session(async_engine):
    """Create async session for testing with automatic rollback."""
    async_session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def setting(db_session: AsyncSession) -> Setting:
    """Create a test setting."""
    setting = Setting(
        telegram_chat_id=123456789,
        name="Test Fantasy Setting",
        description="A test world for integration testing",
        special_points_name="Mana",
        special_points_regen=5,
        max_generatable_attributes=3,
    )
    db_session.add(setting)
    await db_session.flush()
    return setting


@pytest.fixture
async def setting_with_attributes(db_session: AsyncSession, setting: Setting) -> Setting:
    """Create a setting with predefined attributes."""
    poison_attr = AttributeDefinition(
        setting_id=setting.id,
        name="poison",
        display_name="Poison",
        category=AttributeCategory.GENERATABLE,
        max_stacks=10,
    )
    armor_attr = AttributeDefinition(
        setting_id=setting.id,
        name="armor",
        display_name="Armor",
        category=AttributeCategory.GENERATABLE,
        max_stacks=20,
    )
    db_session.add_all([poison_attr, armor_attr])
    await db_session.flush()
    return setting


@pytest.fixture
async def player1(db_session: AsyncSession, setting: Setting) -> Player:
    """Create first test player."""
    player = Player(
        telegram_user_id=111111,
        setting_id=setting.id,
        display_name="TestPlayer1",
        max_hp=100,
        max_special_points=50,
        rating=1000,
    )
    db_session.add(player)
    await db_session.flush()
    return player


@pytest.fixture
async def player2(db_session: AsyncSession, setting: Setting) -> Player:
    """Create second test player."""
    player = Player(
        telegram_user_id=222222,
        setting_id=setting.id,
        display_name="TestPlayer2",
        max_hp=100,
        max_special_points=50,
        rating=1000,
    )
    db_session.add(player)
    await db_session.flush()
    return player


@pytest.fixture
async def bot_player(db_session: AsyncSession, setting: Setting) -> Player:
    """Create a bot player for PvE tests."""
    import random
    import time

    # Use unique negative ID for bot players
    unique_bot_id = -(int(time.time() * 1000000) + random.randint(0, 999999))

    player = Player(
        telegram_user_id=unique_bot_id,
        setting_id=setting.id,
        display_name="Test Enemy",
        max_hp=80,
        max_special_points=30,
        rating=1000,
        is_bot=True,
    )
    db_session.add(player)
    await db_session.flush()
    return player


@pytest.fixture
async def attack_item(db_session: AsyncSession, setting: Setting) -> Item:
    """Create a test attack item (sword)."""
    item = Item(
        setting_id=setting.id,
        name="Test Sword",
        description="A sharp blade for testing",
        slot=ItemSlot.ATTACK,
        rarity=1,
    )
    db_session.add(item)
    await db_session.flush()

    # Create attack action
    action = Action(
        name="sword_attack",
        action_type=ActionType.ATTACK,
        action_data={"value": 15},
    )
    db_session.add(action)
    await db_session.flush()

    # Create phase condition
    condition = Condition(
        name="sword_condition",
        condition_type=ConditionType.PHASE,
        condition_data={"phase": ConditionPhase.PRE_ATTACK.value},
    )
    db_session.add(condition)
    await db_session.flush()

    # Create effect linking item to action
    effect = Effect(
        setting_id=setting.id,
        name="sword_effect",
        description="Deals 15 damage",
        condition_id=condition.id,
        action_id=action.id,
        target=TargetType.ENEMY,
        category=EffectCategory.ITEM_EFFECT,
        item_id=item.id,
    )
    db_session.add(effect)
    await db_session.flush()

    return item


@pytest.fixture
async def defense_item(db_session: AsyncSession, setting: Setting) -> Item:
    """Create a test defense item (shield)."""
    item = Item(
        setting_id=setting.id,
        name="Test Shield",
        description="A sturdy shield for testing",
        slot=ItemSlot.DEFENSE,
        rarity=1,
    )
    db_session.add(item)
    await db_session.flush()

    # Create armor action
    action = Action(
        name="shield_block",
        action_type=ActionType.ADD_STACKS,
        action_data={"value": 3, "attribute": "armor"},
    )
    db_session.add(action)
    await db_session.flush()

    # Create phase condition
    condition = Condition(
        name="shield_condition",
        condition_type=ConditionType.PHASE,
        condition_data={"phase": ConditionPhase.PRE_DAMAGE.value},
    )
    db_session.add(condition)
    await db_session.flush()

    # Create effect
    effect = Effect(
        setting_id=setting.id,
        name="shield_effect",
        description="Adds 3 armor",
        condition_id=condition.id,
        action_id=action.id,
        target=TargetType.SELF,
        category=EffectCategory.ITEM_EFFECT,
        item_id=item.id,
    )
    db_session.add(effect)
    await db_session.flush()

    return item


@pytest.fixture
async def misc_item(db_session: AsyncSession, setting: Setting) -> Item:
    """Create a test misc item (healing potion)."""
    item = Item(
        setting_id=setting.id,
        name="Test Potion",
        description="A healing potion for testing",
        slot=ItemSlot.MISC,
        rarity=1,
    )
    db_session.add(item)
    await db_session.flush()

    # Create heal action
    action = Action(
        name="potion_heal",
        action_type=ActionType.HEAL,
        action_data={"value": 20},
    )
    db_session.add(action)
    await db_session.flush()

    # Create phase condition
    condition = Condition(
        name="potion_condition",
        condition_type=ConditionType.PHASE,
        condition_data={"phase": ConditionPhase.PRE_MOVE.value},
    )
    db_session.add(condition)
    await db_session.flush()

    # Create effect
    effect = Effect(
        setting_id=setting.id,
        name="potion_effect",
        description="Heals 20 HP",
        condition_id=condition.id,
        action_id=action.id,
        target=TargetType.SELF,
        category=EffectCategory.ITEM_EFFECT,
        item_id=item.id,
    )
    db_session.add(effect)
    await db_session.flush()

    return item


async def _create_attack_item(db_session: AsyncSession, setting: Setting, suffix: str) -> Item:
    """Helper to create a unique attack item."""
    item = Item(
        setting_id=setting.id,
        name=f"Test Sword {suffix}",
        description="A sharp blade for testing",
        slot=ItemSlot.ATTACK,
        rarity=1,
    )
    db_session.add(item)
    await db_session.flush()

    action = Action(
        name=f"sword_attack_{suffix}",
        action_type=ActionType.ATTACK,
        action_data={"value": 15},
    )
    db_session.add(action)
    await db_session.flush()

    condition = Condition(
        name=f"sword_condition_{suffix}",
        condition_type=ConditionType.PHASE,
        condition_data={"phase": ConditionPhase.PRE_ATTACK.value},
    )
    db_session.add(condition)
    await db_session.flush()

    effect = Effect(
        setting_id=setting.id,
        name=f"sword_effect_{suffix}",
        description="Deals 15 damage",
        condition_id=condition.id,
        action_id=action.id,
        target=TargetType.ENEMY,
        category=EffectCategory.ITEM_EFFECT,
        item_id=item.id,
    )
    db_session.add(effect)
    await db_session.flush()

    return item


async def _create_defense_item(db_session: AsyncSession, setting: Setting, suffix: str) -> Item:
    """Helper to create a unique defense item."""
    item = Item(
        setting_id=setting.id,
        name=f"Test Shield {suffix}",
        description="A sturdy shield for testing",
        slot=ItemSlot.DEFENSE,
        rarity=1,
    )
    db_session.add(item)
    await db_session.flush()

    action = Action(
        name=f"shield_block_{suffix}",
        action_type=ActionType.ADD_STACKS,
        action_data={"value": 3, "attribute": "armor"},
    )
    db_session.add(action)
    await db_session.flush()

    condition = Condition(
        name=f"shield_condition_{suffix}",
        condition_type=ConditionType.PHASE,
        condition_data={"phase": ConditionPhase.PRE_ATTACK.value},
    )
    db_session.add(condition)
    await db_session.flush()

    effect = Effect(
        setting_id=setting.id,
        name=f"shield_effect_{suffix}",
        description="Adds 3 armor",
        condition_id=condition.id,
        action_id=action.id,
        target=TargetType.SELF,
        category=EffectCategory.ITEM_EFFECT,
        item_id=item.id,
    )
    db_session.add(effect)
    await db_session.flush()

    return item


async def _create_misc_item(db_session: AsyncSession, setting: Setting, suffix: str) -> Item:
    """Helper to create a unique misc item."""
    item = Item(
        setting_id=setting.id,
        name=f"Test Potion {suffix}",
        description="A healing potion for testing",
        slot=ItemSlot.MISC,
        rarity=1,
    )
    db_session.add(item)
    await db_session.flush()

    action = Action(
        name=f"potion_heal_{suffix}",
        action_type=ActionType.HEAL,
        action_data={"value": 20},
    )
    db_session.add(action)
    await db_session.flush()

    condition = Condition(
        name=f"potion_condition_{suffix}",
        condition_type=ConditionType.PHASE,
        condition_data={"phase": ConditionPhase.PRE_MOVE.value},
    )
    db_session.add(condition)
    await db_session.flush()

    effect = Effect(
        setting_id=setting.id,
        name=f"potion_effect_{suffix}",
        description="Heals 20 HP",
        condition_id=condition.id,
        action_id=action.id,
        target=TargetType.SELF,
        category=EffectCategory.ITEM_EFFECT,
        item_id=item.id,
    )
    db_session.add(effect)
    await db_session.flush()

    return item


@pytest.fixture
async def equipped_player1(
    db_session: AsyncSession,
    player1: Player,
    setting: Setting,
) -> Player:
    """Player 1 with unique items equipped."""
    attack = await _create_attack_item(db_session, setting, "p1")
    defense = await _create_defense_item(db_session, setting, "p1")
    misc = await _create_misc_item(db_session, setting, "p1")

    player1.attack_item_id = attack.id
    player1.defense_item_id = defense.id
    player1.misc_item_id = misc.id
    await db_session.flush()
    return player1


@pytest.fixture
async def equipped_player2(
    db_session: AsyncSession,
    player2: Player,
    setting: Setting,
) -> Player:
    """Player 2 with unique items equipped."""
    attack = await _create_attack_item(db_session, setting, "p2")
    defense = await _create_defense_item(db_session, setting, "p2")
    misc = await _create_misc_item(db_session, setting, "p2")

    player2.attack_item_id = attack.id
    player2.defense_item_id = defense.id
    player2.misc_item_id = misc.id
    await db_session.flush()
    return player2


@pytest.fixture
async def poison_world_rule(db_session: AsyncSession, setting_with_attributes: Setting) -> Effect:
    """Create poison tick world rule."""
    setting = setting_with_attributes

    # Phase condition
    phase_condition = Condition(
        name="poison_tick_phase",
        condition_type=ConditionType.PHASE,
        condition_data={"phase": ConditionPhase.PRE_MOVE.value},
    )
    db_session.add(phase_condition)
    await db_session.flush()

    # Stacks condition
    stacks_condition = Condition(
        name="poison_tick_stacks",
        condition_type=ConditionType.HAS_STACKS,
        condition_data={"attribute": "poison", "min_count": 1},
    )
    db_session.add(stacks_condition)
    await db_session.flush()

    # AND condition
    and_condition = Condition(
        name="poison_tick_condition",
        condition_type=ConditionType.AND,
        condition_data={"condition_ids": [phase_condition.id, stacks_condition.id]},
    )
    db_session.add(and_condition)
    await db_session.flush()

    # Damage action
    action = Action(
        name="poison_damage",
        action_type=ActionType.DAMAGE,
        action_data={"value": 5, "per_stack": True},
    )
    db_session.add(action)
    await db_session.flush()

    # Effect
    effect = Effect(
        setting_id=setting.id,
        name="poison_tick",
        description="Poison deals 5 damage per stack each turn",
        condition_id=and_condition.id,
        action_id=action.id,
        target=TargetType.SELF,
        category=EffectCategory.WORLD_RULE,
    )
    db_session.add(effect)
    await db_session.flush()

    return effect
