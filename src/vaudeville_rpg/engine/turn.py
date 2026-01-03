"""Turn resolver - processes both players' actions simultaneously."""

from dataclasses import dataclass
from typing import Any

from ..db.models.enums import ConditionPhase, ConditionType, DuelActionType, ItemSlot
from .effects import EffectData, EffectProcessor
from .types import DuelContext, TurnResult


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
    slot: ItemSlot
    effects: list[EffectData]


class TurnResolver:
    """Resolves a complete turn with both players' actions."""

    def __init__(self) -> None:
        self.effect_processor = EffectProcessor()

    def resolve_turn(
        self,
        context: DuelContext,
        actions: list[ParticipantAction],
        world_rules: list[EffectData],
        participant_items: dict[int, dict[ItemSlot, ItemData]],
        all_conditions: dict[int, tuple[ConditionType, dict[str, Any]]] | None = None,
    ) -> TurnResult:
        """Resolve a complete turn.

        Turn flow per WIKI.md:
        1. PRE_MOVE effects trigger
        2. Both actions revealed and applied simultaneously
           - PRE_ATTACK → ATTACK → POST_ATTACK effects
           - PRE_DAMAGE → DAMAGE → POST_DAMAGE effects
        3. POST_MOVE effects trigger
        4. Check win condition

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

        # Phase 1: PRE_MOVE
        self._process_phase_for_all(ConditionPhase.PRE_MOVE, all_effects, context, all_conditions, result)

        # Check for deaths after PRE_MOVE (e.g., poison)
        winner = self._check_winner(context)
        if winner is not None:
            result.winner_participant_id = winner
            result.is_duel_over = True
            return result

        # Phase 2: Action resolution (PRE_ATTACK → ATTACK → POST_ATTACK)
        self._process_phase_for_all(ConditionPhase.PRE_ATTACK, all_effects, context, all_conditions, result)

        # Execute actual attacks from actions
        for participant_id, action in action_map.items():
            if action.action_type != DuelActionType.SKIP:
                attack_effects = self._get_attack_effects_from_action(participant_id, action, participant_items.get(participant_id, {}))
                for effect in attack_effects:
                    phase_results = self.effect_processor.process_phase(
                        ConditionPhase.PRE_ATTACK,  # Attack effects trigger at attack phase
                        [effect],
                        context,
                        all_conditions,
                    )
                    result.effects_applied.extend(phase_results)

        self._process_phase_for_all(ConditionPhase.POST_ATTACK, all_effects, context, all_conditions, result)

        # Phase 3: Damage resolution (PRE_DAMAGE → apply → POST_DAMAGE)
        self._process_phase_for_all(ConditionPhase.PRE_DAMAGE, all_effects, context, all_conditions, result)

        # Apply any pending damage
        for state in context.states.values():
            if state.pending_damage > 0:
                actual = state.apply_damage(state.pending_damage)
                if actual > 0:
                    from .types import EffectResult

                    result.add_effect(
                        EffectResult(
                            effect_name="pending_damage",
                            target_participant_id=state.participant_id,
                            action_type="damage",
                            value=actual,
                            description=f"Took {actual} damage",
                        )
                    )

        self._process_phase_for_all(ConditionPhase.POST_DAMAGE, all_effects, context, all_conditions, result)

        # Check for deaths after damage
        winner = self._check_winner(context)
        if winner is not None:
            result.winner_participant_id = winner
            result.is_duel_over = True
            return result

        # Phase 4: POST_MOVE
        self._process_phase_for_all(ConditionPhase.POST_MOVE, all_effects, context, all_conditions, result)

        # Reset turn modifiers
        for state in context.states.values():
            state.reset_turn_modifiers()

        # Final death check
        winner = self._check_winner(context)
        if winner is not None:
            result.winner_participant_id = winner
            result.is_duel_over = True

        return result

    def _process_phase_for_all(
        self,
        phase: ConditionPhase,
        all_effects: dict[int, list[EffectData]],
        context: DuelContext,
        all_conditions: dict[int, tuple[ConditionType, dict[str, Any]]] | None,
        result: TurnResult,
    ) -> None:
        """Process a phase for all participants."""
        # Combine all effects and sort by name globally
        combined: list[EffectData] = []
        for effects in all_effects.values():
            combined.extend(effects)

        phase_results = self.effect_processor.process_phase(phase, combined, context, all_conditions)
        result.effects_applied.extend(phase_results)

    def _get_active_item_effects(
        self,
        participant_id: int,
        action: ParticipantAction | None,
        items: dict[ItemSlot, ItemData],
    ) -> list[EffectData]:
        """Get effects from items that are active this turn.

        All equipped items' passive effects are always active.
        Active abilities trigger based on the action chosen.
        """
        effects: list[EffectData] = []

        for slot, item in items.items():
            for effect in item.effects:
                # Set owner
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
