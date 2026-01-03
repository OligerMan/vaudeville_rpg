"""Tests for the duel engine module."""

import pytest

from vaudeville_rpg.db.models.enums import (
    ActionType,
    ConditionPhase,
    ConditionType,
    DuelActionType,
    EffectCategory,
    TargetType,
)
from vaudeville_rpg.engine.actions import ActionExecutor
from vaudeville_rpg.engine.conditions import ConditionEvaluator
from vaudeville_rpg.engine.effects import EffectData, EffectProcessor
from vaudeville_rpg.engine.turn import ParticipantAction, TurnResolver
from vaudeville_rpg.engine.types import ActionContext, CombatState, DuelContext


class TestCombatState:
    """Tests for CombatState data class."""

    def test_initial_state(self):
        """Test CombatState initial values."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        assert state.player_id == 1
        assert state.participant_id == 10
        assert state.current_hp == 100
        assert state.is_alive()
        assert state.attribute_stacks == {}

    def test_is_alive(self):
        """Test is_alive returns correct value."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=1,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        assert state.is_alive()

        state.current_hp = 0
        assert not state.is_alive()

    def test_get_stacks(self):
        """Test getting stack counts."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks={"poison": 3, "armor": 2},
        )
        assert state.get_stacks("poison") == 3
        assert state.get_stacks("armor") == 2
        assert state.get_stacks("nonexistent") == 0

    def test_add_stacks(self):
        """Test adding stacks to an attribute."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        added = state.add_stacks("poison", 3)
        assert added == 3
        assert state.get_stacks("poison") == 3

        # Add more
        added = state.add_stacks("poison", 2)
        assert added == 2
        assert state.get_stacks("poison") == 5

    def test_add_stacks_with_max(self):
        """Test adding stacks respects max limit."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        added = state.add_stacks("armor", 5, max_stacks=3)
        assert added == 3
        assert state.get_stacks("armor") == 3

        # Try to add more - should cap at 3
        added = state.add_stacks("armor", 2, max_stacks=3)
        assert added == 0
        assert state.get_stacks("armor") == 3

    def test_remove_stacks(self):
        """Test removing stacks from an attribute."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks={"poison": 5},
        )
        removed = state.remove_stacks("poison", 2)
        assert removed == 2
        assert state.get_stacks("poison") == 3

        # Remove more than available
        removed = state.remove_stacks("poison", 10)
        assert removed == 3
        assert state.get_stacks("poison") == 0

    def test_apply_damage(self):
        """Test applying damage."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        actual = state.apply_damage(30)
        assert actual == 30
        assert state.current_hp == 70

        # Overkill damage
        actual = state.apply_damage(100)
        assert actual == 70
        assert state.current_hp == 0

    def test_apply_damage_with_reduction(self):
        """Test damage reduction."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        state.incoming_damage_reduction = 10
        actual = state.apply_damage(30)
        assert actual == 20
        assert state.current_hp == 80

    def test_apply_heal(self):
        """Test healing."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=50,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        actual = state.apply_heal(30)
        assert actual == 30
        assert state.current_hp == 80

        # Overheal
        actual = state.apply_heal(50)
        assert actual == 20
        assert state.current_hp == 100

    def test_spend_resource_special(self):
        """Test spending special points."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        success = state.spend_resource("special", 20)
        assert success
        assert state.current_special_points == 30

        # Not enough
        success = state.spend_resource("special", 40)
        assert not success
        assert state.current_special_points == 30

    def test_spend_resource_hp(self):
        """Test spending HP."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        success = state.spend_resource("hp", 20)
        assert success
        assert state.current_hp == 80

        # Can't spend if it would kill
        success = state.spend_resource("hp", 80)
        assert not success
        assert state.current_hp == 80

    def test_reset_turn_modifiers(self):
        """Test resetting turn modifiers."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        state.incoming_damage_reduction = 10
        state.pending_damage = 5

        state.reset_turn_modifiers()
        assert state.incoming_damage_reduction == 0
        assert state.pending_damage == 0


