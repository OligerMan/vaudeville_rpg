"""Condition evaluator - checks if effect conditions are met."""

from typing import Any

from ..db.models.enums import ConditionPhase, ConditionType
from .types import CombatState


class ConditionEvaluator:
    """Evaluates conditions to determine if effects should trigger."""

    def evaluate(
        self,
        condition_type: ConditionType,
        condition_data: dict[str, Any],
        current_phase: ConditionPhase,
        state: CombatState,
        all_conditions: dict[int, tuple[ConditionType, dict[str, Any]]] | None = None,
    ) -> bool:
        """Evaluate a condition.

        Args:
            condition_type: Type of condition to evaluate
            condition_data: Data for the condition
            current_phase: Current phase of the turn
            state: Combat state of the player being checked
            all_conditions: Dict of condition_id -> (type, data) for resolving AND/OR

        Returns:
            True if the condition is met, False otherwise
        """
        match condition_type:
            case ConditionType.PHASE:
                return self._evaluate_phase(condition_data, current_phase)
            case ConditionType.HAS_STACKS:
                return self._evaluate_has_stacks(condition_data, state)
            case ConditionType.AND:
                return self._evaluate_and(condition_data, current_phase, state, all_conditions)
            case ConditionType.OR:
                return self._evaluate_or(condition_data, current_phase, state, all_conditions)
            case _:
                return False

    def _evaluate_phase(
        self,
        condition_data: dict[str, Any],
        current_phase: ConditionPhase,
    ) -> bool:
        """Check if current phase matches the condition's phase."""
        required_phase = condition_data.get("phase")
        if required_phase is None:
            return False
        return current_phase.value == required_phase

    def _evaluate_has_stacks(
        self,
        condition_data: dict[str, Any],
        state: CombatState,
    ) -> bool:
        """Check if player has minimum stacks of an attribute."""
        attribute = condition_data.get("attribute")
        min_count = condition_data.get("min_count", 1)
        if attribute is None:
            return False
        return state.get_stacks(attribute) >= min_count

    def _evaluate_and(
        self,
        condition_data: dict[str, Any],
        current_phase: ConditionPhase,
        state: CombatState,
        all_conditions: dict[int, tuple[ConditionType, dict[str, Any]]] | None,
    ) -> bool:
        """Evaluate AND composition - all sub-conditions must be true."""
        condition_ids = condition_data.get("condition_ids", [])
        if not condition_ids or all_conditions is None:
            return False

        for cond_id in condition_ids:
            if cond_id not in all_conditions:
                return False
            cond_type, cond_data = all_conditions[cond_id]
            if not self.evaluate(cond_type, cond_data, current_phase, state, all_conditions):
                return False
        return True

    def _evaluate_or(
        self,
        condition_data: dict[str, Any],
        current_phase: ConditionPhase,
        state: CombatState,
        all_conditions: dict[int, tuple[ConditionType, dict[str, Any]]] | None,
    ) -> bool:
        """Evaluate OR composition - at least one sub-condition must be true."""
        condition_ids = condition_data.get("condition_ids", [])
        if not condition_ids or all_conditions is None:
            return False

        for cond_id in condition_ids:
            if cond_id not in all_conditions:
                continue
            cond_type, cond_data = all_conditions[cond_id]
            if self.evaluate(cond_type, cond_data, current_phase, state, all_conditions):
                return True
        return False
