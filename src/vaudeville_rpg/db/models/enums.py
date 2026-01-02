"""Enums for game models."""

from enum import Enum


class ItemSlot(str, Enum):
    """Item slot types - each player has one of each."""

    ATTACK = "attack"
    DEFENSE = "defense"
    MISC = "misc"


class BuffType(str, Enum):
    """Types of buffs that items can provide."""

    # Offensive buffs
    DAMAGE = "damage"  # Flat damage bonus
    CRIT_CHANCE = "crit_chance"  # Critical hit chance percentage
    ARMOR_PENETRATION = "armor_penetration"  # Ignores enemy armor

    # Defensive buffs
    ARMOR = "armor"  # Flat damage reduction
    MAX_HEALTH = "max_health"  # Bonus health points
    EVASION = "evasion"  # Chance to dodge attacks

    # Utility buffs
    HEALING_POWER = "healing_power"  # Bonus to healing effects
    ABILITY_POWER = "ability_power"  # General ability effectiveness


class AbilityType(str, Enum):
    """Types of abilities."""

    ATTACK = "attack"  # Offensive abilities (from attack items)
    DEFENSE = "defense"  # Defensive abilities (from defense items)
    MISC = "misc"  # Special abilities (from misc items)


class AbilityEffect(str, Enum):
    """Specific effects that abilities can have."""

    # Attack effects
    PHYSICAL_DAMAGE = "physical_damage"  # Direct physical damage
    MAGICAL_DAMAGE = "magical_damage"  # Direct magical damage
    BLEED = "bleed"  # Damage over time

    # Defense effects
    BLOCK = "block"  # Reduce incoming damage
    EVADE = "evade"  # Chance to completely avoid damage
    REFLECT = "reflect"  # Return portion of damage to attacker

    # Misc effects
    HEAL = "heal"  # Restore health
    COUNTERSPELL = "counterspell"  # Cancel enemy ability
    BUFF_SELF = "buff_self"  # Apply temporary buff to self
    DEBUFF_ENEMY = "debuff_enemy"  # Apply temporary debuff to enemy