class TestConditionEvaluator:
    """Tests for ConditionEvaluator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.evaluator = ConditionEvaluator()
        self.state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks={"poison": 3},
        )

    def test_phase_condition_match(self):
        """Test phase condition matches current phase."""
        result = self.evaluator.evaluate(
            ConditionType.PHASE,
            {"phase": "pre_move"},
            ConditionPhase.PRE_MOVE,
            self.state,
        )
        assert result is True

    def test_phase_condition_no_match(self):
        """Test phase condition doesn't match different phase."""
        result = self.evaluator.evaluate(
            ConditionType.PHASE,
            {"phase": "pre_move"},
            ConditionPhase.POST_MOVE,
            self.state,
        )
        assert result is False

    def test_has_stacks_condition_met(self):
        """Test has_stacks condition when stacks are present."""
        result = self.evaluator.evaluate(
            ConditionType.HAS_STACKS,
            {"attribute": "poison", "min_count": 2},
            ConditionPhase.PRE_MOVE,
            self.state,
        )
        assert result is True

    def test_has_stacks_condition_not_met(self):
        """Test has_stacks condition when not enough stacks."""
        result = self.evaluator.evaluate(
            ConditionType.HAS_STACKS,
            {"attribute": "poison", "min_count": 5},
            ConditionPhase.PRE_MOVE,
            self.state,
        )
        assert result is False

    def test_has_stacks_condition_missing_attribute(self):
        """Test has_stacks condition for missing attribute."""
        result = self.evaluator.evaluate(
            ConditionType.HAS_STACKS,
            {"attribute": "armor", "min_count": 1},
            ConditionPhase.PRE_MOVE,
            self.state,
        )
        assert result is False

    def test_and_condition(self):
        """Test AND condition with all true."""
        all_conditions = {
            1: (ConditionType.PHASE, {"phase": "pre_move"}),
            2: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
        }
        result = self.evaluator.evaluate(
            ConditionType.AND,
            {"condition_ids": [1, 2]},
            ConditionPhase.PRE_MOVE,
            self.state,
            all_conditions,
        )
        assert result is True

    def test_and_condition_one_false(self):
        """Test AND condition with one false."""
        all_conditions = {
            1: (ConditionType.PHASE, {"phase": "pre_move"}),
            2: (ConditionType.HAS_STACKS, {"attribute": "armor", "min_count": 1}),
        }
        result = self.evaluator.evaluate(
            ConditionType.AND,
            {"condition_ids": [1, 2]},
            ConditionPhase.PRE_MOVE,
            self.state,
            all_conditions,
        )
        assert result is False

    def test_or_condition_one_true(self):
        """Test OR condition with one true."""
        all_conditions = {
            1: (ConditionType.PHASE, {"phase": "post_move"}),  # False
            2: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),  # True
        }
        result = self.evaluator.evaluate(
            ConditionType.OR,
            {"condition_ids": [1, 2]},
            ConditionPhase.PRE_MOVE,
            self.state,
            all_conditions,
        )
        assert result is True

    def test_or_condition_all_false(self):
        """Test OR condition with all false."""
        all_conditions = {
            1: (ConditionType.PHASE, {"phase": "post_move"}),
            2: (ConditionType.HAS_STACKS, {"attribute": "armor", "min_count": 1}),
        }
        result = self.evaluator.evaluate(
            ConditionType.OR,
            {"condition_ids": [1, 2]},
            ConditionPhase.PRE_MOVE,
            self.state,
            all_conditions,
        )
        assert result is False


