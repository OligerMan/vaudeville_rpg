"""Effect processor - collects and executes effects by phase."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..db.models.enums import ConditionPhase, ConditionType, EffectCategory, TargetType
from .actions import ActionExecutor
from .conditions import ConditionEvaluator
from .types import ActionContext, CombatState, DuelContext, EffectResult

if TYPE_CHECKING:
    from .interrupts import DamageInterruptHandler
    from .logging import CombatLogger


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
    item_name: str | None = None  # Name of item that triggered this effect (if any)


class EffectProcessor:
    """Processes effects for a phase, collecting and executing them in order."""

    def __init__(
        self,
        logger: "CombatLogger | None" = None,
        interrupt_handler: "DamageInterruptHandler | None" = None,
    ) -> None:
        """Initialize the effect processor.

        Args:
            logger: Optional combat logger for event tracking
            interrupt_handler: Optional handler for damage interrupt processing.
                If provided, damage/attack actions will trigger PRE/POST_DAMAGE phases.
        """
        self.logger = logger
        self.interrupt_handler = interrupt_handler
        self.condition_evaluator = ConditionEvaluator()
        self.action_executor = ActionExecutor(interrupt_handler=interrupt_handler)

    def set_interrupt_handler(self, handler: "DamageInterruptHandler | None") -> None:
        """Set or update the interrupt handler.

        This is useful when the handler needs to be set after creation
        due to circular references (handler needs processor, processor needs handler).
        Can also be used to clear the handler by passing None.
        """
        self.interrupt_handler = handler
        self.action_executor.interrupt_handler = handler

    def process_phase(
        self,
        phase: ConditionPhase,
        effects: list[EffectData],
        context: DuelContext,
        all_conditions: dict[int, tuple[ConditionType, dict[str, Any]]] | None = None,
        turn_number: int = 0,
    ) -> list[EffectResult]:
        """Process all effects for a given phase.

        Args:
            phase: Current phase to process
            effects: All effects that might trigger
            context: Duel context with combat states
            all_conditions: Dict of all conditions for AND/OR resolution
            turn_number: Current turn number (for logging)

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
                if self.logger:
                    self.logger.log_effect_skipped(
                        turn_number=turn_number,
                        phase=phase,
                        participant_id=effect.owner_participant_id,
                        effect_name=effect.name,
                        reason="Owner state not found",
                    )
                continue

            # Check if the condition is met
            # For world rules, we check against the owner's state
            condition_met = self.condition_evaluator.evaluate(
                effect.condition_type,
                effect.condition_data,
                phase,
                owner_state,
                all_conditions,
            )

            # Log condition evaluation
            if self.logger:
                self.logger.log_effect_evaluated(
                    turn_number=turn_number,
                    phase=phase,
                    participant_id=effect.owner_participant_id,
                    effect_name=effect.name,
                    condition_type=effect.condition_type.value,
                    condition_data=effect.condition_data,
                    condition_result=condition_met,
                )

            if not condition_met:
                continue

            # Resolve target
            target_state = self._resolve_target(effect.target, effect.owner_participant_id, context)
            if target_state is None:
                if self.logger:
                    self.logger.log_effect_skipped(
                        turn_number=turn_number,
                        phase=phase,
                        participant_id=effect.owner_participant_id,
                        effect_name=effect.name,
                        reason="Target state not found",
                    )
                continue

            # Create action context
            action_context = ActionContext(
                source_participant_id=effect.owner_participant_id,
                source_state=owner_state,
                target_state=target_state,
                action_data=effect.action_data,
                item_name=effect.item_name,
                phase=phase,
            )

            # Execute the action
            from ..db.models.enums import ActionType

            try:
                action_type = ActionType(effect.action_type)
            except ValueError:
                if self.logger:
                    self.logger.log_effect_skipped(
                        turn_number=turn_number,
                        phase=phase,
                        participant_id=effect.owner_participant_id,
                        effect_name=effect.name,
                        reason=f"Invalid action type: {effect.action_type}",
                    )
                continue

            # Capture state before action for logging
            state_before_snapshot = None
            if self.logger:
                state_before_snapshot = self.logger.snapshot_state(target_state)

            result = self.action_executor.execute(
                action_type,
                effect.action_data,
                action_context,
                effect.name,
            )
            results.append(result)

            # Log action execution
            if self.logger and state_before_snapshot:
                # Create a temporary CombatState from the snapshot for logging
                from .types import CombatState

                state_before_obj = CombatState(
                    player_id=0,  # Not needed for logging
                    participant_id=state_before_snapshot.participant_id,
                    current_hp=state_before_snapshot.current_hp,
                    max_hp=state_before_snapshot.max_hp,
                    current_special_points=state_before_snapshot.current_special_points,
                    max_special_points=state_before_snapshot.max_special_points,
                    attribute_stacks=dict(state_before_snapshot.attribute_stacks),
                    incoming_damage_reduction=state_before_snapshot.incoming_damage_reduction,
                    pending_damage=state_before_snapshot.pending_damage,
                    display_name=state_before_snapshot.display_name,
                )
                self.logger.log_action_executed(
                    turn_number=turn_number,
                    phase=phase,
                    participant_id=effect.owner_participant_id,
                    target_participant_id=target_state.participant_id,
                    effect_name=effect.name,
                    action_type=action_type.value,
                    action_data=effect.action_data,
                    value=result.value,
                    description=result.description,
                    state_before=state_before_obj,
                    state_after=target_state,
                )

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
