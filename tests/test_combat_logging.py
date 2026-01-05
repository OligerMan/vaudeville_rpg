"""Tests for the combat logging system."""

from vaudeville_rpg.db.models.enums import (
    ConditionPhase,
    ConditionType,
    DuelActionType,
    EffectCategory,
    TargetType,
)
from vaudeville_rpg.engine.effects import EffectData, EffectProcessor
from vaudeville_rpg.engine.logging import (
    CombatLog,
    CombatLogger,
    LogEntry,
    LogEventType,
    StateSnapshot,
)
from vaudeville_rpg.engine.turn import ParticipantAction, TurnResolver
from vaudeville_rpg.engine.types import CombatState, DuelContext


class TestStateSnapshot:
    """Tests for StateSnapshot data class."""

    def test_create_snapshot(self):
        """Test creating a state snapshot."""
        snapshot = StateSnapshot(
            participant_id=10,
            current_hp=80,
            max_hp=100,
            current_special_points=30,
            max_special_points=50,
            attribute_stacks={"poison": 3, "armor": 2},
            incoming_damage_reduction=5,
            pending_damage=10,
        )

        assert snapshot.participant_id == 10
        assert snapshot.current_hp == 80
        assert snapshot.max_hp == 100
        assert snapshot.current_special_points == 30
        assert snapshot.max_special_points == 50
        assert snapshot.attribute_stacks == {"poison": 3, "armor": 2}
        assert snapshot.incoming_damage_reduction == 5
        assert snapshot.pending_damage == 10

    def test_snapshot_to_dict(self):
        """Test converting snapshot to dictionary."""
        snapshot = StateSnapshot(
            participant_id=10,
            current_hp=80,
            max_hp=100,
            current_special_points=30,
            max_special_points=50,
            attribute_stacks={"poison": 3},
            incoming_damage_reduction=0,
            pending_damage=0,
        )

        result = snapshot.to_dict()

        assert result["participant_id"] == 10
        assert result["current_hp"] == 80
        assert result["max_hp"] == 100
        assert result["attribute_stacks"] == {"poison": 3}


class TestLogEntry:
    """Tests for LogEntry data class."""

    def test_create_log_entry(self):
        """Test creating a log entry."""
        entry = LogEntry(
            event_type=LogEventType.TURN_START,
            turn_number=1,
            timestamp_order=1,
        )

        assert entry.event_type == LogEventType.TURN_START
        assert entry.turn_number == 1
        assert entry.timestamp_order == 1

    def test_log_entry_with_all_fields(self):
        """Test log entry with all optional fields."""
        before = StateSnapshot(
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks={},
            incoming_damage_reduction=0,
            pending_damage=0,
        )
        after = StateSnapshot(
            participant_id=10,
            current_hp=85,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks={},
            incoming_damage_reduction=0,
            pending_damage=0,
        )

        entry = LogEntry(
            event_type=LogEventType.ACTION_EXECUTED,
            turn_number=1,
            phase=ConditionPhase.PRE_ATTACK,
            timestamp_order=5,
            participant_id=10,
            target_participant_id=20,
            effect_name="sword_attack",
            action_type="attack",
            action_data={"value": 15},
            value=15,
            description="Attack dealt 15 damage",
            state_before=before,
            state_after=after,
        )

        assert entry.effect_name == "sword_attack"
        assert entry.value == 15
        assert entry.state_before.current_hp == 100
        assert entry.state_after.current_hp == 85

    def test_log_entry_to_dict(self):
        """Test converting log entry to dictionary."""
        entry = LogEntry(
            event_type=LogEventType.PHASE_START,
            turn_number=1,
            phase=ConditionPhase.PRE_MOVE,
            timestamp_order=2,
        )

        result = entry.to_dict()

        assert result["event_type"] == "phase_start"
        assert result["turn_number"] == 1
        assert result["phase"] == "pre_move"
        assert result["timestamp_order"] == 2

    def test_log_entry_to_dict_omits_none(self):
        """Test that to_dict omits None values."""
        entry = LogEntry(
            event_type=LogEventType.TURN_START,
            turn_number=1,
            timestamp_order=1,
        )

        result = entry.to_dict()

        assert "phase" not in result
        assert "effect_name" not in result
        assert "value" not in result


