"""Tests for the damage interrupt system.

This module tests the DamageInterruptHandler which processes PRE_DAMAGE/POST_DAMAGE
effects as interrupts that fire whenever damage is applied.
"""

from vaudeville_rpg.db.models.enums import (
    ActionType,
    ConditionPhase,
    ConditionType,
    DuelActionType,
    EffectCategory,
    TargetType,
)
from vaudeville_rpg.engine import CombatLogger, DamageInterruptHandler, LogEventType
from vaudeville_rpg.engine.effects import EffectData, EffectProcessor
from vaudeville_rpg.engine.turn import ParticipantAction, TurnResolver
from vaudeville_rpg.engine.types import CombatState, DuelContext


class TestDamageInterruptHandler:
    """Tests for DamageInterruptHandler."""

    def _create_combat_state(self, player_id: int, participant_id: int, hp: int = 100, stacks: dict | None = None) -> CombatState:
        """Create a combat state for testing."""
        return CombatState(
            player_id=player_id,
            participant_id=participant_id,
            current_hp=hp,
            max_hp=hp,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks=stacks or {},
        )

    def _create_context(self, state1: CombatState, state2: CombatState) -> DuelContext:
        """Create a duel context with two states."""
        return DuelContext(
            duel_id=1,
            setting_id=1,
            current_turn=1,
            states={state1.participant_id: state1, state2.participant_id: state2},
        )

    def test_apply_damage_without_interrupts_blocked(self):
        """Test that damage is applied when interrupts are not blocked."""
        state1 = self._create_combat_state(1, 10, hp=100)
        state2 = self._create_combat_state(2, 20, hp=100)
        context = self._create_context(state1, state2)

        handler = DamageInterruptHandler(
            context=context,
            all_effects={10: [], 20: []},
            all_conditions=None,
            logger=None,
        )
        # Set up effect processor for the handler
        processor = EffectProcessor()
        handler.set_effect_processor(processor)

        result = handler.apply_damage(
            target_state=state1,
            damage=25,
            effect_name="test_attack",
        )

        assert result.actual_damage == 25
        assert state1.current_hp == 75  # 100 - 25

    def test_apply_damage_with_reduction(self):
        """Test that damage reduction is respected."""
        state1 = self._create_combat_state(1, 10, hp=100)
        state1.incoming_damage_reduction = 10
        state2 = self._create_combat_state(2, 20, hp=100)
        context = self._create_context(state1, state2)

        handler = DamageInterruptHandler(
            context=context,
            all_effects={10: [], 20: []},
            all_conditions=None,
            logger=None,
        )
        processor = EffectProcessor()
        handler.set_effect_processor(processor)

        result = handler.apply_damage(
            target_state=state1,
            damage=25,
            effect_name="test_attack",
        )

        assert result.actual_damage == 15  # 25 - 10 reduction
        assert state1.current_hp == 85  # 100 - 15

    def test_damage_blocked_when_interrupts_blocked(self):
        """Test that when interrupts are blocked, damage is applied directly."""
        state1 = self._create_combat_state(1, 10, hp=100)
        state2 = self._create_combat_state(2, 20, hp=100)
        context = self._create_context(state1, state2)
        context.damage_interrupts_blocked = True  # Simulate nested damage

        handler = DamageInterruptHandler(
            context=context,
            all_effects={10: [], 20: []},
            all_conditions=None,
            logger=None,
        )
        processor = EffectProcessor()
        handler.set_effect_processor(processor)

        result = handler.apply_damage(
            target_state=state1,
            damage=25,
            effect_name="nested_damage",
        )

        # Damage should still be applied, but no interrupt effects processed
        assert result.actual_damage == 25
        assert state1.current_hp == 75
        # No effect results from interrupts
        assert len(result.effect_results) == 0

    def test_pre_damage_adds_reduction(self):
        """Test that PRE_DAMAGE effects can add damage reduction."""
        state1 = self._create_combat_state(1, 10, hp=100, stacks={"armor": 3})
        state2 = self._create_combat_state(2, 20, hp=100)
        context = self._create_context(state1, state2)

        # PRE_DAMAGE effect that adds reduction when target has armor
        armor_reduction = EffectData(
            id=1,
            name="armor_reduction",
            condition_type=ConditionType.AND,
            condition_data={"condition_ids": [101, 102]},
            target=TargetType.SELF,
            category=EffectCategory.WORLD_RULE,
            action_type="reduce_incoming_damage",
            action_data={"value": 5},  # 5 reduction
            owner_participant_id=10,
        )

        all_conditions = {
            101: (ConditionType.PHASE, {"phase": "pre_damage"}),
            102: (ConditionType.HAS_STACKS, {"attribute": "armor", "min_count": 1}),
        }

        handler = DamageInterruptHandler(
            context=context,
            all_effects={10: [armor_reduction], 20: []},
            all_conditions=all_conditions,
            logger=None,
        )
        processor = EffectProcessor()
        handler.set_effect_processor(processor)

        result = handler.apply_damage(
            target_state=state1,
            damage=20,
            effect_name="enemy_attack",
        )

        # PRE_DAMAGE adds 5 reduction, so 20 - 5 = 15 damage
        assert result.actual_damage == 15
        assert state1.current_hp == 85

    def test_interrupts_blocked_during_processing(self):
        """Test that interrupts are blocked during PRE/POST_DAMAGE processing."""
        state1 = self._create_combat_state(1, 10, hp=100)
        state2 = self._create_combat_state(2, 20, hp=100)
        context = self._create_context(state1, state2)

        handler = DamageInterruptHandler(
            context=context,
            all_effects={10: [], 20: []},
            all_conditions=None,
            logger=None,
        )
        processor = EffectProcessor()
        handler.set_effect_processor(processor)

        # Before apply_damage
        assert context.damage_interrupts_blocked is False

        result = handler.apply_damage(
            target_state=state1,
            damage=10,
            effect_name="test",
        )

        # After apply_damage, interrupts should be unblocked
        assert context.damage_interrupts_blocked is False
        assert result.actual_damage == 10

    def test_target_died_flag(self):
        """Test that target_died is set when HP drops to 0."""
        state1 = self._create_combat_state(1, 10, hp=20)
        state2 = self._create_combat_state(2, 20, hp=100)
        context = self._create_context(state1, state2)

        handler = DamageInterruptHandler(
            context=context,
            all_effects={10: [], 20: []},
            all_conditions=None,
            logger=None,
        )
        processor = EffectProcessor()
        handler.set_effect_processor(processor)

        result = handler.apply_damage(
            target_state=state1,
            damage=25,
            effect_name="killing_blow",
        )

        assert result.actual_damage == 20  # Can only deal up to current HP
        assert state1.current_hp == 0
        assert result.target_died is True

    def test_pre_damage_only_triggers_for_damage_target(self):
        """Test that PRE_DAMAGE effects only trigger for the player receiving damage.

        When Player 2 (participant_id=20) damages Player 1 (participant_id=10):
        - Player 1's PRE_DAMAGE effects should trigger (they are the target)
        - Player 2's PRE_DAMAGE effects should NOT trigger (they are the attacker)
        """
        # Player 1 (target) has armor with PRE_DAMAGE reduction
        state1 = self._create_combat_state(1, 10, hp=100, stacks={"armor": 3})
        # Player 2 (attacker) also has armor with PRE_DAMAGE reduction
        state2 = self._create_combat_state(2, 20, hp=100, stacks={"armor": 3})
        context = self._create_context(state1, state2)

        # Both players have armor reduction effects
        armor_effect_p1 = EffectData(
            id=1,
            name="armor_reduction_p1",
            condition_type=ConditionType.PHASE,
            condition_data={"phase": ConditionPhase.PRE_DAMAGE.value},
            target=TargetType.SELF,
            category=EffectCategory.WORLD_RULE,
            action_type=ActionType.REDUCE_INCOMING_DAMAGE.value,
            action_data={"value": 5},
            owner_participant_id=10,  # Player 1 owns this effect
        )
        armor_effect_p2 = EffectData(
            id=2,
            name="armor_reduction_p2",
            condition_type=ConditionType.PHASE,
            condition_data={"phase": ConditionPhase.PRE_DAMAGE.value},
            target=TargetType.SELF,
            category=EffectCategory.WORLD_RULE,
            action_type=ActionType.REDUCE_INCOMING_DAMAGE.value,
            action_data={"value": 5},
            owner_participant_id=20,  # Player 2 owns this effect
        )

        handler = DamageInterruptHandler(
            context=context,
            all_effects={10: [armor_effect_p1], 20: [armor_effect_p2]},
            all_conditions=None,
            logger=None,
        )
        processor = EffectProcessor()
        handler.set_effect_processor(processor)

        # Player 2 damages Player 1 with 20 damage
        result = handler.apply_damage(
            target_state=state1,  # Player 1 is the target
            damage=20,
            effect_name="attack_from_p2",
            source_participant_id=20,  # Player 2 is the attacker
        )

        # Only Player 1's armor should trigger (5 reduction)
        # If Player 2's armor also triggered, reduction would be 10
        assert result.actual_damage == 15  # 20 - 5 = 15
        assert state1.current_hp == 85

        # Verify Player 2's HP is unchanged (their armor didn't do anything)
        assert state2.current_hp == 100

    def test_attacker_armor_does_not_reduce_damage_they_deal(self):
        """Test that when Player 2 attacks Player 1, Player 2's armor doesn't apply.

        This is a regression test for the bug where attacker's PRE_DAMAGE effects
        would incorrectly trigger when they deal damage.
        """
        # Player 1 (target) has NO armor
        state1 = self._create_combat_state(1, 10, hp=100, stacks={})
        # Player 2 (attacker) has armor with PRE_DAMAGE reduction
        state2 = self._create_combat_state(2, 20, hp=100, stacks={"armor": 5})
        context = self._create_context(state1, state2)

        # Only Player 2 has armor reduction effect
        armor_effect_p2 = EffectData(
            id=1,
            name="armor_reduction_p2",
            condition_type=ConditionType.PHASE,
            condition_data={"phase": ConditionPhase.PRE_DAMAGE.value},
            target=TargetType.SELF,
            category=EffectCategory.WORLD_RULE,
            action_type=ActionType.REDUCE_INCOMING_DAMAGE.value,
            action_data={"value": 10},
            owner_participant_id=20,  # Player 2 owns this effect
        )

        handler = DamageInterruptHandler(
            context=context,
            all_effects={10: [], 20: [armor_effect_p2]},  # Only P2 has effects
            all_conditions=None,
            logger=None,
        )
        processor = EffectProcessor()
        handler.set_effect_processor(processor)

        # Player 2 attacks Player 1 with 20 damage
        result = handler.apply_damage(
            target_state=state1,  # Player 1 is the target
            damage=20,
            effect_name="attack_from_p2",
            source_participant_id=20,  # Player 2 is the attacker
        )

        # Player 2's armor should NOT reduce damage dealt to Player 1
        # Full 20 damage should be applied
        assert result.actual_damage == 20
        assert state1.current_hp == 80  # 100 - 20


