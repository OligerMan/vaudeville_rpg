"""Tests for fresh stacks decay protection."""

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
from vaudeville_rpg.engine.effects import EffectData, EffectProcessor
from vaudeville_rpg.engine.turn import ParticipantAction, TurnResolver, ItemData
from vaudeville_rpg.engine.types import ActionContext, CombatState, DuelContext


class TestFreshStacksTracking:
    """Tests for fresh_stacks field in CombatState."""

    def test_fresh_stacks_initially_empty(self):
        """Fresh stacks should be empty on new CombatState."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        assert state.fresh_stacks == {}

    def test_add_stacks_tracks_fresh(self):
        """Adding stacks should track them as fresh."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        state.add_stacks("poison", 3)
        assert state.get_stacks("poison") == 3
        assert state.fresh_stacks.get("poison", 0) == 3

    def test_add_stacks_accumulates_fresh(self):
        """Multiple add_stacks calls should accumulate fresh count."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        state.add_stacks("poison", 2)
        state.add_stacks("poison", 3)
        assert state.get_stacks("poison") == 5
        assert state.fresh_stacks.get("poison", 0) == 5

    def test_add_stacks_with_max_tracks_actual(self):
        """Fresh stacks should only track actually added stacks."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        # Try to add 10 but max is 3
        state.add_stacks("armor", 10, max_stacks=3)
        assert state.get_stacks("armor") == 3
        assert state.fresh_stacks.get("armor", 0) == 3

    def test_reset_turn_modifiers_clears_fresh(self):
        """reset_turn_modifiers should clear fresh_stacks."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        state.add_stacks("poison", 3)
        state.add_stacks("armor", 2)
        assert state.fresh_stacks == {"poison": 3, "armor": 2}

        state.reset_turn_modifiers()
        assert state.fresh_stacks == {}
        # Original stacks should remain
        assert state.get_stacks("poison") == 3
        assert state.get_stacks("armor") == 2


class TestDecayProtection:
    """Tests for decay protection of fresh stacks at POST_MOVE."""

    def create_state(self, **kwargs):
        """Helper to create a CombatState."""
        defaults = {
            "player_id": 1,
            "participant_id": 10,
            "current_hp": 100,
            "max_hp": 100,
            "current_special_points": 50,
            "max_special_points": 50,
        }
        defaults.update(kwargs)
        return CombatState(**defaults)

    def test_decay_at_post_move_skips_fresh_stacks(self):
        """At POST_MOVE, decay should skip fresh stacks."""
        state = self.create_state()
        state.add_stacks("poison", 3)  # All 3 are fresh

        executor = ActionExecutor()
        context = ActionContext(
            source_participant_id=10,
            source_state=state,
            target_state=state,
            action_data={"attribute": "poison", "value": 1},
            phase=ConditionPhase.POST_MOVE,
        )

        result = executor._execute_remove_stacks(
            {"attribute": "poison", "value": 1},
            context,
            "test_decay",
        )

        # Should not remove anything - all stacks are fresh
        assert result.value == 0
        assert state.get_stacks("poison") == 3

    def test_decay_at_post_move_removes_old_stacks(self):
        """At POST_MOVE, decay should remove non-fresh stacks."""
        state = self.create_state(attribute_stacks={"poison": 2})
        # Add 1 fresh stack on top of 2 old
        state.add_stacks("poison", 1)

        executor = ActionExecutor()
        context = ActionContext(
            source_participant_id=10,
            source_state=state,
            target_state=state,
            action_data={"attribute": "poison", "value": 1},
            phase=ConditionPhase.POST_MOVE,
        )

        result = executor._execute_remove_stacks(
            {"attribute": "poison", "value": 1},
            context,
            "test_decay",
        )

        # Should remove 1 old stack
        assert result.value == 1
        assert state.get_stacks("poison") == 2  # 2 old + 1 fresh - 1 = 2

    def test_decay_at_post_move_limited_by_old_stacks(self):
        """Decay should be limited to non-fresh stack count."""
        state = self.create_state(attribute_stacks={"poison": 2})
        state.add_stacks("poison", 3)  # 2 old + 3 fresh = 5 total

        executor = ActionExecutor()
        context = ActionContext(
            source_participant_id=10,
            source_state=state,
            target_state=state,
            action_data={"attribute": "poison", "value": 10},  # Try to remove 10
            phase=ConditionPhase.POST_MOVE,
        )

        result = executor._execute_remove_stacks(
            {"attribute": "poison", "value": 10},
            context,
            "test_decay",
        )

        # Should only remove 2 (the old stacks)
        assert result.value == 2
        assert state.get_stacks("poison") == 3  # Only fresh remain

    def test_remove_at_other_phase_ignores_fresh(self):
        """REMOVE_STACKS at non-POST_MOVE should remove any stacks."""
        state = self.create_state()
        state.add_stacks("poison", 3)  # All fresh

        executor = ActionExecutor()

        # Test at PRE_MOVE
        context = ActionContext(
            source_participant_id=10,
            source_state=state,
            target_state=state,
            action_data={"attribute": "poison", "value": 1},
            phase=ConditionPhase.PRE_MOVE,
        )

        result = executor._execute_remove_stacks(
            {"attribute": "poison", "value": 1},
            context,
            "test_cleanse",
        )

        # Should remove normally
        assert result.value == 1
        assert state.get_stacks("poison") == 2

    def test_remove_with_no_phase_ignores_fresh(self):
        """REMOVE_STACKS with None phase should remove any stacks."""
        state = self.create_state()
        state.add_stacks("poison", 3)  # All fresh

        executor = ActionExecutor()
        context = ActionContext(
            source_participant_id=10,
            source_state=state,
            target_state=state,
            action_data={"attribute": "poison", "value": 1},
            phase=None,  # No phase specified
        )

        result = executor._execute_remove_stacks(
            {"attribute": "poison", "value": 1},
            context,
            "test_cleanse",
        )

        # Should remove normally
        assert result.value == 1
        assert state.get_stacks("poison") == 2


class TestTurnFlowWithFreshStacks:
    """Integration tests for fresh stacks across turn phases."""

    def create_context(self, p1_stacks=None, p2_stacks=None):
        """Helper to create a DuelContext with two participants."""
        state1 = CombatState(
            player_id=1,
            participant_id=10,
            display_name="Player 1",
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks=p1_stacks or {},
        )
        state2 = CombatState(
            player_id=2,
            participant_id=20,
            display_name="Player 2",
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks=p2_stacks or {},
        )
        return DuelContext(
            duel_id=1,
            setting_id=1,
            current_turn=1,
            states={10: state1, 20: state2},
        )

    def test_full_turn_fresh_stacks_protected(self):
        """Stacks added during combat should not decay in same turn."""
        context = self.create_context()

        # Conditions for poison decay world rule
        all_conditions = {
            100: (ConditionType.PHASE, {"phase": "post_move"}),
            101: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
            102: (ConditionType.AND, {"condition_ids": [100, 101]}),
        }

        # World rule: decay poison at POST_MOVE
        decay_rule = EffectData(
            id=1,
            name="poison_decay",
            condition_type=ConditionType.AND,
            condition_data={"condition_ids": [100, 101]},
            target=TargetType.SELF,
            category=EffectCategory.WORLD_RULE,
            action_type=ActionType.REMOVE_STACKS.value,
            action_data={"attribute": "poison", "value": 1},
            owner_participant_id=10,
        )

        # Player 1 adds poison to self (simulating being poisoned this turn)
        context.states[10].add_stacks("poison", 1)
        assert context.states[10].get_stacks("poison") == 1
        assert context.states[10].fresh_stacks.get("poison", 0) == 1

        # Process POST_MOVE phase (decay should be blocked)
        processor = EffectProcessor()
        results = processor.process_phase(
            ConditionPhase.POST_MOVE,
            [decay_rule],
            context,
            all_conditions,
        )

        # Decay should not have removed the fresh stack
        assert context.states[10].get_stacks("poison") == 1

    def test_next_turn_stacks_decay_normally(self):
        """After turn reset, previously fresh stacks should decay normally."""
        context = self.create_context()

        all_conditions = {
            100: (ConditionType.PHASE, {"phase": "post_move"}),
            101: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
            102: (ConditionType.AND, {"condition_ids": [100, 101]}),
        }

        decay_rule = EffectData(
            id=1,
            name="poison_decay",
            condition_type=ConditionType.AND,
            condition_data={"condition_ids": [100, 101]},
            target=TargetType.SELF,
            category=EffectCategory.WORLD_RULE,
            action_type=ActionType.REMOVE_STACKS.value,
            action_data={"attribute": "poison", "value": 1},
            owner_participant_id=10,
        )

        # Add poison as fresh
        context.states[10].add_stacks("poison", 2)

        # Simulate end of turn - clear fresh stacks
        context.states[10].reset_turn_modifiers()

        # Now POST_MOVE should decay normally
        processor = EffectProcessor()
        results = processor.process_phase(
            ConditionPhase.POST_MOVE,
            [decay_rule],
            context,
            all_conditions,
        )

        # Should have removed 1 stack
        assert context.states[10].get_stacks("poison") == 1


class TestMultipleAttributes:
    """Tests for fresh stacks with multiple attributes."""

    def test_fresh_stacks_tracked_per_attribute(self):
        """Each attribute should track its own fresh stacks."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks={"armor": 2},  # 2 old armor
        )

        # Add fresh stacks to different attributes
        state.add_stacks("poison", 3)
        state.add_stacks("armor", 1)  # 1 fresh on top of 2 old

        assert state.fresh_stacks == {"poison": 3, "armor": 1}
        assert state.get_stacks("poison") == 3
        assert state.get_stacks("armor") == 3

    def test_decay_respects_per_attribute_freshness(self):
        """Decay should check freshness per attribute."""
        state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks={"poison": 2},  # 2 old poison
        )

        # Add fresh armor but not poison
        state.add_stacks("armor", 3)

        executor = ActionExecutor()

        # Decay poison at POST_MOVE (should work - no fresh poison)
        context_poison = ActionContext(
            source_participant_id=10,
            source_state=state,
            target_state=state,
            action_data={"attribute": "poison", "value": 1},
            phase=ConditionPhase.POST_MOVE,
        )
        result_poison = executor._execute_remove_stacks(
            {"attribute": "poison", "value": 1},
            context_poison,
            "poison_decay",
        )
        assert result_poison.value == 1  # Removed 1 old poison

        # Decay armor at POST_MOVE (should be blocked - all fresh)
        context_armor = ActionContext(
            source_participant_id=10,
            source_state=state,
            target_state=state,
            action_data={"attribute": "armor", "value": 1},
            phase=ConditionPhase.POST_MOVE,
        )
        result_armor = executor._execute_remove_stacks(
            {"attribute": "armor", "value": 1},
            context_armor,
            "armor_decay",
        )
        assert result_armor.value == 0  # No decay - all fresh
