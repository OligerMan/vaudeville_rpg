"""Damage interrupt handler - processes PRE_DAMAGE/POST_DAMAGE effects on damage events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..db.models.enums import ConditionPhase
from .types import CombatState, DuelContext, EffectResult

if TYPE_CHECKING:
    from .effects import EffectData
    from .logging import CombatLogger


@dataclass
class DamageEvent:
    """Represents a damage event with its source and target."""

    source_participant_id: int
    target_participant_id: int
    base_damage: int
    effect_name: str
    is_attack: bool = False  # True if this is an attack (can crit/miss)


@dataclass
class DamageResult:
    """Result of processing a damage event through the interrupt system."""

    actual_damage: int
    effect_results: list[EffectResult]
    target_died: bool = False


class DamageInterruptHandler:
    """Handles damage events with PRE_DAMAGE/POST_DAMAGE interrupt processing.

    When damage is about to be applied:
    1. If interrupts are blocked (we're already in an interrupt), apply damage directly
    2. Otherwise:
       a. Block interrupts
       b. Process PRE_DAMAGE effects (can add reduction, heal, or deal MORE damage)
       c. Apply the original damage (with any reductions)
       d. Process POST_DAMAGE effects (can deal revenge damage, etc.)
       e. Unblock interrupts

    Any damage that occurs during PRE_DAMAGE or POST_DAMAGE is applied directly
    without triggering further interrupts (the flag prevents infinite loops).
    """

    def __init__(
        self,
        context: DuelContext,
        all_effects: dict[int, list["EffectData"]],
        all_conditions: dict[int, tuple[Any, dict[str, Any]]] | None = None,
        logger: "CombatLogger | None" = None,
    ) -> None:
        """Initialize the interrupt handler.

        Args:
            context: The duel context (contains states and interrupt flag)
            all_effects: All effects for each participant
            all_conditions: All conditions for AND/OR resolution
            logger: Optional combat logger
        """
        self.context = context
        self.all_effects = all_effects
        self.all_conditions = all_conditions
        self.logger = logger
        self._effect_processor: Any = None  # Set later to avoid circular import

    def set_effect_processor(self, processor: Any) -> None:
        """Set the effect processor for processing interrupt phases."""
        self._effect_processor = processor

    def apply_damage(
        self,
        target_state: CombatState,
        damage: int,
        effect_name: str,
        source_participant_id: int | None = None,
    ) -> DamageResult:
        """Apply damage to a target, triggering PRE/POST_DAMAGE interrupts if not blocked.

        Args:
            target_state: The combat state of the target
            damage: Amount of damage to apply
            effect_name: Name of the effect causing the damage
            source_participant_id: Who is dealing the damage (for targeting)

        Returns:
            DamageResult with actual damage dealt and any effect results
        """
        all_results: list[EffectResult] = []

        # If interrupts are blocked, apply damage directly
        if self.context.damage_interrupts_blocked:
            actual = self._apply_damage_direct(target_state, damage)
            return DamageResult(
                actual_damage=actual,
                effect_results=[],
                target_died=not target_state.is_alive(),
            )

        # Block interrupts to prevent recursion
        self.context.damage_interrupts_blocked = True

        try:
            # Log interrupt start
            if self.logger:
                self.logger.log_damage_interrupt_start(
                    turn_number=self.context.current_turn,
                    target_participant_id=target_state.participant_id,
                    base_damage=damage,
                    effect_name=effect_name,
                )

            # Process PRE_DAMAGE effects
            if self._effect_processor:
                pre_damage_results = self._process_interrupt_phase(
                    ConditionPhase.PRE_DAMAGE,
                    target_state.participant_id,
                )
                all_results.extend(pre_damage_results)

            # Apply the actual damage (with any reductions from PRE_DAMAGE)
            actual = self._apply_damage_direct(target_state, damage)

            # Log damage application
            if self.logger:
                self.logger.log_damage_applied(
                    turn_number=self.context.current_turn,
                    target_participant_id=target_state.participant_id,
                    base_damage=damage,
                    actual_damage=actual,
                    reduction=target_state.incoming_damage_reduction,
                )

            # Process POST_DAMAGE effects
            if self._effect_processor:
                post_damage_results = self._process_interrupt_phase(
                    ConditionPhase.POST_DAMAGE,
                    target_state.participant_id,
                )
                all_results.extend(post_damage_results)

            # Log interrupt end
            if self.logger:
                self.logger.log_damage_interrupt_end(
                    turn_number=self.context.current_turn,
                    target_participant_id=target_state.participant_id,
                )

            return DamageResult(
                actual_damage=actual,
                effect_results=all_results,
                target_died=not target_state.is_alive(),
            )

        finally:
            # Always unblock interrupts when done
            self.context.damage_interrupts_blocked = False

    def _apply_damage_direct(self, target_state: CombatState, damage: int) -> int:
        """Apply damage directly to a target, respecting damage reduction.

        Args:
            target_state: The combat state of the target
            damage: Amount of damage to apply

        Returns:
            Actual damage dealt after reductions
        """
        return target_state.apply_damage(damage)

    def _process_interrupt_phase(
        self,
        phase: ConditionPhase,
        damage_target_participant_id: int,
    ) -> list[EffectResult]:
        """Process effects for an interrupt phase (PRE_DAMAGE or POST_DAMAGE).

        Only effects owned by the damage target are processed. This ensures that
        when Player A damages Player B, only Player B's PRE_DAMAGE/POST_DAMAGE
        effects trigger (e.g., Player B's armor reduces damage to Player B).

        Args:
            phase: PRE_DAMAGE or POST_DAMAGE
            damage_target_participant_id: Who is receiving damage

        Returns:
            List of effect results from this phase
        """
        if not self._effect_processor:
            return []

        # Only include effects from the damage target (the player receiving damage)
        target_effects = list(self.all_effects.get(damage_target_participant_id, []))

        # Process the phase
        return self._effect_processor.process_phase(
            phase=phase,
            effects=target_effects,
            context=self.context,
            all_conditions=self.all_conditions,
            turn_number=self.context.current_turn,
        )