class TestInterruptSystemLogging:
    """Tests for interrupt system logging."""

    def _create_combat_state(self, player_id: int, participant_id: int, hp: int = 100, stacks: dict | None = None) -> CombatState:
        """Create a combat state for testing."""
        return CombatState(
            player_id=player_id,
            participant_id=participant_id,
            current_hp=hp,
            max_hp=hp,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks=stacks or {},
        )

    def _create_context(self, state1: CombatState, state2: CombatState) -> DuelContext:
        """Create a duel context with two states."""
        return DuelContext(
            duel_id=1,
            setting_id=1,
            current_turn=1,
            states={state1.participant_id: state1, state2.participant_id: state2},
        )

    def test_damage_interrupt_logging(self):
        """Test that damage interrupts are logged correctly."""
        state1 = self._create_combat_state(1, 10, hp=100)
        state2 = self._create_combat_state(2, 20, hp=100)
        context = self._create_context(state1, state2)
        logger = CombatLogger(duel_id=1)

        handler = DamageInterruptHandler(
            context=context,
            all_effects={10: [], 20: []},
            all_conditions=None,
            logger=logger,
        )
        processor = EffectProcessor(logger=logger)
        handler.set_effect_processor(processor)

        handler.apply_damage(
            target_state=state1,
            damage=25,
            effect_name="sword_slash",
        )

        log = logger.get_log()

        # Should have interrupt start, damage applied, and interrupt end
        interrupt_starts = log.get_entries_by_type(LogEventType.DAMAGE_INTERRUPT_START)
        damage_applied = log.get_entries_by_type(LogEventType.DAMAGE_APPLIED)
        interrupt_ends = log.get_entries_by_type(LogEventType.DAMAGE_INTERRUPT_END)

        assert len(interrupt_starts) == 1
        assert interrupt_starts[0].value == 25
        assert interrupt_starts[0].effect_name == "sword_slash"

        assert len(damage_applied) == 1
        assert damage_applied[0].value == 25

        assert len(interrupt_ends) == 1