class TestCombatLog:
    """Tests for CombatLog class."""

    def test_create_combat_log(self):
        """Test creating a combat log."""
        log = CombatLog(duel_id=123)

        assert log.duel_id == 123
        assert log.entries == []

    def test_add_entries(self):
        """Test adding entries to log."""
        log = CombatLog(duel_id=123)

        log.entries.append(
            LogEntry(
                event_type=LogEventType.TURN_START,
                turn_number=1,
                timestamp_order=1,
            )
        )
        log.entries.append(
            LogEntry(
                event_type=LogEventType.PHASE_START,
                turn_number=1,
                phase=ConditionPhase.PRE_MOVE,
                timestamp_order=2,
            )
        )

        assert len(log.entries) == 2

    def test_get_entries_by_type(self):
        """Test filtering entries by type."""
        log = CombatLog(duel_id=123)
        log.entries = [
            LogEntry(event_type=LogEventType.TURN_START, turn_number=1, timestamp_order=1),
            LogEntry(event_type=LogEventType.PHASE_START, turn_number=1, phase=ConditionPhase.PRE_MOVE, timestamp_order=2),
            LogEntry(event_type=LogEventType.PHASE_END, turn_number=1, phase=ConditionPhase.PRE_MOVE, timestamp_order=3),
            LogEntry(event_type=LogEventType.PHASE_START, turn_number=1, phase=ConditionPhase.POST_MOVE, timestamp_order=4),
            LogEntry(event_type=LogEventType.TURN_END, turn_number=1, timestamp_order=5),
        ]

        phase_starts = log.get_entries_by_type(LogEventType.PHASE_START)
        assert len(phase_starts) == 2

        turn_starts = log.get_entries_by_type(LogEventType.TURN_START)
        assert len(turn_starts) == 1

    def test_get_entries_for_turn(self):
        """Test filtering entries by turn number."""
        log = CombatLog(duel_id=123)
        log.entries = [
            LogEntry(event_type=LogEventType.TURN_START, turn_number=1, timestamp_order=1),
            LogEntry(event_type=LogEventType.TURN_END, turn_number=1, timestamp_order=2),
            LogEntry(event_type=LogEventType.TURN_START, turn_number=2, timestamp_order=3),
            LogEntry(event_type=LogEventType.TURN_END, turn_number=2, timestamp_order=4),
        ]

        turn_1_entries = log.get_entries_for_turn(1)
        assert len(turn_1_entries) == 2

        turn_2_entries = log.get_entries_for_turn(2)
        assert len(turn_2_entries) == 2

    def test_get_entries_for_phase(self):
        """Test filtering entries by phase."""
        log = CombatLog(duel_id=123)
        log.entries = [
            LogEntry(event_type=LogEventType.PHASE_START, turn_number=1, phase=ConditionPhase.PRE_MOVE, timestamp_order=1),
            LogEntry(event_type=LogEventType.ACTION_EXECUTED, turn_number=1, phase=ConditionPhase.PRE_MOVE, timestamp_order=2),
            LogEntry(event_type=LogEventType.PHASE_END, turn_number=1, phase=ConditionPhase.PRE_MOVE, timestamp_order=3),
            LogEntry(event_type=LogEventType.PHASE_START, turn_number=1, phase=ConditionPhase.POST_MOVE, timestamp_order=4),
        ]

        pre_move_entries = log.get_entries_for_phase(ConditionPhase.PRE_MOVE)
        assert len(pre_move_entries) == 3

        post_move_entries = log.get_entries_for_phase(ConditionPhase.POST_MOVE)
        assert len(post_move_entries) == 1

    def test_combat_log_to_dict(self):
        """Test converting combat log to dictionary."""
        log = CombatLog(duel_id=123)
        log.entries = [
            LogEntry(event_type=LogEventType.TURN_START, turn_number=1, timestamp_order=1),
            LogEntry(event_type=LogEventType.TURN_END, turn_number=1, timestamp_order=2),
        ]

        result = log.to_dict()

        assert result["duel_id"] == 123
        assert len(result["entries"]) == 2
        assert result["entries"][0]["event_type"] == "turn_start"

    def test_format_readable(self):
        """Test human-readable format."""
        log = CombatLog(duel_id=123)
        log.entries = [
            LogEntry(event_type=LogEventType.TURN_START, turn_number=1, timestamp_order=1),
            LogEntry(event_type=LogEventType.PHASE_START, turn_number=1, phase=ConditionPhase.PRE_MOVE, timestamp_order=2),
            LogEntry(event_type=LogEventType.TURN_END, turn_number=1, timestamp_order=3),
        ]

        output = log.format_readable()

        assert "Combat Log (Duel #123)" in output
        assert "Turn 1" in output


