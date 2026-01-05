"""Action executor - applies actions to combat state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..db.models.enums import ActionType
from .types import ActionContext, EffectResult

if TYPE_CHECKING:
    from .interrupts import DamageInterruptHandler


class ActionExecutor:
    """Executes actions and modifies combat state."""

    def __init__(self, interrupt_handler: "DamageInterruptHandler | None" = None) -> None:
        """Initialize the action executor.

        Args:
            interrupt_handler: Optional handler for damage interrupt processing.
                If provided, damage/attack actions will go through PRE/POST_DAMAGE
                interrupt phases.
        """
        self.interrupt_handler = interrupt_handler

    def execute(
        self,
        action_type: ActionType,
        action_data: dict[str, Any],
        context: ActionContext,
        effect_name: str,
    ) -> EffectResult:
        """Execute an action and return the result.

        Args:
            action_type: Type of action to execute
            action_data: Data for the action (value, attribute, etc.)
            context: Context with source/target states
            effect_name: Name of the effect triggering this action

        Returns:
            EffectResult describing what happened
        """
        match action_type:
            case ActionType.DAMAGE:
                return self._execute_damage(action_data, context, effect_name)
            case ActionType.ATTACK:
                return self._execute_attack(action_data, context, effect_name)
            case ActionType.HEAL:
                return self._execute_heal(action_data, context, effect_name)
            case ActionType.ADD_STACKS:
                return self._execute_add_stacks(action_data, context, effect_name)
            case ActionType.REMOVE_STACKS:
                return self._execute_remove_stacks(action_data, context, effect_name)
            case ActionType.REDUCE_INCOMING_DAMAGE:
                return self._execute_reduce_incoming_damage(action_data, context, effect_name)
            case ActionType.SPEND:
                return self._execute_spend(action_data, context, effect_name)
            case ActionType.MODIFY_MAX:
                return self._execute_modify_max(action_data, context, effect_name)
            case ActionType.MODIFY_CURRENT_MAX:
                return self._execute_modify_current_max(action_data, context, effect_name)
            case _:
                return EffectResult(
                    effect_name=effect_name,
                    target_participant_id=context.target_state.participant_id,
                    action_type=action_type.value,
                    value=0,
                    description=f"Unknown action type: {action_type}",
                )

    def _execute_damage(
        self,
        action_data: dict[str, Any],
        context: ActionContext,
        effect_name: str,
    ) -> EffectResult:
        """Apply direct damage (bypasses crit/miss).

        If an interrupt handler is set, damage goes through PRE/POST_DAMAGE phases.
        """
        value = action_data.get("value", 0)

        if self.interrupt_handler:
            # Route through interrupt system
            result = self.interrupt_handler.apply_damage(
                target_state=context.target_state,
                damage=value,
                effect_name=effect_name,
                source_participant_id=context.source_participant_id,
            )
            actual = result.actual_damage
        else:
            # Direct damage (no interrupt processing)
            actual = context.target_state.apply_damage(value)

        return EffectResult(
            effect_name=effect_name,
            target_participant_id=context.target_state.participant_id,
            action_type=ActionType.DAMAGE.value,
            value=actual,
            description=f"Dealt {actual} damage",
        )

    def _execute_attack(
        self,
        action_data: dict[str, Any],
        context: ActionContext,
        effect_name: str,
    ) -> EffectResult:
        """Execute an attack (can crit/miss in future).

        For now, attacks are similar to damage but could later include:
        - Crit chance calculation
        - Miss chance calculation
        - Bonus damage from buffs

        If an interrupt handler is set, damage goes through PRE/POST_DAMAGE phases.
        """
        value = action_data.get("value", 0)
        # TODO: Add crit/miss mechanics later

        if self.interrupt_handler:
            # Route through interrupt system
            result = self.interrupt_handler.apply_damage(
                target_state=context.target_state,
                damage=value,
                effect_name=effect_name,
                source_participant_id=context.source_participant_id,
            )
            actual = result.actual_damage
        else:
            # Direct damage (no interrupt processing)
            actual = context.target_state.apply_damage(value)

        return EffectResult(
            effect_name=effect_name,
            target_participant_id=context.target_state.participant_id,
            action_type=ActionType.ATTACK.value,
            value=actual,
            description=f"Attack dealt {actual} damage",
        )

    def _execute_heal(
        self,
        action_data: dict[str, Any],
        context: ActionContext,
        effect_name: str,
    ) -> EffectResult:
        """Heal the target."""
        value = action_data.get("value", 0)
        actual = context.target_state.apply_heal(value)
        return EffectResult(
            effect_name=effect_name,
            target_participant_id=context.target_state.participant_id,
            action_type=ActionType.HEAL.value,
            value=actual,
            description=f"Healed {actual} HP",
        )

    def _execute_add_stacks(
        self,
        action_data: dict[str, Any],
        context: ActionContext,
        effect_name: str,
    ) -> EffectResult:
        """Add stacks of an attribute to the target."""
        attribute = action_data.get("attribute", "")
        value = action_data.get("value", 0)
        max_stacks = action_data.get("max_stacks")  # Optional cap
        actual = context.target_state.add_stacks(attribute, value, max_stacks)
        return EffectResult(
            effect_name=effect_name,
            target_participant_id=context.target_state.participant_id,
            action_type=ActionType.ADD_STACKS.value,
            value=actual,
            description=f"Added {actual} {attribute} stacks",
        )

    def _execute_remove_stacks(
        self,
        action_data: dict[str, Any],
        context: ActionContext,
        effect_name: str,
    ) -> EffectResult:
        """Remove stacks of an attribute from the target."""
        attribute = action_data.get("attribute", "")
        value = action_data.get("value", 0)
        actual = context.target_state.remove_stacks(attribute, value)
        return EffectResult(
            effect_name=effect_name,
            target_participant_id=context.target_state.participant_id,
            action_type=ActionType.REMOVE_STACKS.value,
            value=actual,
            description=f"Removed {actual} {attribute} stacks",
        )

    def _execute_reduce_incoming_damage(
        self,
        action_data: dict[str, Any],
        context: ActionContext,
        effect_name: str,
    ) -> EffectResult:
        """Add damage reduction for the current turn."""
        value = action_data.get("value", 0)
        # Per-stack reduction if specified
        per_stack = action_data.get("per_stack")
        if per_stack:
            attribute = action_data.get("attribute", "")
            stacks = context.target_state.get_stacks(attribute)
            value = value * stacks

        context.target_state.incoming_damage_reduction += value
        return EffectResult(
            effect_name=effect_name,
            target_participant_id=context.target_state.participant_id,
            action_type=ActionType.REDUCE_INCOMING_DAMAGE.value,
            value=value,
            description=f"Reduced incoming damage by {value}",
        )

    def _execute_spend(
        self,
        action_data: dict[str, Any],
        context: ActionContext,
        effect_name: str,
    ) -> EffectResult:
        """Spend HP or special points as a cost."""
        resource = action_data.get("resource", "special")
        value = action_data.get("value", 0)
        success = context.source_state.spend_resource(resource, value)
        return EffectResult(
            effect_name=effect_name,
            target_participant_id=context.source_state.participant_id,
            action_type=ActionType.SPEND.value,
            value=value if success else 0,
            description=f"Spent {value} {resource}" if success else f"Failed to spend {value} {resource}",
        )

    def _execute_modify_max(
        self,
        action_data: dict[str, Any],
        context: ActionContext,
        effect_name: str,
    ) -> EffectResult:
        """Modify the max stacks for an attribute (permanent for duel)."""
        # This would require tracking max_stacks per attribute in CombatState
        # For now, return a placeholder
        attribute = action_data.get("attribute", "")
        value = action_data.get("value", 0)
        return EffectResult(
            effect_name=effect_name,
            target_participant_id=context.target_state.participant_id,
            action_type=ActionType.MODIFY_MAX.value,
            value=value,
            description=f"Modified {attribute} max stacks by {value}",
        )

    def _execute_modify_current_max(
        self,
        action_data: dict[str, Any],
        context: ActionContext,
        effect_name: str,
    ) -> EffectResult:
        """Modify max HP or special points for the current combat."""
        resource = action_data.get("resource", "hp")
        value = action_data.get("value", 0)

        if resource == "hp":
            context.target_state.max_hp += value
            # If increasing max, optionally heal the difference
            if value > 0:
                context.target_state.current_hp = min(
                    context.target_state.current_hp + value,
                    context.target_state.max_hp,
                )
        elif resource == "special":
            context.target_state.max_special_points += value
            if value > 0:
                context.target_state.current_special_points = min(
                    context.target_state.current_special_points + value,
                    context.target_state.max_special_points,
                )

        return EffectResult(
            effect_name=effect_name,
            target_participant_id=context.target_state.participant_id,
            action_type=ActionType.MODIFY_CURRENT_MAX.value,
            value=value,
            description=f"Modified max {resource} by {value}",
        )