class TestInterruptSystemIntegration:
    """Integration tests for the interrupt system with TurnResolver."""

    def _create_combat_state(self, player_id: int, participant_id: int, hp: int = 100, stacks: dict | None = None) -> CombatState:
        """Create a combat state for testing."""
        return CombatState(
            player_id=player_id,
            participant_id=participant_id,
            current_hp=hp,
            max_hp=hp,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks=stacks or {},
        )

    def _create_context(self, state1: CombatState, state2: CombatState) -> DuelContext:
        """Create a duel context with two states."""
        return DuelContext(
            duel_id=1,
            setting_id=1,
            current_turn=1,
            states={state1.participant_id: state1, state2.participant_id: state2},
        )

    def test_poison_triggers_pre_damage_interrupt(self):
        """Test that poison damage in PRE_MOVE triggers PRE_DAMAGE interrupt."""
        state1 = self._create_combat_state(1, 10, hp=100, stacks={"poison": 2, "armor": 3})
        state2 = self._create_combat_state(2, 20, hp=100)
        context = self._create_context(state1, state2)
        logger = CombatLogger(duel_id=1)

        resolver = TurnResolver(logger=logger)

        # World rules:
        # 1. Poison tick at PRE_MOVE
        # 2. Armor reduces damage at PRE_DAMAGE
        world_rules = [
            EffectData(
                id=1,
                name="a_poison_tick",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [100, 101]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 10},
                owner_participant_id=0,
            ),
            EffectData(
                id=2,
                name="armor_reduction",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [102, 103]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="reduce_incoming_damage",
                action_data={"value": 5},
                owner_participant_id=0,
            ),
        ]

        all_conditions = {
            100: (ConditionType.PHASE, {"phase": "pre_move"}),
            101: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
            102: (ConditionType.PHASE, {"phase": "pre_damage"}),
            103: (ConditionType.HAS_STACKS, {"attribute": "armor", "min_count": 1}),
        }

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        resolver.resolve_turn(
            context,
            actions,
            world_rules=world_rules,
            participant_items={10: {}, 20: {}},
            all_conditions=all_conditions,
        )

        # Poison deals 10 damage, armor reduces by 5, so 5 damage taken
        assert state1.current_hp == 95

        # Check that interrupt events were logged
        log = logger.get_log()
        interrupt_starts = log.get_entries_by_type(LogEventType.DAMAGE_INTERRUPT_START)
        assert len(interrupt_starts) >= 1

    def test_post_damage_triggers_after_damage(self):
        """Test that POST_DAMAGE effects trigger after damage is applied."""
        state1 = self._create_combat_state(1, 10, hp=100, stacks={"poison": 1, "thorns": 2})
        state2 = self._create_combat_state(2, 20, hp=100)
        context = self._create_context(state1, state2)
        logger = CombatLogger(duel_id=1)

        resolver = TurnResolver(logger=logger)

        # World rules:
        # 1. Poison tick at PRE_MOVE
        # 2. Thorns damage at POST_DAMAGE (revenge damage)
        world_rules = [
            EffectData(
                id=1,
                name="a_poison_tick",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [100, 101]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 10},
                owner_participant_id=0,
            ),
            EffectData(
                id=2,
                name="thorns_revenge",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [102, 103]},
                target=TargetType.ENEMY,  # Damages the enemy
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 5},
                owner_participant_id=0,
            ),
        ]

        all_conditions = {
            100: (ConditionType.PHASE, {"phase": "pre_move"}),
            101: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
            102: (ConditionType.PHASE, {"phase": "post_damage"}),
            103: (ConditionType.HAS_STACKS, {"attribute": "thorns", "min_count": 1}),
        }

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        resolver.resolve_turn(
            context,
            actions,
            world_rules=world_rules,
            participant_items={10: {}, 20: {}},
            all_conditions=all_conditions,
        )

        # State1 takes 10 poison damage
        assert state1.current_hp == 90

        # State2 takes 5 thorns revenge damage (triggered during POST_DAMAGE of poison)
        # Note: The thorns damage is applied directly because interrupts are blocked
        assert state2.current_hp == 95

    def test_no_interrupt_without_damage(self):
        """Test that no interrupt events fire when no damage is dealt."""
        state1 = self._create_combat_state(1, 10, hp=100)
        state2 = self._create_combat_state(2, 20, hp=100)
        context = self._create_context(state1, state2)
        logger = CombatLogger(duel_id=1)

        resolver = TurnResolver(logger=logger)

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        resolver.resolve_turn(
            context,
            actions,
            world_rules=[],
            participant_items={10: {}, 20: {}},
        )

        log = logger.get_log()
        interrupt_starts = log.get_entries_by_type(LogEventType.DAMAGE_INTERRUPT_START)
        assert len(interrupt_starts) == 0
