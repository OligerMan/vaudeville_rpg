"""Type definitions for the duel engine."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CombatState:
    """In-memory representation of a player's combat state during a duel.

    This is a mutable object that gets modified during turn resolution.
    Changes are persisted back to PlayerCombatState after the turn.
    """

    player_id: int
    participant_id: int
    current_hp: int
    max_hp: int
    current_special_points: int
    max_special_points: int
    attribute_stacks: dict[str, int] = field(default_factory=dict)

    # Temporary modifiers for the current turn (reset after turn)
    incoming_damage_reduction: int = 0
    pending_damage: int = 0

    def is_alive(self) -> bool:
        """Check if the player is still alive."""
        return self.current_hp > 0

    def get_stacks(self, attribute: str) -> int:
        """Get the number of stacks for an attribute."""
        return self.attribute_stacks.get(attribute, 0)

    def add_stacks(self, attribute: str, count: int, max_stacks: int | None = None) -> int:
        """Add stacks to an attribute, respecting max if set. Returns actual added."""
        current = self.get_stacks(attribute)
        new_value = current + count
        if max_stacks is not None:
            new_value = min(new_value, max_stacks)
        self.attribute_stacks[attribute] = max(0, new_value)
        return self.attribute_stacks[attribute] - current

    def remove_stacks(self, attribute: str, count: int) -> int:
        """Remove stacks from an attribute. Returns actual removed."""
        current = self.get_stacks(attribute)
        to_remove = min(current, count)
        self.attribute_stacks[attribute] = current - to_remove
        if self.attribute_stacks[attribute] == 0:
            del self.attribute_stacks[attribute]
        return to_remove

    def apply_damage(self, amount: int) -> int:
        """Apply damage after reductions. Returns actual damage dealt."""
        reduced = max(0, amount - self.incoming_damage_reduction)
        actual = min(self.current_hp, reduced)
        self.current_hp -= actual
        return actual

    def apply_heal(self, amount: int) -> int:
        """Apply healing. Returns actual HP restored."""
        actual = min(self.max_hp - self.current_hp, amount)
        self.current_hp += actual
        return actual

    def spend_resource(self, resource: str, amount: int) -> bool:
        """Spend HP or special points. Returns True if successful."""
        if resource == "hp":
            if self.current_hp > amount:  # Can't spend if it would kill
                self.current_hp -= amount
                return True
        elif resource == "special":
            if self.current_special_points >= amount:
                self.current_special_points -= amount
                return True
        return False

    def reset_turn_modifiers(self) -> None:
        """Reset temporary modifiers at the end of a turn."""
        self.incoming_damage_reduction = 0
        self.pending_damage = 0


@dataclass
class DuelContext:
    """Context for the current duel, shared across all processors."""

    duel_id: int
    setting_id: int
    current_turn: int
    states: dict[int, CombatState]  # participant_id -> CombatState

    def get_opponent_state(self, participant_id: int) -> CombatState:
        """Get the opponent's combat state."""
        for pid, state in self.states.items():
            if pid != participant_id:
                return state
        raise ValueError(f"No opponent found for participant {participant_id}")


@dataclass
class EffectResult:
    """Result of applying a single effect."""

    effect_name: str
    target_participant_id: int
    action_type: str
    value: int
    description: str


@dataclass
class TurnResult:
    """Result of processing a complete turn."""

    turn_number: int
    effects_applied: list[EffectResult] = field(default_factory=list)
    winner_participant_id: int | None = None
    is_duel_over: bool = False

    def add_effect(self, result: EffectResult) -> None:
        """Add an effect result to the turn."""
        self.effects_applied.append(result)


@dataclass
class ActionContext:
    """Context for executing an action."""

    source_participant_id: int
    source_state: CombatState
    target_state: CombatState
    action_data: dict[str, Any]