class TestActionExecutor:
    """Tests for ActionExecutor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.executor = ActionExecutor()
        self.source_state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        self.target_state = CombatState(
            player_id=2,
            participant_id=20,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )

    def _make_context(self, action_data: dict) -> ActionContext:
        """Create an action context."""
        return ActionContext(
            source_participant_id=10,
            source_state=self.source_state,
            target_state=self.target_state,
            action_data=action_data,
        )

    def test_execute_damage(self):
        """Test damage action."""
        context = self._make_context({"value": 30})
        result = self.executor.execute(ActionType.DAMAGE, {"value": 30}, context, "test_damage")
        assert result.value == 30
        assert self.target_state.current_hp == 70

    def test_execute_attack(self):
        """Test attack action."""
        context = self._make_context({"value": 25})
        result = self.executor.execute(ActionType.ATTACK, {"value": 25}, context, "test_attack")
        assert result.value == 25
        assert self.target_state.current_hp == 75

    def test_execute_heal(self):
        """Test heal action."""
        self.target_state.current_hp = 50
        context = self._make_context({"value": 30})
        result = self.executor.execute(ActionType.HEAL, {"value": 30}, context, "test_heal")
        assert result.value == 30
        assert self.target_state.current_hp == 80

    def test_execute_add_stacks(self):
        """Test add_stacks action."""
        context = self._make_context({"attribute": "poison", "value": 3})
        result = self.executor.execute(
            ActionType.ADD_STACKS,
            {"attribute": "poison", "value": 3},
            context,
            "test_add_stacks",
        )
        assert result.value == 3
        assert self.target_state.get_stacks("poison") == 3

    def test_execute_remove_stacks(self):
        """Test remove_stacks action."""
        self.target_state.attribute_stacks["poison"] = 5
        context = self._make_context({"attribute": "poison", "value": 2})
        result = self.executor.execute(
            ActionType.REMOVE_STACKS,
            {"attribute": "poison", "value": 2},
            context,
            "test_remove_stacks",
        )
        assert result.value == 2
        assert self.target_state.get_stacks("poison") == 3

    def test_execute_reduce_incoming_damage(self):
        """Test reduce_incoming_damage action."""
        context = self._make_context({"value": 5})
        result = self.executor.execute(
            ActionType.REDUCE_INCOMING_DAMAGE,
            {"value": 5},
            context,
            "test_reduce_damage",
        )
        assert result.value == 5
        assert self.target_state.incoming_damage_reduction == 5

    def test_execute_spend_special(self):
        """Test spend action for special points."""
        context = self._make_context({"resource": "special", "value": 20})
        result = self.executor.execute(
            ActionType.SPEND,
            {"resource": "special", "value": 20},
            context,
            "test_spend",
        )
        assert result.value == 20
        assert self.source_state.current_special_points == 30


class TestEffectProcessor:
    """Tests for EffectProcessor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = EffectProcessor()
        self.state1 = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks={"poison": 3},
        )
        self.state2 = CombatState(
            player_id=2,
            participant_id=20,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        self.context = DuelContext(
            duel_id=1,
            setting_id=1,
            current_turn=1,
            states={10: self.state1, 20: self.state2},
        )

    def test_process_phase_triggers_matching_effects(self):
        """Test that effects trigger at the correct phase."""
        effects = [
            EffectData(
                id=1,
                name="poison_damage",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "pre_move"},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 5},
                owner_participant_id=10,
            )
        ]

        results = self.processor.process_phase(ConditionPhase.PRE_MOVE, effects, self.context)
        assert len(results) == 1
        assert results[0].value == 5
        assert self.state1.current_hp == 95

    def test_process_phase_skips_wrong_phase(self):
        """Test that effects don't trigger at wrong phase."""
        effects = [
            EffectData(
                id=1,
                name="poison_damage",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "pre_move"},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 5},
                owner_participant_id=10,
            )
        ]

        results = self.processor.process_phase(ConditionPhase.POST_MOVE, effects, self.context)
        assert len(results) == 0
        assert self.state1.current_hp == 100

    def test_process_phase_enemy_target(self):
        """Test effects that target enemy."""
        effects = [
            EffectData(
                id=1,
                name="attack_effect",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "pre_attack"},
                target=TargetType.ENEMY,
                category=EffectCategory.ITEM_EFFECT,
                action_type="damage",
                action_data={"value": 10},
                owner_participant_id=10,
            )
        ]

        results = self.processor.process_phase(ConditionPhase.PRE_ATTACK, effects, self.context)
        assert len(results) == 1
        assert self.state2.current_hp == 90  # Enemy took damage

    def test_effects_sorted_alphabetically(self):
        """Test effects are processed in alphabetical order."""
        effects = [
            EffectData(
                id=2,
                name="zebra_effect",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "pre_move"},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="heal",
                action_data={"value": 10},
                owner_participant_id=10,
            ),
            EffectData(
                id=1,
                name="alpha_effect",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "pre_move"},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 5},
                owner_participant_id=10,
            ),
        ]

        results = self.processor.process_phase(ConditionPhase.PRE_MOVE, effects, self.context)
        assert len(results) == 2
        assert results[0].effect_name == "alpha_effect"
        assert results[1].effect_name == "zebra_effect"