class TestCombatLogger:
    """Tests for CombatLogger class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logger = CombatLogger(duel_id=123)
        self.state = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks={"poison": 3},
        )

    def test_create_logger(self):
        """Test creating a logger."""
        logger = CombatLogger(duel_id=456)
        assert logger.duel_id == 456
        assert len(logger.get_log().entries) == 0

    def test_snapshot_state(self):
        """Test creating snapshot from CombatState."""
        snapshot = CombatLogger.snapshot_state(self.state)

        assert snapshot.participant_id == 10
        assert snapshot.current_hp == 100
        assert snapshot.max_hp == 100
        assert snapshot.current_special_points == 50
        assert snapshot.max_special_points == 50
        assert snapshot.attribute_stacks == {"poison": 3}
        assert snapshot.incoming_damage_reduction == 0
        assert snapshot.pending_damage == 0

    def test_log_turn_start(self):
        """Test logging turn start."""
        states = {10: self.state}
        self.logger.log_turn_start(turn_number=1, states=states)

        log = self.logger.get_log()
        assert len(log.entries) == 1
        assert log.entries[0].event_type == LogEventType.TURN_START
        assert log.entries[0].turn_number == 1
        assert log.entries[0].all_states is not None
        assert 10 in log.entries[0].all_states

    def test_log_turn_end(self):
        """Test logging turn end."""
        states = {10: self.state}
        self.logger.log_turn_end(turn_number=1, states=states)

        log = self.logger.get_log()
        assert len(log.entries) == 1
        assert log.entries[0].event_type == LogEventType.TURN_END

    def test_log_phase_start_end(self):
        """Test logging phase transitions."""
        self.logger.log_phase_start(turn_number=1, phase=ConditionPhase.PRE_MOVE)
        self.logger.log_phase_end(turn_number=1, phase=ConditionPhase.PRE_MOVE)

        log = self.logger.get_log()
        assert len(log.entries) == 2
        assert log.entries[0].event_type == LogEventType.PHASE_START
        assert log.entries[0].phase == ConditionPhase.PRE_MOVE
        assert log.entries[1].event_type == LogEventType.PHASE_END

    def test_log_effect_evaluated(self):
        """Test logging effect evaluation."""
        self.logger.log_effect_evaluated(
            turn_number=1,
            phase=ConditionPhase.PRE_MOVE,
            participant_id=10,
            effect_name="poison_tick",
            condition_type="phase",
            condition_data={"phase": "pre_move"},
            condition_result=True,
        )

        log = self.logger.get_log()
        assert len(log.entries) == 1
        assert log.entries[0].event_type == LogEventType.EFFECT_EVALUATED
        assert log.entries[0].effect_name == "poison_tick"
        assert log.entries[0].condition_result is True

    def test_log_effect_skipped(self):
        """Test logging skipped effect."""
        self.logger.log_effect_skipped(
            turn_number=1,
            phase=ConditionPhase.PRE_MOVE,
            participant_id=10,
            effect_name="armor_reduction",
            reason="No armor stacks",
        )

        log = self.logger.get_log()
        assert len(log.entries) == 1
        assert log.entries[0].event_type == LogEventType.EFFECT_SKIPPED
        assert log.entries[0].reason == "No armor stacks"

    def test_log_action_executed(self):
        """Test logging action execution."""
        state_before = CombatState(
            player_id=2,
            participant_id=20,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )
        state_after = CombatState(
            player_id=2,
            participant_id=20,
            current_hp=85,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )

        self.logger.log_action_executed(
            turn_number=1,
            phase=ConditionPhase.PRE_ATTACK,
            participant_id=10,
            target_participant_id=20,
            effect_name="sword_attack",
            action_type="attack",
            action_data={"value": 15},
            value=15,
            description="Attack dealt 15 damage",
            state_before=state_before,
            state_after=state_after,
        )

        log = self.logger.get_log()
        assert len(log.entries) == 1
        entry = log.entries[0]
        assert entry.event_type == LogEventType.ACTION_EXECUTED
        assert entry.effect_name == "sword_attack"
        assert entry.value == 15
        assert entry.state_before.current_hp == 100
        assert entry.state_after.current_hp == 85

    def test_log_pending_damage_applied(self):
        """Test logging pending damage application."""
        state_before = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            pending_damage=20,
        )
        state_after = CombatState(
            player_id=1,
            participant_id=10,
            current_hp=80,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
        )

        self.logger.log_pending_damage_applied(
            turn_number=1,
            target_participant_id=10,
            value=20,
            state_before=state_before,
            state_after=state_after,
        )

        log = self.logger.get_log()
        assert len(log.entries) == 1
        assert log.entries[0].event_type == LogEventType.PENDING_DAMAGE_APPLIED
        assert log.entries[0].value == 20

    def test_log_winner(self):
        """Test logging winner determination."""
        self.logger.log_winner(turn_number=3, winner_participant_id=20)

        log = self.logger.get_log()
        assert len(log.entries) == 1
        assert log.entries[0].event_type == LogEventType.WINNER_DETERMINED
        assert log.entries[0].winner_participant_id == 20

    def test_clear_log(self):
        """Test clearing the log."""
        self.logger.log_turn_start(1, {10: self.state})
        self.logger.log_turn_end(1, {10: self.state})

        assert len(self.logger.get_log().entries) == 2

        self.logger.clear()

        assert len(self.logger.get_log().entries) == 0

    def test_timestamp_order_increments(self):
        """Test that timestamp order auto-increments."""
        self.logger.log_turn_start(1, {10: self.state})
        self.logger.log_phase_start(1, ConditionPhase.PRE_MOVE)
        self.logger.log_phase_end(1, ConditionPhase.PRE_MOVE)

        log = self.logger.get_log()
        assert log.entries[0].timestamp_order == 1
        assert log.entries[1].timestamp_order == 2
        assert log.entries[2].timestamp_order == 3


class TestTurnResolverWithLogging:
    """Tests for TurnResolver integration with logging."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logger = CombatLogger(duel_id=1)
        self.resolver = TurnResolver(logger=self.logger)
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

    def test_turn_start_end_logged(self):
        """Test that turn start and end are logged."""
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

        log = self.logger.get_log()
        turn_starts = log.get_entries_by_type(LogEventType.TURN_START)
        turn_ends = log.get_entries_by_type(LogEventType.TURN_END)

        assert len(turn_starts) == 1
        assert len(turn_ends) == 1

    def test_phases_logged(self):
        """Test that all sequential phases are logged.

        Note: PRE_DAMAGE and POST_DAMAGE are now interrupt phases that only fire
        when damage is being applied, not sequential phases.
        """
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

        log = self.logger.get_log()
        phase_starts = log.get_entries_by_type(LogEventType.PHASE_START)
        phase_ends = log.get_entries_by_type(LogEventType.PHASE_END)

        # Should have PRE_MOVE, PRE_ATTACK, POST_ATTACK, POST_MOVE
        # (PRE_DAMAGE and POST_DAMAGE are now interrupt phases, not sequential)
        assert len(phase_starts) == 4
        assert len(phase_ends) == 4

    def test_effect_evaluation_logged(self):
        """Test that effect evaluations are logged."""
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
        ]

        all_conditions = {
            101: (ConditionType.PHASE, {"phase": "pre_move"}),
            102: (ConditionType.HAS_STACKS, {"attribute": "poison", "min_count": 1}),
        }

        actions = [
            ParticipantAction(participant_id=10, action_type=DuelActionType.SKIP),
            ParticipantAction(participant_id=20, action_type=DuelActionType.SKIP),
        ]

        self.resolver.resolve_turn(
            self.context,
            actions,
            world_rules=world_rules,
            participant_items={10: {}, 20: {}},
            all_conditions=all_conditions,
        )

        log = self.logger.get_log()
        evaluations = log.get_entries_by_type(LogEventType.EFFECT_EVALUATED)

        # Both players evaluated for poison_tick
        assert len(evaluations) >= 2

    def test_action_execution_logged(self):
        """Test that action executions are logged with state changes."""
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

        self.resolver.resolve_turn(
            self.context,
            actions,
            world_rules=world_rules,
            participant_items={10: {}, 20: {}},
            all_conditions=all_conditions,
        )

        log = self.logger.get_log()
        executions = log.get_entries_by_type(LogEventType.ACTION_EXECUTED)

        # Player 1 has poison, should have action executed
        assert len(executions) >= 1

        poison_exec = [e for e in executions if e.effect_name == "poison_tick"]
        assert len(poison_exec) >= 1

        # Verify state change was captured
        exec_entry = poison_exec[0]
        assert exec_entry.state_before is not None
        assert exec_entry.state_after is not None
        assert exec_entry.value == 10

    def test_winner_logged(self):
        """Test that winner is logged when duel ends."""
        # Player 1 will die from poison
        self.state1.current_hp = 5
        self.state1.attribute_stacks = {"poison": 1}

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

        result = self.resolver.resolve_turn(
            self.context,
            actions,
            world_rules=world_rules,
            participant_items={10: {}, 20: {}},
            all_conditions=all_conditions,
        )

        assert result.is_duel_over
        assert result.winner_participant_id == 20

        log = self.logger.get_log()
        winner_entries = log.get_entries_by_type(LogEventType.WINNER_DETERMINED)

        assert len(winner_entries) == 1
        assert winner_entries[0].winner_participant_id == 20

    def test_full_turn_log_sequence(self):
        """Test complete log sequence for a turn."""
        world_rules = [
            EffectData(
                id=1,
                name="poison_tick",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "pre_move"},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 5},
                owner_participant_id=0,
            ),
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

        log = self.logger.get_log()

        # Verify sequence: TURN_START should come first
        assert log.entries[0].event_type == LogEventType.TURN_START

        # TURN_END should come last
        assert log.entries[-1].event_type == LogEventType.TURN_END

        # All entries should have turn_number = 1
        for entry in log.entries:
            assert entry.turn_number == 1

        # Verify timestamps are in order
        prev_order = 0
        for entry in log.entries:
            assert entry.timestamp_order > prev_order
            prev_order = entry.timestamp_order


