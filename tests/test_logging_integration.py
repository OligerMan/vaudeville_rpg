"""Integration test for combat logging - plays a full duel and verifies log output."""

from vaudeville_rpg.db.models.enums import (
    ConditionPhase,
    ConditionType,
    DuelActionType,
    EffectCategory,
    TargetType,
)
from vaudeville_rpg.engine.effects import EffectData
from vaudeville_rpg.engine.logging import CombatLogger, LogEventType
from vaudeville_rpg.engine.turn import ParticipantAction, TurnResolver
from vaudeville_rpg.engine.types import CombatState, DuelContext


class TestFullDuelWithLogging:
    """Integration test: Play a complete duel and verify all logging output."""

    def setup_method(self):
        """Set up test fixtures for a full duel scenario.

        Scenario: Two players fight with poison mechanics.
        - Player 1 (Knight): 100 HP, starts with 2 armor stacks
        - Player 2 (Rogue): 80 HP, starts with 3 poison stacks on self (from previous effect)

        World Rules:
        - Poison tick: At PRE_MOVE, if has poison, deal 15 damage to self
        - Poison decay: At POST_MOVE, if has poison, remove 1 stack
        - Armor reduction: At PRE_DAMAGE, if has armor, reduce incoming damage by 5 per stack
        - Armor decay: At POST_DAMAGE, if has armor, remove 1 stack
        """
        self.logger = CombatLogger(duel_id=1)
        self.resolver = TurnResolver(logger=self.logger)

        # Player 1: Knight with armor
        self.knight = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks={"armor": 2},
        )

        # Player 2: Rogue with poison (self-inflicted from previous turn)
        self.rogue = CombatState(
            player_id=2,
            participant_id=20,
            current_hp=80,
            max_hp=80,
            current_special_points=30,
            max_special_points=30,
            attribute_stacks={"poison": 3},
        )

        # World rules
        self.world_rules = [
            # Poison tick - alphabetically first with 'a_' prefix
            EffectData(
                id=1,
                name="a_poison_tick",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [101, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 15},
                owner_participant_id=0,
            ),
            # Poison decay
            EffectData(
                id=2,
                name="b_poison_decay",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [103, 102]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="remove_stacks",
                action_data={"attribute": "poison", "value": 1},
                owner_participant_id=0,
            ),
            # Armor reduction
            EffectData(
                id=3,
                name="c_armor_reduction",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [104, 105]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="reduce_incoming_damage",
                action_data={"value": 5},
                owner_participant_id=0,
            ),
            # Armor decay
            EffectData(
                id=4,
                name="d_armor_decay",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [106, 105]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="remove_stacks",
                action_data={"attribute": "armor", "value": 1},
                owner_participant_id=0,
            ),
        ]

        # Conditions for AND resolution
        self.all_conditions = {
            101: (ConditionType.PHASE, {"phase": "pre_move"}),
            102: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
            103: (ConditionType.PHASE, {"phase": "post_move"}),
            104: (ConditionType.PHASE, {"phase": "pre_damage"}),
            105: (ConditionType.HAS_STACKS, {"attribute": "armor", "min_count": 1}),
            106: (ConditionType.PHASE, {"phase": "post_damage"}),
        }

        # Both players skip (no items)
        self.actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

    def _create_context(self, turn: int = 1) -> DuelContext:
        """Create a duel context for the current turn."""
        return DuelContext(
            duel_id=1,
            setting_id=1,
            current_turn=turn,
            states={10: self.knight, 20: self.rogue},
        )

    def _reset_turn_modifiers(self):
        """Reset turn modifiers for both players."""
        self.knight.reset_turn_modifiers()
        self.rogue.reset_turn_modifiers()

    def test_full_duel_until_death(self):
        """Play a full duel until someone dies, verify all logging."""
        # The rogue has 80 HP and takes 15 poison damage per turn
        # Turn 1: 80 - 15 = 65 HP, poison 3 -> 2
        # Turn 2: 65 - 15 = 50 HP, poison 2 -> 1
        # Turn 3: 50 - 15 = 35 HP, poison 1 -> 0
        # Turn 4: No poison, no damage
        # Turn 5: Still alive

        # But we want a death - let's set rogue HP lower
        self.rogue.current_hp = 40

        # Now:
        # Turn 1: 40 - 15 = 25 HP, poison 3 -> 2
        # Turn 2: 25 - 15 = 10 HP, poison 2 -> 1
        # Turn 3: 10 - 15 = 0 HP (capped), rogue dies

        context = self._create_context(turn=1)
        duel_over = False
        turn_count = 0
        max_turns = 5

        while not duel_over and turn_count < max_turns:
            turn_count += 1
            context.current_turn = turn_count

            if turn_count > 1:
                self._reset_turn_modifiers()

            result = self.resolver.resolve_turn(
                context,
                self.actions,
                world_rules=self.world_rules,
                participant_items={10: {}, 20: {}},
                all_conditions=self.all_conditions,
            )

            duel_over = result.is_duel_over

        # Verify duel ended with knight winning
        assert duel_over, "Duel should have ended"
        assert result.winner_participant_id == 10, "Knight should win"
        assert self.rogue.current_hp == 0, "Rogue should be dead"
        assert turn_count == 3, f"Should take 3 turns, took {turn_count}"

        # Get the complete log
        log = self.logger.get_log()

        # Verify log structure
        self._verify_log_structure(log, expected_turns=3)

        # Verify specific events
        self._verify_turn_events(log)
        self._verify_phase_events(log)
        self._verify_effect_evaluations(log)
        self._verify_action_executions(log)
        self._verify_winner_logged(log)

    def _verify_log_structure(self, log, expected_turns: int):
        """Verify basic log structure."""
        assert log.duel_id == 1, "Log should have correct duel ID"
        assert len(log.entries) > 0, "Log should have entries"

        # Should have turn start/end for each turn
        turn_starts = log.get_entries_by_type(LogEventType.TURN_START)
        turn_ends = log.get_entries_by_type(LogEventType.TURN_END)

        assert len(turn_starts) == expected_turns, f"Should have {expected_turns} turn starts"
        assert len(turn_ends) == expected_turns, f"Should have {expected_turns} turn ends"

    def _verify_turn_events(self, log):
        """Verify turn start/end events have state snapshots."""
        turn_starts = log.get_entries_by_type(LogEventType.TURN_START)

        for entry in turn_starts:
            assert entry.all_states is not None, "Turn start should have state snapshot"
            assert 10 in entry.all_states, "Knight state should be in snapshot"
            assert 20 in entry.all_states, "Rogue state should be in snapshot"

        # Verify first turn start has correct initial state
        first_turn = turn_starts[0]
        knight_state = first_turn.all_states[10]
        rogue_state = first_turn.all_states[20]

        assert knight_state.current_hp == 100, "Knight should start with 100 HP"
        assert knight_state.attribute_stacks.get("armor") == 2, "Knight should have 2 armor"
        assert rogue_state.current_hp == 40, "Rogue should start with 40 HP"
        assert rogue_state.attribute_stacks.get("poison") == 3, "Rogue should have 3 poison"

    def _verify_phase_events(self, log):
        """Verify all phases are logged correctly."""
        phase_starts = log.get_entries_by_type(LogEventType.PHASE_START)

        # Each turn should have 6 phases (PRE_MOVE, PRE_ATTACK, POST_ATTACK, PRE_DAMAGE, POST_DAMAGE, POST_MOVE)
        # But the last turn ends early (at PRE_MOVE death check), so we need to account for that

        # At minimum, should have PRE_MOVE for all 3 turns
        pre_move_starts = [e for e in phase_starts if e.phase == ConditionPhase.PRE_MOVE]
        assert len(pre_move_starts) >= 3, "Should have PRE_MOVE for each turn"

        # Verify phases are logged in order for turn 1
        turn_1_phases = [e for e in phase_starts if e.turn_number == 1]
        phase_order = [e.phase for e in turn_1_phases]

        # Note: PRE_DAMAGE and POST_DAMAGE are now interrupt phases, not sequential
        # They fire within damage events, not as separate phases
        expected_order = [
            ConditionPhase.PRE_MOVE,
            ConditionPhase.PRE_ATTACK,
            ConditionPhase.POST_ATTACK,
            ConditionPhase.POST_MOVE,
        ]

        assert phase_order == expected_order, f"Phase order should be {expected_order}, got {phase_order}"

    def _verify_effect_evaluations(self, log):
        """Verify effect condition evaluations are logged."""
        evaluations = log.get_entries_by_type(LogEventType.EFFECT_EVALUATED)

        assert len(evaluations) > 0, "Should have effect evaluations"

        # Find poison tick evaluations
        poison_evals = [e for e in evaluations if e.effect_name == "a_poison_tick"]
        assert len(poison_evals) > 0, "Should have poison tick evaluations"

        # Rogue should have poison tick evaluate to True (has poison stacks)
        rogue_poison_evals = [e for e in poison_evals if e.participant_id == 20]
        assert len(rogue_poison_evals) > 0, "Rogue should have poison tick evaluations"

        # At least in turn 1, rogue's poison should evaluate to True
        turn_1_rogue_poison = [e for e in rogue_poison_evals if e.turn_number == 1]
        assert len(turn_1_rogue_poison) > 0, "Rogue should have turn 1 poison eval"
        assert turn_1_rogue_poison[0].condition_result is True, "Rogue poison should trigger"

        # Knight should have poison tick evaluate to False (no poison stacks)
        knight_poison_evals = [e for e in poison_evals if e.participant_id == 10]
        if len(knight_poison_evals) > 0:
            assert knight_poison_evals[0].condition_result is False, "Knight has no poison"

    def _verify_action_executions(self, log):
        """Verify action executions are logged with state changes."""
        executions = log.get_entries_by_type(LogEventType.ACTION_EXECUTED)

        assert len(executions) > 0, "Should have action executions"

        # Find poison tick damage executions
        poison_damage = [e for e in executions if e.effect_name == "a_poison_tick"]
        assert len(poison_damage) > 0, "Should have poison damage executions"

        # Verify rogue took poison damage in turn 1
        turn_1_poison = [e for e in poison_damage if e.turn_number == 1]
        assert len(turn_1_poison) >= 1, "Should have turn 1 poison damage"

        # Rogue's poison damage should show HP change
        rogue_poison = [e for e in turn_1_poison if e.target_participant_id == 20]
        assert len(rogue_poison) == 1, "Rogue should take poison damage in turn 1"

        poison_entry = rogue_poison[0]
        assert poison_entry.value == 15, "Poison should deal 15 damage"
        assert poison_entry.state_before is not None, "Should have state before"
        assert poison_entry.state_after is not None, "Should have state after"
        assert poison_entry.state_before.current_hp == 40, "Rogue started at 40 HP"
        assert poison_entry.state_after.current_hp == 25, "Rogue should be at 25 HP after"

        # Find poison decay executions
        poison_decay = [e for e in executions if e.effect_name == "b_poison_decay"]
        assert len(poison_decay) > 0, "Should have poison decay executions"

        # Verify stacks decreased
        turn_1_decay = [e for e in poison_decay if e.turn_number == 1 and e.target_participant_id == 20]
        if len(turn_1_decay) > 0:
            decay_entry = turn_1_decay[0]
            assert decay_entry.state_before.attribute_stacks.get("poison") == 3
            assert decay_entry.state_after.attribute_stacks.get("poison") == 2

    def _verify_winner_logged(self, log):
        """Verify winner determination is logged."""
        winner_entries = log.get_entries_by_type(LogEventType.WINNER_DETERMINED)

        assert len(winner_entries) == 1, "Should have exactly one winner entry"
        assert winner_entries[0].winner_participant_id == 10, "Knight should be winner"
        assert winner_entries[0].turn_number == 3, "Winner should be determined on turn 3"

    def test_log_format_readable(self):
        """Test that log produces readable output."""
        # Play one turn
        context = self._create_context(turn=1)
        self.resolver.resolve_turn(
            context,
            self.actions,
            world_rules=self.world_rules,
            participant_items={10: {}, 20: {}},
            all_conditions=self.all_conditions,
        )

        log = self.logger.get_log()
        output = log.format_readable()

        # Verify output contains key information
        assert "Combat Log (Duel #1)" in output
        assert "Turn 1" in output
        assert "PRE_MOVE" in output
        assert "a_poison_tick" in output
        assert "15" in output  # Damage value

    def test_log_to_dict_serializable(self):
        """Test that log can be serialized to dict."""
        # Play one turn
        context = self._create_context(turn=1)
        self.resolver.resolve_turn(
            context,
            self.actions,
            world_rules=self.world_rules,
            participant_items={10: {}, 20: {}},
            all_conditions=self.all_conditions,
        )

        log = self.logger.get_log()
        data = log.to_dict()

        # Verify dict structure
        assert "duel_id" in data
        assert data["duel_id"] == 1
        assert "entries" in data
        assert len(data["entries"]) > 0

        # Verify entries are serialized
        first_entry = data["entries"][0]
        assert "event_type" in first_entry
        assert "turn_number" in first_entry

    def test_state_changes_tracked_across_turns(self):
        """Verify state changes are correctly tracked across multiple turns."""
        self.rogue.current_hp = 100  # Give rogue more HP to survive

        # Play 2 turns
        for turn in range(1, 3):
            context = self._create_context(turn=turn)
            if turn > 1:
                self._reset_turn_modifiers()

            self.resolver.resolve_turn(
                context,
                self.actions,
                world_rules=self.world_rules,
                participant_items={10: {}, 20: {}},
                all_conditions=self.all_conditions,
            )

        log = self.logger.get_log()

        # Get turn end snapshots
        turn_ends = log.get_entries_by_type(LogEventType.TURN_END)

        # Turn 1 end: Rogue should be at 85 HP (100 - 15), poison 2
        turn_1_end = [e for e in turn_ends if e.turn_number == 1][0]
        rogue_t1 = turn_1_end.all_states[20]
        assert rogue_t1.current_hp == 85, f"Rogue should be at 85 HP after turn 1, got {rogue_t1.current_hp}"
        assert rogue_t1.attribute_stacks.get("poison") == 2, "Rogue should have 2 poison after turn 1"

        # Turn 2 end: Rogue should be at 70 HP (85 - 15), poison 1
        turn_2_end = [e for e in turn_ends if e.turn_number == 2][0]
        rogue_t2 = turn_2_end.all_states[20]
        assert rogue_t2.current_hp == 70, f"Rogue should be at 70 HP after turn 2, got {rogue_t2.current_hp}"
        assert rogue_t2.attribute_stacks.get("poison") == 1, "Rogue should have 1 poison after turn 2"

        # Knight should still have armor decaying
        knight_t1 = turn_1_end.all_states[10]
        knight_t2 = turn_2_end.all_states[10]
        assert knight_t1.attribute_stacks.get("armor") == 1, "Knight should have 1 armor after turn 1"
        # When stacks reach 0, the attribute is removed from the dict
        assert knight_t2.attribute_stacks.get("armor", 0) == 0, "Knight should have 0 armor after turn 2"

    def test_alphabetical_effect_ordering(self):
        """Verify effects are processed in alphabetical order."""
        context = self._create_context(turn=1)
        self.resolver.resolve_turn(
            context,
            self.actions,
            world_rules=self.world_rules,
            participant_items={10: {}, 20: {}},
            all_conditions=self.all_conditions,
        )

        log = self.logger.get_log()

        # Get all action executions in PRE_MOVE phase
        pre_move_actions = [e for e in log.get_entries_by_type(LogEventType.ACTION_EXECUTED) if e.phase == ConditionPhase.PRE_MOVE]

        # a_poison_tick should come before any other effects in PRE_MOVE
        if len(pre_move_actions) > 0:
            effect_names = [e.effect_name for e in pre_move_actions]
            # All should be a_poison_tick in PRE_MOVE (only poison triggers there)
            for name in effect_names:
                assert name == "a_poison_tick", f"Expected a_poison_tick, got {name}"

    def test_condition_data_logged(self):
        """Verify condition evaluation data is captured."""
        context = self._create_context(turn=1)
        self.resolver.resolve_turn(
            context,
            self.actions,
            world_rules=self.world_rules,
            participant_items={10: {}, 20: {}},
            all_conditions=self.all_conditions,
        )

        log = self.logger.get_log()
        evaluations = log.get_entries_by_type(LogEventType.EFFECT_EVALUATED)

        # Find a poison tick evaluation
        poison_eval = next((e for e in evaluations if e.effect_name == "a_poison_tick"), None)
        assert poison_eval is not None

        # Verify condition data is logged
        assert poison_eval.condition_type == "and"
        assert poison_eval.condition_data is not None
        assert "condition_ids" in poison_eval.condition_data


