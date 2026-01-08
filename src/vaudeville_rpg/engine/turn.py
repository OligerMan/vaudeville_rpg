"""Turn resolver - processes both players' actions simultaneously."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..db.models.enums import ConditionPhase, ConditionType, DuelActionType, ItemSlot
from .effects import EffectData, EffectProcessor
from .interrupts import DamageInterruptHandler
from .types import DuelContext, EffectResult, TurnResult

if TYPE_CHECKING:
    from .logging import CombatLogger


@dataclass
class ParticipantAction:
    """Action submitted by a participant for a turn."""

    participant_id: int
    action_type: DuelActionType
    item_id: int | None = None


@dataclass
class ItemData:
    """Data for an equipped item."""

    id: int
    name: str
    slot: ItemSlot
    effects: list[EffectData]


@dataclass
class PreMoveResult:
    """Result of processing the PRE_MOVE phase.

    This is returned to allow players to see the state after PRE_MOVE
    effects (like poison damage) before choosing their actions.
    """

    turn_number: int
    effects_applied: list[EffectResult] = field(default_factory=list)
    winner_participant_id: int | None = None
    is_duel_over: bool = False

    # Stored context for combat phase
    _all_effects: dict[int, list[EffectData]] | None = field(default=None, repr=False)
    _all_conditions: dict[int, tuple[ConditionType, dict[str, Any]]] | None = field(default=None, repr=False)

    def add_effect(self, result: EffectResult) -> None:
        """Add an effect result."""
        self.effects_applied.append(result)


class TurnResolver:
    """Resolves a complete turn with both players' actions.

    The turn can be resolved in two ways:
    1. All at once: resolve_turn() - processes entire turn with actions
    2. Split: resolve_pre_move() -> resolve_combat() - allows players to see
       PRE_MOVE results before choosing actions

    The split approach enables interactive gameplay where players can see
    effects like poison damage before deciding their action.
    """

    def __init__(self, logger: "CombatLogger | None" = None) -> None:
        self.logger = logger
        self.effect_processor = EffectProcessor(logger=logger)

    def resolve_pre_move(
        self,
        context: DuelContext,
        world_rules: list[EffectData],
        all_conditions: dict[int, tuple[ConditionType, dict[str, Any]]] | None = None,
    ) -> PreMoveResult:
        """Process only the PRE_MOVE phase of a turn.

        This allows players to see the state after PRE_MOVE effects (like
        poison damage, buffs) before choosing their actions. Returns a
        PreMoveResult that contains the state and can be passed to
        resolve_combat() later.

        Args:
            context: Duel context with combat states
            world_rules: World rule effects
            all_conditions: All conditions for AND/OR resolution

        Returns:
            PreMoveResult with effects applied and state for combat phase
        """
        result = PreMoveResult(turn_number=context.current_turn)

        # Log turn start
        if self.logger:
            self.logger.log_turn_start(context.current_turn, context.states)

        # Collect world rule effects for each participant (no item effects yet)
        all_effects: dict[int, list[EffectData]] = {}
        for participant_id in context.states:
            all_effects[participant_id] = self.effect_processor.collect_effects_for_participant(participant_id, world_rules, [])

        # Create the damage interrupt handler
        interrupt_handler = DamageInterruptHandler(
            context=context,
            all_effects=all_effects,
            all_conditions=all_conditions,
            logger=self.logger,
        )
        interrupt_handler.set_effect_processor(self.effect_processor)
        self.effect_processor.set_interrupt_handler(interrupt_handler)

        try:
            # Process PRE_MOVE phase
            self._process_phase_for_all(ConditionPhase.PRE_MOVE, all_effects, context, all_conditions, result)

            # Check for deaths after PRE_MOVE
            winner = self._check_winner(context)
            if winner is not None:
                result.winner_participant_id = winner
                result.is_duel_over = True
                if self.logger:
                    self.logger.log_winner(context.current_turn, winner)
                    self.logger.log_turn_end(context.current_turn, context.states)

            # Store context for combat phase
            result._all_effects = all_effects
            result._all_conditions = all_conditions

            return result

        finally:
            self.effect_processor.set_interrupt_handler(None)

    def resolve_combat(
        self,
        context: DuelContext,
        actions: list[ParticipantAction],
        world_rules: list[EffectData],
        participant_items: dict[int, dict[ItemSlot, ItemData]],
        all_conditions: dict[int, tuple[ConditionType, dict[str, Any]]] | None = None,
        pre_move_result: PreMoveResult | None = None,
    ) -> TurnResult:
        """Process the combat phase of a turn (PRE_ATTACK through POST_MOVE).

        This should be called after resolve_pre_move() once both players have
        submitted their actions. It processes item effects and combat.

        Args:
            context: Duel context with combat states
            actions: Actions from each participant
            world_rules: World rule effects
            participant_items: Equipped items per participant
            all_conditions: All conditions for AND/OR resolution
            pre_move_result: Result from resolve_pre_move() if called separately

        Returns:
            TurnResult with effects applied and winner if any
        """
        result = TurnResult(turn_number=context.current_turn)

        # If we have a pre_move_result, copy its effects
        if pre_move_result:
            result.effects_applied.extend(pre_move_result.effects_applied)
            if pre_move_result.is_duel_over:
                result.winner_participant_id = pre_move_result.winner_participant_id
                result.is_duel_over = True
                return result

        # Build action lookup
        action_map = {a.participant_id: a for a in actions}

        # Collect all effects for each participant (including item effects)
        all_effects: dict[int, list[EffectData]] = {}
        for participant_id in context.states:
            item_effects = self._get_active_item_effects(
                participant_id,
                action_map.get(participant_id),
                participant_items.get(participant_id, {}),
            )
            all_effects[participant_id] = self.effect_processor.collect_effects_for_participant(participant_id, world_rules, item_effects)

        # Create the damage interrupt handler
        interrupt_handler = DamageInterruptHandler(
            context=context,
            all_effects=all_effects,
            all_conditions=all_conditions,
            logger=self.logger,
        )
        interrupt_handler.set_effect_processor(self.effect_processor)
        self.effect_processor.set_interrupt_handler(interrupt_handler)

        try:
            # Phase 2: Action resolution (PRE_ATTACK → attacks → POST_ATTACK)
            self._process_phase_for_all(ConditionPhase.PRE_ATTACK, all_effects, context, all_conditions, result)
            self._process_phase_for_all(ConditionPhase.POST_ATTACK, all_effects, context, all_conditions, result)

            # Check for deaths after attacks
            winner = self._check_winner(context)
            if winner is not None:
                result.winner_participant_id = winner
                result.is_duel_over = True
                if self.logger:
                    self.logger.log_winner(context.current_turn, winner)
                    self.logger.log_turn_end(context.current_turn, context.states)
                return result

            # Phase 3: POST_MOVE
            self._process_phase_for_all(ConditionPhase.POST_MOVE, all_effects, context, all_conditions, result)

            # Reset turn modifiers
            for state in context.states.values():
                state.reset_turn_modifiers()

            # Final death check
            winner = self._check_winner(context)
            if winner is not None:
                result.winner_participant_id = winner
                result.is_duel_over = True
                if self.logger:
                    self.logger.log_winner(context.current_turn, winner)

            # Log turn end
            if self.logger:
                self.logger.log_turn_end(context.current_turn, context.states)

            return result

        finally:
            self.effect_processor.set_interrupt_handler(None)

    def resolve_turn(
        self,
        context: DuelContext,
        actions: list[ParticipantAction],
        world_rules: list[EffectData],
        participant_items: dict[int, dict[ItemSlot, ItemData]],
        all_conditions: dict[int, tuple[ConditionType, dict[str, Any]]] | None = None,
    ) -> TurnResult:
        """Resolve a complete turn.

        Turn flow:
        1. PRE_MOVE effects trigger (poison tick, buffs)
        2. PRE_ATTACK effects trigger (if attack/defense items used)
        3. Attacks and effects resolve (damage goes through interrupt system)
        4. POST_ATTACK effects trigger
        5. POST_MOVE effects trigger (stack decay)
        6. Check win condition

        PRE_DAMAGE and POST_DAMAGE are NOT sequential phases - they are interrupts
        that trigger automatically whenever any damage is applied via ActionExecutor.

        Args:
            context: Duel context with combat states
            actions: Actions from each participant
            world_rules: World rule effects
            participant_items: Equipped items per participant
            all_conditions: All conditions for AND/OR resolution

        Returns:
            TurnResult with effects applied and winner if any
        """
        result = TurnResult(turn_number=context.current_turn)

        # Log turn start
        if self.logger:
            self.logger.log_turn_start(context.current_turn, context.states)

        # Build action lookup
        action_map = {a.participant_id: a for a in actions}

        # Collect all effects for each participant
        all_effects: dict[int, list[EffectData]] = {}
        for participant_id in context.states:
            item_effects = self._get_active_item_effects(
                participant_id,
                action_map.get(participant_id),
                participant_items.get(participant_id, {}),
            )
            all_effects[participant_id] = self.effect_processor.collect_effects_for_participant(participant_id, world_rules, item_effects)

        # Create the damage interrupt handler for this turn
        # This handler will process PRE_DAMAGE/POST_DAMAGE effects whenever damage occurs
        interrupt_handler = DamageInterruptHandler(
            context=context,
            all_effects=all_effects,
            all_conditions=all_conditions,
            logger=self.logger,
        )
        # Set up the circular reference: handler needs processor, processor needs handler
        interrupt_handler.set_effect_processor(self.effect_processor)
        self.effect_processor.set_interrupt_handler(interrupt_handler)

        try:
            # Phase 1: PRE_MOVE
            self._process_phase_for_all(ConditionPhase.PRE_MOVE, all_effects, context, all_conditions, result)

            # Check for deaths after PRE_MOVE (e.g., poison triggers damage interrupt)
            winner = self._check_winner(context)
            if winner is not None:
                result.winner_participant_id = winner
                result.is_duel_over = True
                if self.logger:
                    self.logger.log_winner(context.current_turn, winner)
                    self.logger.log_turn_end(context.current_turn, context.states)
                return result

            # Phase 2: Action resolution (PRE_ATTACK → attacks → POST_ATTACK)
            # Note: Attack effects trigger damage which goes through the interrupt system
            self._process_phase_for_all(ConditionPhase.PRE_ATTACK, all_effects, context, all_conditions, result)
            self._process_phase_for_all(ConditionPhase.POST_ATTACK, all_effects, context, all_conditions, result)

            # Check for deaths after attacks
            winner = self._check_winner(context)
            if winner is not None:
                result.winner_participant_id = winner
                result.is_duel_over = True
                if self.logger:
                    self.logger.log_winner(context.current_turn, winner)
                    self.logger.log_turn_end(context.current_turn, context.states)
                return result

            # Phase 3: POST_MOVE
            self._process_phase_for_all(ConditionPhase.POST_MOVE, all_effects, context, all_conditions, result)

            # Reset turn modifiers
            for state in context.states.values():
                state.reset_turn_modifiers()

            # Final death check
            winner = self._check_winner(context)
            if winner is not None:
                result.winner_participant_id = winner
                result.is_duel_over = True
                if self.logger:
                    self.logger.log_winner(context.current_turn, winner)

            # Log turn end
            if self.logger:
                self.logger.log_turn_end(context.current_turn, context.states)

            return result

        finally:
            # Clean up: remove the interrupt handler to avoid keeping references
            self.effect_processor.set_interrupt_handler(None)

    def _process_phase_for_all(
        self,
        phase: ConditionPhase,
        all_effects: dict[int, list[EffectData]],
        context: DuelContext,
        all_conditions: dict[int, tuple[ConditionType, dict[str, Any]]] | None,
        result: TurnResult,
    ) -> None:
        """Process a phase for all participants."""
        # Log phase start
        if self.logger:
            self.logger.log_phase_start(context.current_turn, phase)

        # Combine all effects and sort by name globally
        combined: list[EffectData] = []
        for effects in all_effects.values():
            combined.extend(effects)

        phase_results = self.effect_processor.process_phase(phase, combined, context, all_conditions, context.current_turn)
        result.effects_applied.extend(phase_results)

        # Log phase end
        if self.logger:
            self.logger.log_phase_end(context.current_turn, phase)

    def _get_active_item_effects(
        self,
        participant_id: int,
        action: ParticipantAction | None,
        items: dict[ItemSlot, ItemData],
    ) -> list[EffectData]:
        """Get effects from items that are active this turn.

        Only returns effects from items that are being used this turn.
        The item slot is determined by the action type.
        """
        effects: list[EffectData] = []

        # If no action or skip, no item effects trigger
        if action is None or action.action_type == DuelActionType.SKIP:
            return effects

        # Map action type to item slot
        slot_map = {
            DuelActionType.ATTACK: ItemSlot.ATTACK,
            DuelActionType.DEFENSE: ItemSlot.DEFENSE,
            DuelActionType.MISC: ItemSlot.MISC,
        }

        active_slot = slot_map.get(action.action_type)
        if active_slot is None:
            return effects

        item = items.get(active_slot)
        if item is None:
            return effects

        for effect in item.effects:
            effect_with_owner = EffectData(
                id=effect.id,
                name=effect.name,
                condition_type=effect.condition_type,
                condition_data=effect.condition_data,
                target=effect.target,
                category=effect.category,
                action_type=effect.action_type,
                action_data=effect.action_data,
                owner_participant_id=participant_id,
                item_name=item.name,
            )
            effects.append(effect_with_owner)

        return effects

    def _get_attack_effects_from_action(
        self,
        participant_id: int,
        action: ParticipantAction,
        items: dict[ItemSlot, ItemData],
    ) -> list[EffectData]:
        """Get attack/ability effects based on the action type."""
        effects: list[EffectData] = []

        # Map action type to item slot
        slot_map = {
            DuelActionType.ATTACK: ItemSlot.ATTACK,
            DuelActionType.DEFENSE: ItemSlot.DEFENSE,
            DuelActionType.MISC: ItemSlot.MISC,
        }

        slot = slot_map.get(action.action_type)
        if slot is None:
            return effects

        item = items.get(slot)
        if item is None:
            return effects

        # Get effects from this item that are attack-like
        # For now, return all effects from the used item
        for effect in item.effects:
            effect_with_owner = EffectData(
                id=effect.id,
                name=effect.name,
                condition_type=effect.condition_type,
                condition_data=effect.condition_data,
                target=effect.target,
                category=effect.category,
                action_type=effect.action_type,
                action_data=effect.action_data,
                owner_participant_id=participant_id,
                item_name=item.name,
            )
            effects.append(effect_with_owner)

        return effects

    def _check_winner(self, context: DuelContext) -> int | None:
        """Check if there's a winner.

        Returns the winner's participant_id, or None if no winner yet.
        If both die simultaneously, the player with turn_order=1 wins (first mover advantage).
        """
        dead_participants: list[int] = []
        alive_participants: list[int] = []

        for pid, state in context.states.items():
            if state.is_alive():
                alive_participants.append(pid)
            else:
                dead_participants.append(pid)

        if not dead_participants:
            return None  # No one died

        if len(alive_participants) == 1:
            return alive_participants[0]  # Clear winner

        if len(alive_participants) == 0:
            # Both died - need to check turn order
            # For now, return None (draw scenario - might need special handling)
            return None

        return None