class TestTurnResolver:
    """Tests for TurnResolver."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = TurnResolver()
        self.state1 = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        self.state2 = CombatState(
            player_id=2,
            participant_id=20,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        self.context = DuelContext(
            duel_id=1,
            setting_id=1,
            current_turn=1,
            states={10: self.state1, 20: self.state2},
        )

    def test_resolve_turn_with_skip_actions(self):
        """Test resolving a turn where both players skip."""
        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        result = self.resolver.resolve_turn(
            self.context,
            actions,
            world_rules=[],
            participant_items={10: {}, 20: {}},
        )

        assert result.turn_number == 1
        assert not result.is_duel_over
        assert result.winner_participant_id is None

    def test_resolve_turn_with_world_rule_damage(self):
        """Test world rule dealing damage during turn."""
        self.state1.attribute_stacks["poison"] = 3

        world_rules = [
            EffectData(
                id=1,
                name="poison_tick",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "pre_move"},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 10},
                owner_participant_id=0,  # Will be set per-participant
            )
        ]

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        self.resolver.resolve_turn(
            self.context,
            actions,
            world_rules=world_rules,
            participant_items={10: {}, 20: {}},
        )

        # Both players should take poison damage
        assert self.state1.current_hp == 90
        assert self.state2.current_hp == 90

    def test_check_winner_one_dead(self):
        """Test winner detection when one player dies."""
        self.state2.current_hp = 0
        winner = self.resolver._check_winner(self.context)
        assert winner == 10

    def test_check_winner_both_alive(self):
        """Test no winner when both alive."""
        winner = self.resolver._check_winner(self.context)
        assert winner is None

    def test_check_winner_both_dead(self):
        """Test draw scenario when both dead."""
        self.state1.current_hp = 0
        self.state2.current_hp = 0
        winner = self.resolver._check_winner(self.context)
        assert winner is None  # Draw

    def test_turn_modifiers_reset(self):
        """Test that turn modifiers are reset after turn."""
        self.state1.incoming_damage_reduction = 10

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        self.resolver.resolve_turn(
            self.context,
            actions,
            world_rules=[],
            participant_items={10: {}, 20: {}},
        )

        assert self.state1.incoming_damage_reduction == 0


class TestDuelContext:
    """Tests for DuelContext."""

    def test_get_opponent_state(self):
        """Test getting opponent's state."""
        state1 = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        state2 = CombatState(
            player_id=2,
            participant_id=20,
            current_hp=80,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        context = DuelContext(
            duel_id=1,
            setting_id=1,
            current_turn=1,
            states={10: state1, 20: state2},
        )

        opponent = context.get_opponent_state(10)
        assert opponent.participant_id == 20
        assert opponent.current_hp == 80

        opponent = context.get_opponent_state(20)
        assert opponent.participant_id == 10
        assert opponent.current_hp == 100

    def test_get_opponent_state_not_found(self):
        """Test error when opponent not found."""
        state1 = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        context = DuelContext(
            duel_id=1,
            setting_id=1,
            current_turn=1,
            states={10: state1},
        )

        with pytest.raises(ValueError):
            context.get_opponent_state(10)