class TestEffectProcessorWithLogging:
    """Tests for EffectProcessor integration with logging."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logger = CombatLogger(duel_id=1)
        self.processor = EffectProcessor(logger=self.logger)
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

    def test_condition_evaluation_logged(self):
        """Test that condition evaluations are logged."""
        effects = [
            EffectData(
                id=1,
                name="test_effect",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "pre_move"},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 5},
                owner_participant_id=10,
            ),
        ]

        self.processor.process_phase(
            ConditionPhase.PRE_MOVE,
            effects,
            self.context,
            turn_number=1,
        )

        log = self.logger.get_log()
        evaluations = log.get_entries_by_type(LogEventType.EFFECT_EVALUATED)

        assert len(evaluations) == 1
        assert evaluations[0].effect_name == "test_effect"
        assert evaluations[0].condition_result is True

    def test_condition_failure_logged(self):
        """Test that failed condition evaluations are logged."""
        effects = [
            EffectData(
                id=1,
                name="test_effect",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "post_move"},  # Wrong phase
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 5},
                owner_participant_id=10,
            ),
        ]

        self.processor.process_phase(
            ConditionPhase.PRE_MOVE,  # Different from condition
            effects,
            self.context,
            turn_number=1,
        )

        log = self.logger.get_log()
        evaluations = log.get_entries_by_type(LogEventType.EFFECT_EVALUATED)

        assert len(evaluations) == 1
        assert evaluations[0].condition_result is False

    def test_action_execution_with_state_change(self):
        """Test that actions are logged with before/after state."""
        effects = [
            EffectData(
                id=1,
                name="heal_effect",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "pre_move"},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="heal",
                action_data={"value": 20},
                owner_participant_id=10,
            ),
        ]

        # Damage the player first
        self.state1.current_hp = 80

        self.processor.process_phase(
            ConditionPhase.PRE_MOVE,
            effects,
            self.context,
            turn_number=1,
        )

        log = self.logger.get_log()
        executions = log.get_entries_by_type(LogEventType.ACTION_EXECUTED)

        assert len(executions) == 1
        exec_entry = executions[0]
        assert exec_entry.state_before.current_hp == 80
        assert exec_entry.state_after.current_hp == 100  # Healed
        assert exec_entry.value == 20

    def test_multiple_effects_logged_alphabetically(self):
        """Test that multiple effects are logged in alphabetical order."""
        effects = [
            EffectData(
                id=2,
                name="z_heal",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "pre_move"},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="heal",
                action_data={"value": 5},
                owner_participant_id=10,
            ),
            EffectData(
                id=1,
                name="a_damage",
                condition_type=ConditionType.PHASE,
                condition_data={"phase": "pre_move"},
                target=TargetType.SELF,
                category=EffectCategory.WORLD_RULE,
                action_type="damage",
                action_data={"value": 10},
                owner_participant_id=10,
            ),
        ]

        self.processor.process_phase(
            ConditionPhase.PRE_MOVE,
            effects,
            self.context,
            turn_number=1,
        )

        log = self.logger.get_log()
        executions = log.get_entries_by_type(LogEventType.ACTION_EXECUTED)

        assert len(executions) == 2
        # a_damage should be first (alphabetical)
        assert executions[0].effect_name == "a_damage"
        assert executions[1].effect_name == "z_heal"


class TestLogFormatting:
    """Tests for log formatting and readability."""

    def test_format_action_with_hp_change(self):
        """Test formatting shows HP changes."""
        log = CombatLog(duel_id=123)

        before = StateSnapshot(
            participant_id=10,
            current_hp=100,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks={},
            incoming_damage_reduction=0,
            pending_damage=0,
        )
        after = StateSnapshot(
            participant_id=10,
            current_hp=85,
            max_hp=100,
            current_special_points=50,
            max_special_points=50,
            attribute_stacks={},
            incoming_damage_reduction=0,
            pending_damage=0,
        )

        log.entries = [
            LogEntry(
                event_type=LogEventType.ACTION_EXECUTED,
                turn_number=1,
                phase=ConditionPhase.PRE_ATTACK,
                timestamp_order=1,
                participant_id=20,
                target_participant_id=10,
                effect_name="sword_attack",
                action_type="attack",
                value=15,
                description="Attack dealt 15 damage",
                state_before=before,
                state_after=after,
            ),
        ]

        output = log.format_readable()

        assert "sword_attack" in output
        assert "15" in output
        assert "100" in output  # HP before
        assert "85" in output  # HP after

    def test_format_state_snapshot(self):
        """Test formatting state snapshot."""
        log = CombatLog(duel_id=123)

        snapshot = StateSnapshot(
            participant_id=10,
            current_hp=80,
            max_hp=100,
            current_special_points=30,
            max_special_points=50,
            attribute_stacks={"poison": 3, "armor": 2},
            incoming_damage_reduction=0,
            pending_damage=0,
        )

        log.entries = [
            LogEntry(
                event_type=LogEventType.STATE_SNAPSHOT,
                turn_number=1,
                timestamp_order=1,
                all_states={10: snapshot},
            ),
        ]

        output = log.format_readable()

        assert "HP=80/100" in output
        assert "SP=30/50" in output
        assert "poison:3" in output
        assert "armor:2" in output

    def test_format_winner(self):
        """Test formatting winner announcement."""
        log = CombatLog(duel_id=123)
        log.entries = [
            LogEntry(
                event_type=LogEventType.WINNER_DETERMINED,
                turn_number=5,
                timestamp_order=100,
                winner_participant_id=20,
            ),
        ]

        output = log.format_readable()

        assert "WINNER" in output
        assert "20" in output
