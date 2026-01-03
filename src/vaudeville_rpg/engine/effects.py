"""Effect processor - collects and executes effects by phase."""

from dataclasses import dataclass
from typing import Any

from ..db.models.enums import ConditionPhase, ConditionType, EffectCategory, TargetType
from .actions import ActionExecutor
from .conditions import ConditionEvaluator
from .types import ActionContext, CombatState, DuelContext, EffectResult


@dataclass
class EffectData:
    """Data for a single effect to be processed."""

    id: int
    name: str
    condition_type: ConditionType
    condition_data: dict[str, Any]
    target: TargetType
    category: EffectCategory
    action_type: str  # ActionType value
    action_data: dict[str, Any]
    owner_participant_id: int  # Who owns this effect (for SELF/ENEMY resolution)


class EffectProcessor:
    """Processes effects for a phase, collecting and executing them in order."""

    def __init__(self) -> None:
        self.condition_evaluator = ConditionEvaluator()
        self.action_executor = ActionExecutor()

    def process_phase(
        self,
        phase: ConditionPhase,
        effects: list[EffectData],
        context: DuelContext,
        all_conditions: dict[int, tuple[ConditionType, dict[str, Any]]] | None = None,
    ) -> list[EffectResult]:
        """Process all effects for a given phase.

        Args:
            phase: Current phase to process
            effects: All effects that might trigger
            context: Duel context with combat states
            all_conditions: Dict of all conditions for AND/OR resolution

        Returns:
            List of effect results from this phase
        """
        results: list[EffectResult] = []

        # Sort effects alphabetically by name for deterministic ordering
        sorted_effects = sorted(effects, key=lambda e: e.name)

        for effect in sorted_effects:
            # Get the combat state of the effect owner
            owner_state = context.states.get(effect.owner_participant_id)
            if owner_state is None:
                continue

            # Check if the condition is met
            # For world rules, we check against the owner's state
            if not self.condition_evaluator.evaluate(
                effect.condition_type,
                effect.condition_data,
                phase,
                owner_state,
                all_conditions,
            ):
                continue

            # Resolve target
            target_state = self._resolve_target(effect.target, effect.owner_participant_id, context)
            if target_state is None:
                continue

            # Create action context
            action_context = ActionContext(
                source_participant_id=effect.owner_participant_id,
                source_state=owner_state,
                target_state=target_state,
                action_data=effect.action_data,
            )

            # Execute the action
            from ..db.models.enums import ActionType

            try:
                action_type = ActionType(effect.action_type)
            except ValueError:
                continue

            result = self.action_executor.execute(
                action_type,
                effect.action_data,
                action_context,
                effect.name,
            )
            results.append(result)

        return results

    def _resolve_target(
        self,
        target: TargetType,
        owner_participant_id: int,
        context: DuelContext,
    ) -> CombatState | None:
        """Resolve the target of an effect.

        Args:
            target: SELF or ENEMY
            owner_participant_id: Who owns the effect
            context: Duel context

        Returns:
            The target's combat state, or None if not found
        """
        if target == TargetType.SELF:
            return context.states.get(owner_participant_id)
        elif target == TargetType.ENEMY:
            # Find the opponent
            for pid, state in context.states.items():
                if pid != owner_participant_id:
                    return state
        return None

    def collect_effects_for_participant(
        self,
        participant_id: int,
        world_rules: list[EffectData],
        item_effects: list[EffectData],
    ) -> list[EffectData]:
        """Collect all effects that apply to a participant.

        Args:
            participant_id: The participant to collect effects for
            world_rules: World rules that apply to everyone
            item_effects: Effects from the participant's equipped items

        Returns:
            Combined list of effects with owner set
        """
        effects: list[EffectData] = []

        # World rules apply to everyone, but we process them per-participant
        for rule in world_rules:
            effects.append(
                EffectData(
                    id=rule.id,
                    name=rule.name,
                    condition_type=rule.condition_type,
                    condition_data=rule.condition_data,
                    target=rule.target,
                    category=rule.category,
                    action_type=rule.action_type,
                    action_data=rule.action_data,
                    owner_participant_id=participant_id,
                )
            )

        # Item effects belong to the participant
        for item_effect in item_effects:
            if item_effect.owner_participant_id == participant_id:
                effects.append(item_effect)

        return effects
