"""Database models."""

from .base import Base, TimestampMixin
from .duels import Duel, DuelAction, DuelParticipant
from .dungeons import Dungeon, DungeonEnemy
from .effects import Action, Condition, Effect
from .enums import (
    ActionType,
    AttributeCategory,
    ConditionPhase,
    ConditionType,
    DuelActionType,
    DuelStatus,
    DungeonDifficulty,
    DungeonStatus,
    EffectCategory,
    ItemSlot,
    TargetType,
)
from .items import Item
from .players import Player, PlayerCombatState
from .settings import AttributeDefinition, Setting

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    # Enums
    "ActionType",
    "AttributeCategory",
    "ConditionPhase",
    "ConditionType",
    "DuelActionType",
    "DuelStatus",
    "DungeonDifficulty",
    "DungeonStatus",
    "EffectCategory",
    "ItemSlot",
    "TargetType",
    # Settings
    "Setting",
    "AttributeDefinition",
    # Effects
    "Condition",
    "Action",
    "Effect",
    # Items
    "Item",
    # Players
    "Player",
    "PlayerCombatState",
    # Duels
    "Duel",
    "DuelParticipant",
    "DuelAction",
    # Dungeons
    "Dungeon",
    "DungeonEnemy",
]
