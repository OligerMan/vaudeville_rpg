"""Enums for game models."""

from enum import Enum


class ItemSlot(str, Enum):
    """Item slot types - each player has one of each."""

    ATTACK = "attack"
    DEFENSE = "defense"
    MISC = "misc"


class AttributeCategory(str, Enum):
    """Categories of attributes."""

    CORE_HP = "core_hp"  # HP - universal, 0 = death
    CORE_SPECIAL = "core_special"  # Special points (mana/energy/etc.)
    GENERATABLE = "generatable"  # Setting-specific stack-based attributes


class ActionType(str, Enum):
    """Types of actions that effects can perform."""

    # HP interactions
    DAMAGE = "damage"  # Reduce HP (bypasses crit/miss)
    ATTACK = "attack"  # Player-initiated damage (can crit/miss)
    HEAL = "heal"  # Restore HP

    # Stack interactions
    ADD_STACKS = "add_stacks"  # Add stacks to an attribute
    REMOVE_STACKS = "remove_stacks"  # Remove stacks from an attribute

    # Max value modifications
    MODIFY_MAX = "modify_max"  # Change attribute's max stacks
    MODIFY_CURRENT_MAX = "modify_current_max"  # Change HP/Special max for combat

    # Cost/price
    SPEND = "spend"  # Spend HP or Special Points as cost

    # Damage modification (for armor-like effects)
    REDUCE_INCOMING_DAMAGE = "reduce_incoming_damage"  # Reduce damage before it's applied


class ConditionPhase(str, Enum):
    """Phases at which conditions can trigger."""

    PRE_ATTACK = "pre_attack"  # Before attack is resolved
    POST_ATTACK = "post_attack"  # After attack is resolved
    PRE_DAMAGE = "pre_damage"  # Before damage is applied
    POST_DAMAGE = "post_damage"  # After damage is applied
    PRE_MOVE = "pre_move"  # Before turn actions resolve
    POST_MOVE = "post_move"  # After turn actions resolve


class ConditionType(str, Enum):
    """Types of conditions."""

    PHASE = "phase"  # Triggers at a specific phase
    HAS_STACKS = "has_stacks"  # Requires stacks of an attribute
    AND = "and"  # All sub-conditions must be true
    OR = "or"  # At least one sub-condition must be true


class TargetType(str, Enum):
    """Who the effect targets."""

    SELF = "self"  # Effect applies to the owner/triggering player
    ENEMY = "enemy"  # Effect applies to the opponent


class EffectCategory(str, Enum):
    """Category of the effect - determines where it's defined."""

    ITEM_EFFECT = "item_effect"  # Effect comes from an equipped item
    WORLD_RULE = "world_rule"  # Effect is a setting-level rule


class DuelStatus(str, Enum):
    """Status of a duel."""

    PENDING = "pending"  # Waiting for acceptance (PvP) or start (PvE)
    IN_PROGRESS = "in_progress"  # Both players joined, turns being processed
    COMPLETED = "completed"  # One player won (HP reached 0)
    CANCELLED = "cancelled"  # Duel was cancelled before completion


class DuelActionType(str, Enum):
    """Type of action a player can take in a duel turn."""

    ATTACK = "attack"  # Use attack item ability
    DEFENSE = "defense"  # Use defense item ability
    MISC = "misc"  # Use misc item ability
    SKIP = "skip"  # Do nothing this turn