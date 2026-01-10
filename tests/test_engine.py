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


class TestComplexWorldEffects:
    """Tests for complex world effect interactions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = TurnResolver()

    def _create_combat_state(
        self,
        player_id: int,
        participant_id: int,
        hp: int = 100,
        stacks: dict | None = None,
    ) -> CombatState:
        """Helper to create combat state."""
        return CombatState(
            player_id=player_id,
            participant_id=participant_id,
            current_hp=hp,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks=stacks or {},
        )

    def _create_context(self, state1: CombatState, state2: CombatState, turn: int = 1) -> DuelContext:
        """Helper to create duel context."""
        return DuelContext(
            duel_id=1,
            setting_id=1,
            current_turn=turn,
            states={state1.participant_id: state1, state2.participant_id: state2},
        )

    def test_poison_tick_and_decay(self):
        """Test poison deals damage at PRE_MOVE and decays at POST_MOVE."""
        state1 = self._create_combat_state(1, 10, stacks={"poison": 3})
        state2 = self._create_combat_state(2, 20, stacks={"poison": 2})
        context = self._create_context(state1, state2)

        # Poison tick: deals 5 damage per stack at PRE_MOVE
        # Poison decay: removes 1 stack at POST_MOVE
        world_rules = [
            EffectData(
                id=1,
                name="a_poison_tick",  # 'a' prefix to run first
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [101, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 5},
                owner_participant_id=0,
            ),
            EffectData(
                id=2,
                name="b_poison_decay",  # 'b' prefix to run second
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [103, 104]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="remove_stacks",
                action_data={"attribute": "poison", "value": 1},
                owner_participant_id=0,
            ),
        ]

        # Conditions for AND resolution
        all_conditions = {
            101: (ConditionType.PHASE, {"phase": "pre_move"}),
            102: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
            103: (ConditionType.PHASE, {"phase": "post_move"}),
            104: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
        }

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        result = self.resolver.resolve_turn(
            context,
            actions,
            world_rules=world_rules,
            participant_items={10: {}, 20: {}},
            all_conditions=all_conditions,
        )

        # Player 1: 100 - 5 (poison tick) = 95 HP, 3 - 1 = 2 poison stacks
        assert state1.current_hp == 95
        assert state1.get_stacks("poison") == 2

        # Player 2: 100 - 5 (poison tick) = 95 HP, 2 - 1 = 1 poison stack
        assert state2.current_hp == 95
        assert state2.get_stacks("poison") == 1

        assert not result.is_duel_over

    def test_armor_reduces_and_decays(self):
        """Test armor reduces damage at PRE_DAMAGE (interrupt) and decays at POST_MOVE."""
        # Player 1 has armor and poison (poison will trigger damage -> PRE_DAMAGE interrupt)
        state1 = self._create_combat_state(1, 10, stacks={"armor": 3, "poison": 1})
        state2 = self._create_combat_state(2, 20)
        context = self._create_context(state1, state2)

        # Poison tick at PRE_MOVE (triggers damage -> PRE_DAMAGE interrupt)
        # Armor reduction at PRE_DAMAGE (interrupt)
        # Armor decay at POST_MOVE (sequential phase)
        world_rules = [
            EffectData(
                id=1,
                name="a_poison_tick",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [100, 105]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 10},  # 10 damage
                owner_participant_id=0,
            ),
            EffectData(
                id=2,
                name="armor_reduction",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [101, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="reduce_incoming_damage",
                action_data={"value": 5},  # 5 reduction per call (we have 3 armor)
                owner_participant_id=0,
            ),
            EffectData(
                id=3,
                name="armor_decay",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [103, 104]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="remove_stacks",
                action_data={"attribute": "armor", "value": 1},
                owner_participant_id=0,
            ),
        ]

        all_conditions = {
            100: (ConditionType.PHASE, {"phase": "pre_move"}),
            105: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
            101: (ConditionType.PHASE, {"phase": "pre_damage"}),
            102: (ConditionType.HAS_STACKS, {"attribute": "armor", "min_count": 1}),
            103: (ConditionType.PHASE, {"phase": "post_move"}),  # Changed to POST_MOVE
            104: (ConditionType.HAS_STACKS, {"attribute": "armor", "min_count": 1}),
        }

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        self.resolver.resolve_turn(
            context,
            actions,
            world_rules=world_rules,
            participant_items={10: {}, 20: {}},
            all_conditions=all_conditions,
        )

        # Player 1 has armor, which should reduce damage and then decay at end of turn
        assert state1.get_stacks("armor") == 2  # Decayed from 3 to 2 at POST_MOVE
        # Poison dealt 10 damage, armor reduced by 5, so 5 damage taken (100 - 5 = 95)
        assert state1.current_hp == 95

    def test_multiple_dot_effects(self):
        """Test multiple damage-over-time effects (poison + burn)."""
        state1 = self._create_combat_state(1, 10, stacks={"poison": 2, "burn": 3})
        state2 = self._create_combat_state(2, 20)
        context = self._create_context(state1, state2)

        world_rules = [
            EffectData(
                id=1,
                name="a_burn_tick",  # Burns first (alphabetical)
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [101, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 3},  # 3 damage per burn stack
                owner_participant_id=0,
            ),
            EffectData(
                id=2,
                name="b_poison_tick",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [101, 103]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 2},  # 2 damage per poison stack
                owner_participant_id=0,
            ),
        ]

        all_conditions = {
            101: (ConditionType.PHASE, {"phase": "pre_move"}),
            102: (ConditionType.HAS_STACKS, {"attribute": "burn", "min_count": 1}),
            103: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
        }

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        self.resolver.resolve_turn(
            context,
            actions,
            world_rules=world_rules,
            participant_items={10: {}, 20: {}},
            all_conditions=all_conditions,
        )

        # Player 1: 100 - 3 (burn) - 2 (poison) = 95 HP
        assert state1.current_hp == 95
        # Player 2: no stacks, no damage
        assert state2.current_hp == 100

    def test_heal_and_damage_same_turn(self):
        """Test healing and damage effects in the same turn."""
        state1 = self._create_combat_state(1, 10, hp=50, stacks={"regen": 2, "poison": 1})
        state2 = self._create_combat_state(2, 20)
        context = self._create_context(state1, state2)

        world_rules = [
            EffectData(
                id=1,
                name="a_regen_tick",  # Heals first (alphabetical)
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [101, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="heal",
                action_data={"value": 10},
                owner_participant_id=0,
            ),
            EffectData(
                id=2,
                name="b_poison_tick",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [101, 103]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 5},
                owner_participant_id=0,
            ),
        ]

        all_conditions = {
            101: (ConditionType.PHASE, {"phase": "pre_move"}),
            102: (ConditionType.HAS_STACKS, {"attribute": "regen", "min_count": 1}),
            103: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
        }

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        self.resolver.resolve_turn(
            context,
            actions,
            world_rules=world_rules,
            participant_items={10: {}, 20: {}},
            all_conditions=all_conditions,
        )

        # Player 1: 50 + 10 (regen) - 5 (poison) = 55 HP
        assert state1.current_hp == 55


class TestMultiTurnDuelScenarios:
    """Tests for multi-turn duel scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = TurnResolver()

    def _create_combat_state(
        self,
        player_id: int,
        participant_id: int,
        hp: int = 100,
        stacks: dict | None = None,
    ) -> CombatState:
        """Helper to create combat state."""
        return CombatState(
            player_id=player_id,
            participant_id=participant_id,
            current_hp=hp,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks=stacks.copy() if stacks else {},
        )

    def _create_context(self, state1: CombatState, state2: CombatState, turn: int = 1) -> DuelContext:
        """Helper to create duel context."""
        return DuelContext(
            duel_id=1,
            setting_id=1,
            current_turn=turn,
            states={state1.participant_id: state1, state2.participant_id: state2},
        )

    def test_poison_kills_over_multiple_turns(self):
        """Test that poison eventually kills a player over multiple turns."""
        state1 = self._create_combat_state(1, 10, hp=30, stacks={"poison": 5})
        state2 = self._create_combat_state(2, 20)

        # Poison: 10 damage per turn, decays 1 stack per turn
        world_rules = [
            EffectData(
                id=1,
                name="poison_tick",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [101, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 10},
                owner_participant_id=0,
            ),
            EffectData(
                id=2,
                name="poison_decay",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [103, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="remove_stacks",
                action_data={"attribute": "poison", "value": 1},
                owner_participant_id=0,
            ),
        ]

        all_conditions = {
            101: (ConditionType.PHASE, {"phase": "pre_move"}),
            102: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
            103: (ConditionType.PHASE, {"phase": "post_move"}),
        }

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        # Turn 1: 30 HP - 10 = 20 HP, 5 -> 4 stacks
        context = self._create_context(state1, state2, turn=1)
        result = self.resolver.resolve_turn(context, actions, world_rules, {10: {}, 20: {}}, all_conditions)
        assert state1.current_hp == 20
        assert state1.get_stacks("poison") == 4
        assert not result.is_duel_over

        # Turn 2: 20 HP - 10 = 10 HP, 4 -> 3 stacks
        context.current_turn = 2
        state1.reset_turn_modifiers()
        state2.reset_turn_modifiers()
        result = self.resolver.resolve_turn(context, actions, world_rules, {10: {}, 20: {}}, all_conditions)
        assert state1.current_hp == 10
        assert state1.get_stacks("poison") == 3
        assert not result.is_duel_over

        # Turn 3: 10 HP - 10 = 0 HP, player 1 dies
        context.current_turn = 3
        state1.reset_turn_modifiers()
        state2.reset_turn_modifiers()
        result = self.resolver.resolve_turn(context, actions, world_rules, {10: {}, 20: {}}, all_conditions)
        assert state1.current_hp == 0
        assert result.is_duel_over
        assert result.winner_participant_id == 20  # Player 2 wins

    def test_poison_expires_before_kill(self):
        """Test that poison expires (all stacks removed) before killing."""
        state1 = self._create_combat_state(1, 10, hp=100, stacks={"poison": 2})
        state2 = self._create_combat_state(2, 20)

        # Poison: 5 damage per turn, decays 1 stack per turn
        world_rules = [
            EffectData(
                id=1,
                name="poison_tick",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [101, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 5},
                owner_participant_id=0,
            ),
            EffectData(
                id=2,
                name="poison_decay",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [103, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="remove_stacks",
                action_data={"attribute": "poison", "value": 1},
                owner_participant_id=0,
            ),
        ]

        all_conditions = {
            101: (ConditionType.PHASE, {"phase": "pre_move"}),
            102: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
            103: (ConditionType.PHASE, {"phase": "post_move"}),
        }

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        # Turn 1: 100 - 5 = 95 HP, 2 -> 1 stacks
        context = self._create_context(state1, state2, turn=1)
        self.resolver.resolve_turn(context, actions, world_rules, {10: {}, 20: {}}, all_conditions)
        assert state1.current_hp == 95
        assert state1.get_stacks("poison") == 1

        # Turn 2: 95 - 5 = 90 HP, 1 -> 0 stacks (poison expires)
        context.current_turn = 2
        state1.reset_turn_modifiers()
        state2.reset_turn_modifiers()
        self.resolver.resolve_turn(context, actions, world_rules, {10: {}, 20: {}}, all_conditions)
        assert state1.current_hp == 90
        assert state1.get_stacks("poison") == 0

        # Turn 3: No poison, no damage
        context.current_turn = 3
        state1.reset_turn_modifiers()
        state2.reset_turn_modifiers()
        self.resolver.resolve_turn(context, actions, world_rules, {10: {}, 20: {}}, all_conditions)
        assert state1.current_hp == 90  # No change
        assert state1.get_stacks("poison") == 0

    def test_both_players_take_damage_over_turns(self):
        """Test both players taking poison damage over multiple turns."""
        state1 = self._create_combat_state(1, 10, hp=50, stacks={"poison": 3})
        state2 = self._create_combat_state(2, 20, hp=40, stacks={"poison": 2})

        world_rules = [
            EffectData(
                id=1,
                name="poison_tick",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [101, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 10},
                owner_participant_id=0,
            ),
            EffectData(
                id=2,
                name="poison_decay",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [103, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="remove_stacks",
                action_data={"attribute": "poison", "value": 1},
                owner_participant_id=0,
            ),
        ]

        all_conditions = {
            101: (ConditionType.PHASE, {"phase": "pre_move"}),
            102: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
            103: (ConditionType.PHASE, {"phase": "post_move"}),
        }

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        # Turn 1
        context = self._create_context(state1, state2, turn=1)
        result = self.resolver.resolve_turn(context, actions, world_rules, {10: {}, 20: {}}, all_conditions)
        assert state1.current_hp == 40  # 50 - 10
        assert state1.get_stacks("poison") == 2
        assert state2.current_hp == 30  # 40 - 10
        assert state2.get_stacks("poison") == 1
        assert not result.is_duel_over

        # Turn 2
        context.current_turn = 2
        state1.reset_turn_modifiers()
        state2.reset_turn_modifiers()
        result = self.resolver.resolve_turn(context, actions, world_rules, {10: {}, 20: {}}, all_conditions)
        assert state1.current_hp == 30  # 40 - 10
        assert state1.get_stacks("poison") == 1
        assert state2.current_hp == 20  # 30 - 10
        assert state2.get_stacks("poison") == 0
        assert not result.is_duel_over

        # Turn 3 - Player 2's poison expired
        context.current_turn = 3
        state1.reset_turn_modifiers()
        state2.reset_turn_modifiers()
        result = self.resolver.resolve_turn(context, actions, world_rules, {10: {}, 20: {}}, all_conditions)
        assert state1.current_hp == 20  # 30 - 10
        assert state1.get_stacks("poison") == 0
        assert state2.current_hp == 20  # No damage (poison expired)
        assert not result.is_duel_over

    def test_stacking_buffs_over_turns(self):
        """Test buffs accumulating over multiple turns."""
        state1 = self._create_combat_state(1, 10, stacks={"might": 1})
        state2 = self._create_combat_state(2, 20)

        # Each turn, gain 1 might stack (up to max 5)
        world_rules = [
            EffectData(
                id=1,
                name="might_gain",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "pre_move"},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="add_stacks",
                action_data={"attribute": "might", "value": 1, "max_stacks": 5},
                owner_participant_id=0,
            ),
        ]

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        context = self._create_context(state1, state2, turn=1)

        # Simulate 6 turns
        for turn in range(1, 7):
            context.current_turn = turn
            state1.reset_turn_modifiers()
            state2.reset_turn_modifiers()
            self.resolver.resolve_turn(context, actions, world_rules, {10: {}, 20: {}}, None)

        # Both players should have 5 might (capped)
        assert state1.get_stacks("might") == 5
        assert state2.get_stacks("might") == 5

    def test_full_duel_simulation(self):
        """Simulate a complete duel with poison and damage over time."""
        # Player 1 starts with 3 poison, Player 2 starts healthy
        # Poison deals 15 damage/turn and decays 1 stack/turn
        # Player 1 should die on turn 4 (100 -> 85 -> 70 -> 55 -> 40 -> dies at 25)
        state1 = self._create_combat_state(1, 10, hp=60, stacks={"poison": 4})
        state2 = self._create_combat_state(2, 20, hp=100)

        world_rules = [
            EffectData(
                id=1,
                name="poison_tick",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [101, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 15},
                owner_participant_id=0,
            ),
            EffectData(
                id=2,
                name="poison_decay",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [103, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="remove_stacks",
                action_data={"attribute": "poison", "value": 1},
                owner_participant_id=0,
            ),
        ]

        all_conditions = {
            101: (ConditionType.PHASE, {"phase": "pre_move"}),
            102: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
            103: (ConditionType.PHASE, {"phase": "post_move"}),
        }

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        context = self._create_context(state1, state2, turn=1)
        turn_count = 0
        max_turns = 10  # Safety limit

        while turn_count < max_turns:
            turn_count += 1
            context.current_turn = turn_count
            state1.reset_turn_modifiers()
            state2.reset_turn_modifiers()

            result = self.resolver.resolve_turn(context, actions, world_rules, {10: {}, 20: {}}, all_conditions)

            if result.is_duel_over:
                break

        # Player 1 should have died from poison
        # Turn 1: 60 - 15 = 45, stacks 4->3
        # Turn 2: 45 - 15 = 30, stacks 3->2
        # Turn 3: 30 - 15 = 15, stacks 2->1
        # Turn 4: 15 - 15 = 0, dies
        assert result.is_duel_over
        assert result.winner_participant_id == 20
        assert state1.current_hp == 0
        assert turn_count == 4

    def test_mutual_kill_scenario(self):
        """Test scenario where both players would die on same turn."""
        state1 = self._create_combat_state(1, 10, hp=10, stacks={"poison": 1})
        state2 = self._create_combat_state(2, 20, hp=10, stacks={"poison": 1})

        world_rules = [
            EffectData(
                id=1,
                name="poison_tick",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [101, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 10},
                owner_participant_id=0,
            ),
        ]

        all_conditions = {
            101: (ConditionType.PHASE, {"phase": "pre_move"}),
            102: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
        }

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        context = self._create_context(state1, state2, turn=1)
        result = self.resolver.resolve_turn(context, actions, world_rules, {10: {}, 20: {}}, all_conditions)

        # Both players die simultaneously
        assert state1.current_hp == 0
        assert state2.current_hp == 0
        # Current implementation returns None for draws
        assert result.winner_participant_id is None


class TestDefenseItemWithArmor:
    """Tests for defense items adding armor and world rules reducing damage.

    This tests the full combat flow:
    1. Player uses DEFENSE action
    2. Defense item adds armor stacks at PRE_ATTACK
    3. Enemy attack deals damage, triggering PRE_DAMAGE interrupt
    4. Armor world rule converts stacks to damage reduction
    """

    def setup_method(self):
        """Set up test fixtures."""
        from vaudeville_rpg.db.models.enums import ItemSlot
        from vaudeville_rpg.engine.turn import ItemData

        self.resolver = TurnResolver()
        self.ItemSlot = ItemSlot
        self.ItemData = ItemData

    def _create_combat_state(
        self,
        player_id: int,
        participant_id: int,
        hp: int = 100,
        stacks: dict | None = None,
        display_name: str = "",
    ) -> CombatState:
        """Helper to create combat state."""
        return CombatState(
            player_id=player_id,
            participant_id=participant_id,
            current_hp=hp,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks=stacks.copy() if stacks else {},
            display_name=display_name or f"Player{player_id}",
        )

    def _create_context(
        self,
        state1: CombatState,
        state2: CombatState,
        turn: int = 1,
    ) -> DuelContext:
        """Helper to create duel context."""
        return DuelContext(
            duel_id=1,
            setting_id=1,
            current_turn=turn,
            states={state1.participant_id: state1, state2.participant_id: state2},
        )

    def test_defense_item_adds_armor_before_attack_damage(self):
        """Test that defense item adds armor at PRE_ATTACK, before attack damage triggers PRE_DAMAGE."""
        # Player 1 (attacker): 100 HP
        # Player 2 (defender): 100 HP, will use defense
        state1 = self._create_combat_state(1, 10, hp=100, display_name="Attacker")
        state2 = self._create_combat_state(2, 20, hp=100, display_name="Defender")
        context = self._create_context(state1, state2)

        # Attack item effect: deals 20 damage at PRE_ATTACK
        attack_item_effect = EffectData(
            id=1,
            name="sword_attack",
            condition_type=ConditionType.PHASE,
            condition_data={"phase": "pre_attack"},
            target=TargetType.ENEMY,
            category=EffectCategory.ITEM_EFFECT,
            action_type="attack",
            action_data={"value": 20},
            owner_participant_id=10,
            item_name="Sword",
        )

        # Defense item effect: adds 3 armor stacks at PRE_ATTACK
        # This is the fix - defense items now trigger at PRE_ATTACK, not PRE_DAMAGE
        defense_item_effect = EffectData(
            id=2,
            name="shield_armor",
            condition_type=ConditionType.PHASE,
            condition_data={"phase": "pre_attack"},
            target=TargetType.SELF,
            category=EffectCategory.ITEM_EFFECT,
            action_type="add_stacks",
            action_data={"value": 3, "attribute": "armor"},
            owner_participant_id=20,
            item_name="Shield",
        )

        # Armor world rule: reduces incoming damage at PRE_DAMAGE
        armor_reduction_rule = EffectData(
            id=3,
            name="armor_reduction",
            condition_type=ConditionType.AND,
            condition_data={"condition_ids": [101, 102]},
            target=TargetType.SELF,
            category=EffectCategory.WORLD_RULE,
            action_type="reduce_incoming_damage",
            action_data={"value": 2, "per_stack": True, "attribute": "armor"},
            owner_participant_id=0,  # World rules apply to everyone
        )

        # Create items
        attack_item = self.ItemData(
            id=1,
            name="Sword",
            slot=self.ItemSlot.ATTACK,
            effects=[attack_item_effect],
        )

        defense_item = self.ItemData(
            id=2,
            name="Shield",
            slot=self.ItemSlot.DEFENSE,
            effects=[defense_item_effect],
        )

        # Player items
        participant_items = {
            10: {self.ItemSlot.ATTACK: attack_item},
            20: {self.ItemSlot.DEFENSE: defense_item},
        }

        # World rules with armor_reduction
        world_rules = [armor_reduction_rule]

        # Conditions for AND resolution
        all_conditions = {
            101: (ConditionType.PHASE, {"phase": "pre_damage"}),
            102: (ConditionType.HAS_STACKS, {"attribute": "armor", "min_count": 1}),
        }

        # Actions: Player 1 attacks, Player 2 defends
        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.ATTACK),
            ParticipantAction(participant_id=20, action_type=DuelActionType.DEFENSE),
        ]

        # Resolve combat
        result = self.resolver.resolve_turn(context, actions, world_rules, participant_items, all_conditions)

        # Verify:
        # 1. Player 2 should have armor stacks (added at PRE_ATTACK by defense item)
        assert state2.get_stacks("armor") == 3, f"Expected 3 armor stacks, got {state2.get_stacks('armor')}"

        # 2. Player 2 should have taken reduced damage:
        #    - Attack: 20 damage
        #    - Armor reduction: 3 stacks * 2 = 6 reduction
        #    - Actual damage: 20 - 6 = 14
        #    - HP: 100 - 14 = 86
        assert state2.current_hp == 86, f"Expected 86 HP after armor reduction, got {state2.current_hp}"

        # 3. Player 1 should be unaffected
        assert state1.current_hp == 100

    def test_defense_without_armor_world_rule(self):
        """Test that defense item adds armor stacks even without a world rule to use them."""
        state1 = self._create_combat_state(1, 10, hp=100, display_name="Attacker")
        state2 = self._create_combat_state(2, 20, hp=100, display_name="Defender")
        context = self._create_context(state1, state2)

        # Attack item effect: deals 20 damage
        attack_item_effect = EffectData(
            id=1,
            name="sword_attack",
            condition_type=ConditionType.PHASE,
            condition_data={"phase": "pre_attack"},
            target=TargetType.ENEMY,
            category=EffectCategory.ITEM_EFFECT,
            action_type="attack",
            action_data={"value": 20},
            owner_participant_id=10,
            item_name="Sword",
        )

        # Defense item effect: adds 3 armor stacks at PRE_ATTACK
        defense_item_effect = EffectData(
            id=2,
            name="shield_armor",
            condition_type=ConditionType.PHASE,
            condition_data={"phase": "pre_attack"},
            target=TargetType.SELF,
            category=EffectCategory.ITEM_EFFECT,
            action_type="add_stacks",
            action_data={"value": 3, "attribute": "armor"},
            owner_participant_id=20,
            item_name="Shield",
        )

        # Create items
        attack_item = self.ItemData(
            id=1,
            name="Sword",
            slot=self.ItemSlot.ATTACK,
            effects=[attack_item_effect],
        )

        defense_item = self.ItemData(
            id=2,
            name="Shield",
            slot=self.ItemSlot.DEFENSE,
            effects=[defense_item_effect],
        )

        participant_items = {
            10: {self.ItemSlot.ATTACK: attack_item},
            20: {self.ItemSlot.DEFENSE: defense_item},
        }

        # No world rules (no armor reduction)
        world_rules = []

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.ATTACK),
            ParticipantAction(participant_id=20, action_type=DuelActionType.DEFENSE),
        ]

        result = self.resolver.resolve_turn(context, actions, world_rules, participant_items, {})

        # Armor stacks added but no reduction (no world rule)
        assert state2.get_stacks("armor") == 3
        # Full damage taken (no reduction)
        assert state2.current_hp == 80  # 100 - 20 = 80

    def test_attack_vs_attack_no_defense(self):
        """Test that without defense action, no armor is added."""
        state1 = self._create_combat_state(1, 10, hp=100, display_name="Attacker1")
        state2 = self._create_combat_state(2, 20, hp=100, display_name="Attacker2")
        context = self._create_context(state1, state2)

        # Both players have attack items
        attack1_effect = EffectData(
            id=1,
            name="sword_attack_1",
            condition_type=ConditionType.PHASE,
            condition_data={"phase": "pre_attack"},
            target=TargetType.ENEMY,
            category=EffectCategory.ITEM_EFFECT,
            action_type="attack",
            action_data={"value": 15},
            owner_participant_id=10,
            item_name="Sword",
        )

        attack2_effect = EffectData(
            id=2,
            name="sword_attack_2",
            condition_type=ConditionType.PHASE,
            condition_data={"phase": "pre_attack"},
            target=TargetType.ENEMY,
            category=EffectCategory.ITEM_EFFECT,
            action_type="attack",
            action_data={"value": 10},
            owner_participant_id=20,
            item_name="Dagger",
        )

        attack_item_1 = self.ItemData(
            id=1,
            name="Sword",
            slot=self.ItemSlot.ATTACK,
            effects=[attack1_effect],
        )

        attack_item_2 = self.ItemData(
            id=2,
            name="Dagger",
            slot=self.ItemSlot.ATTACK,
            effects=[attack2_effect],
        )

        participant_items = {
            10: {self.ItemSlot.ATTACK: attack_item_1},
            20: {self.ItemSlot.ATTACK: attack_item_2},
        }

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.ATTACK),
            ParticipantAction(participant_id=20, action_type=DuelActionType.ATTACK),
        ]

        result = self.resolver.resolve_turn(context, actions, [], participant_items, {})

        # Both players take full damage
        assert state1.current_hp == 90  # 100 - 10
        assert state2.current_hp == 85  # 100 - 15
        # No armor stacks on either player
        assert state1.get_stacks("armor") == 0
        assert state2.get_stacks("armor") == 0