class TestDuelScenarios:
    """Additional duel scenarios to test logging edge cases."""

    def test_mutual_kill_logged(self):
        """Test logging when both players die simultaneously."""
        logger = CombatLogger(duel_id=2)
        resolver = TurnResolver(logger=logger)

        # Both players have fatal poison
        player1 = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=10,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks={"poison": 1},
        )
        player2 = CombatState(
            player_id=2,
            participant_id=20,
            current_hp=10,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks={"poison": 1},
        )

        world_rules = [
            EffectData(
                id=1,
                name="poison_tick",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [1, 2]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 15},
                owner_participant_id=0,
            ),
        ]

        all_conditions = {
            1: (ConditionType.PHASE, {"phase": "pre_move"}),
            2: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
        }

        context = DuelContext(
            duel_id=2,
            setting_id=1,
            current_turn=1,
            states={10: player1, 20: player2},
        )

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        result = resolver.resolve_turn(
            context,
            actions,
            world_rules=world_rules,
            participant_items={10: {}, 20: {}},
            all_conditions=all_conditions,
        )

        log = logger.get_log()

        # Both players should have taken damage
        executions = log.get_entries_by_type(LogEventType.ACTION_EXECUTED)
        assert len(executions) == 2, "Both players should take poison damage"

        # Both should be dead
        assert player1.current_hp == 0
        assert player2.current_hp == 0

        # Winner is None (draw)
        assert result.winner_participant_id is None

    def test_no_effects_triggered_logged(self):
        """Test logging when no effects trigger (no stacks)."""
        logger = CombatLogger(duel_id=3)
        resolver = TurnResolver(logger=logger)

        # Players with no stacks
        player1 = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        player2 = CombatState(
            player_id=2,
            participant_id=20,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )

        # Poison rule that won't trigger (no stacks)
        world_rules = [
            EffectData(
                id=1,
                name="poison_tick",
                condition_type=ConditionType.AND,
                condition_data={"condition_ids": [1, 2]},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 10},
                owner_participant_id=0,
            ),
        ]

        all_conditions = {
            1: (ConditionType.PHASE, {"phase": "pre_move"}),
            2: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
        }

        context = DuelContext(
            duel_id=3,
            setting_id=1,
            current_turn=1,
            states={10: player1, 20: player2},
        )

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

        log = logger.get_log()

        # Should have evaluations but they should fail
        evaluations = log.get_entries_by_type(LogEventType.EFFECT_EVALUATED)
        assert len(evaluations) > 0, "Should have effect evaluations"

        # All should have condition_result = False (no poison stacks)
        for ev in evaluations:
            if ev.effect_name == "poison_tick":
                assert ev.condition_result is False, "Poison should not trigger without stacks"

        # No action executions for poison
        executions = log.get_entries_by_type(LogEventType.ACTION_EXECUTED)
        poison_execs = [e for e in executions if e.effect_name == "poison_tick"]
        assert len(poison_execs) == 0, "Poison should not execute without stacks"

        # HP unchanged
        assert player1.current_hp == 100
        assert player2.current_hp == 100
