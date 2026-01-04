"""Combat logging system for tracking and verifying game engine output.

Provides structured logging of all combat events including:
- Phase transitions
- Effect evaluations (condition checks)
- Action executions with before/after state
- State snapshots
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..db.models.enums import ConditionPhase


class LogEventType(str, Enum):
    """Types of log events."""

    # Turn lifecycle
    TURN_START = "turn_start"
    TURN_END = "turn_end"

    # Phase lifecycle
    PHASE_START = "phase_start"
    PHASE_END = "phase_end"

    # Effect processing
    EFFECT_EVALUATED = "effect_evaluated"
    EFFECT_SKIPPED = "effect_skipped"  # Condition not met

    # Action execution
    ACTION_EXECUTED = "action_executed"

    # State changes
    STATE_SNAPSHOT = "state_snapshot"

    # Damage application
    PENDING_DAMAGE_APPLIED = "pending_damage_applied"

    # Win condition
    WINNER_DETERMINED = "winner_determined"


@dataclass
class StateSnapshot:
    """Snapshot of a participant's combat state at a point in time."""

    participant_id: int
    current_hp: int
    max_hp: int
    current_special_points: int
    max_special_points: int
    attribute_stacks: dict[str, int]
    incoming_damage_reduction: int
    pending_damage: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "participant_id": self.participant_id,
            "current_hp": self.current_hp,
            "max_hp": self.max_hp,
            "current_special_points": self.current_special_points,
            "max_special_points": self.max_special_points,
            "attribute_stacks": dict(self.attribute_stacks),
            "incoming_damage_reduction": self.incoming_damage_reduction,
            "pending_damage": self.pending_damage,
        }


@dataclass
class LogEntry:
    """A single log entry representing a combat event."""

    event_type: LogEventType
    turn_number: int
    phase: ConditionPhase | None = None
    timestamp_order: int = 0  # Order within the turn for deterministic sorting

    # Event-specific data
    participant_id: int | None = None
    target_participant_id: int | None = None
    effect_name: str | None = None
    action_type: str | None = None
    action_data: dict[str, Any] | None = None
    reason: str | None = None  # Why this happened (effect name, world rule, etc.)

    # State before/after for action events
    state_before: StateSnapshot | None = None
    state_after: StateSnapshot | None = None

    # Condition evaluation details
    condition_type: str | None = None
    condition_data: dict[str, Any] | None = None
    condition_result: bool | None = None

    # Action result
    value: int | None = None
    description: str | None = None

    # For state snapshots - all participants
    all_states: dict[int, StateSnapshot] | None = None

    # Winner info
    winner_participant_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {
            "event_type": self.event_type.value,
            "turn_number": self.turn_number,
            "timestamp_order": self.timestamp_order,
        }

        if self.phase is not None:
            result["phase"] = self.phase.value
        if self.participant_id is not None:
            result["participant_id"] = self.participant_id
        if self.target_participant_id is not None:
            result["target_participant_id"] = self.target_participant_id
        if self.effect_name is not None:
            result["effect_name"] = self.effect_name
        if self.action_type is not None:
            result["action_type"] = self.action_type
        if self.action_data is not None:
            result["action_data"] = self.action_data
        if self.reason is not None:
            result["reason"] = self.reason
        if self.state_before is not None:
            result["state_before"] = self.state_before.to_dict()
        if self.state_after is not None:
            result["state_after"] = self.state_after.to_dict()
        if self.condition_type is not None:
            result["condition_type"] = self.condition_type
        if self.condition_data is not None:
            result["condition_data"] = self.condition_data
        if self.condition_result is not None:
            result["condition_result"] = self.condition_result
        if self.value is not None:
            result["value"] = self.value
        if self.description is not None:
            result["description"] = self.description
        if self.all_states is not None:
            result["all_states"] = {pid: state.to_dict() for pid, state in self.all_states.items()}
        if self.winner_participant_id is not None:
            result["winner_participant_id"] = self.winner_participant_id

        return result


@dataclass
class CombatLog:
    """Complete log of a combat encounter (turn or duel)."""

    duel_id: int
    entries: list[LogEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "duel_id": self.duel_id,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def get_entries_by_type(self, event_type: LogEventType) -> list[LogEntry]:
        """Get all entries of a specific type."""
        return [e for e in self.entries if e.event_type == event_type]

    def get_entries_for_turn(self, turn_number: int) -> list[LogEntry]:
        """Get all entries for a specific turn."""
        return [e for e in self.entries if e.turn_number == turn_number]

    def get_entries_for_phase(self, phase: ConditionPhase) -> list[LogEntry]:
        """Get all entries for a specific phase."""
        return [e for e in self.entries if e.phase == phase]

    def format_readable(self) -> str:
        """Format the log in a human-readable format."""
        lines: list[str] = []
        lines.append(f"=== Combat Log (Duel #{self.duel_id}) ===\n")

        current_turn = -1
        current_phase = None

        for entry in self.entries:
            # Turn header
            if entry.turn_number != current_turn:
                current_turn = entry.turn_number
                current_phase = None
                lines.append(f"\n--- Turn {current_turn} ---\n")

            # Phase header
            if entry.phase != current_phase and entry.phase is not None:
                current_phase = entry.phase
                lines.append(f"\n  [{current_phase.value.upper()}]\n")

            # Format based on event type
            lines.append(self._format_entry(entry))

        return "\n".join(lines)

    def _format_entry(self, entry: LogEntry) -> str:
        """Format a single log entry."""
        match entry.event_type:
            case LogEventType.TURN_START:
                return f"  Turn {entry.turn_number} begins"

            case LogEventType.TURN_END:
                return f"  Turn {entry.turn_number} ends"

            case LogEventType.PHASE_START:
                return f"    Phase {entry.phase.value if entry.phase else '?'} begins"

            case LogEventType.PHASE_END:
                return f"    Phase {entry.phase.value if entry.phase else '?'} ends"

            case LogEventType.EFFECT_EVALUATED:
                status = "✓" if entry.condition_result else "✗"
                return (
                    f"    {status} Effect '{entry.effect_name}' "
                    f"(owner: P{entry.participant_id}) - "
                    f"condition {entry.condition_type}: {entry.condition_result}"
                )

            case LogEventType.EFFECT_SKIPPED:
                return f"    ✗ Effect '{entry.effect_name}' skipped (condition not met: {entry.reason})"

            case LogEventType.ACTION_EXECUTED:
                hp_change = ""
                if entry.state_before and entry.state_after:
                    hp_diff = entry.state_after.current_hp - entry.state_before.current_hp
                    if hp_diff != 0:
                        hp_change = f" [HP: {entry.state_before.current_hp} → {entry.state_after.current_hp}]"

                return (
                    f"    → {entry.effect_name}: {entry.action_type} on "
                    f"P{entry.target_participant_id} = {entry.value}"
                    f"{hp_change}"
                    f" ({entry.description})"
                )

            case LogEventType.PENDING_DAMAGE_APPLIED:
                return f"    → Pending damage applied to P{entry.target_participant_id}: {entry.value} damage"

            case LogEventType.STATE_SNAPSHOT:
                if entry.all_states:
                    state_lines = []
                    for pid, state in entry.all_states.items():
                        stacks_str = ", ".join(f"{k}:{v}" for k, v in state.attribute_stacks.items()) or "none"
                        state_lines.append(
                            f"      P{pid}: HP={state.current_hp}/{state.max_hp}, "
                            f"SP={state.current_special_points}/{state.max_special_points}, "
                            f"stacks=[{stacks_str}]"
                        )
                    return "    State snapshot:\n" + "\n".join(state_lines)
                return "    State snapshot (empty)"

            case LogEventType.WINNER_DETERMINED:
                return f"  *** WINNER: Participant {entry.winner_participant_id} ***"

            case _:
                return f"    {entry.event_type.value}: {entry.description or ''}"


class CombatLogger:
    """Logger for tracking combat events.

    Usage:
        logger = CombatLogger(duel_id=123)
        logger.log_turn_start(turn_number=1)
        logger.log_phase_start(turn_number=1, phase=ConditionPhase.PRE_MOVE)
        # ... log events ...
        logger.log_phase_end(turn_number=1, phase=ConditionPhase.PRE_MOVE)
        logger.log_turn_end(turn_number=1)

        # Get the complete log
        log = logger.get_log()
        print(log.format_readable())
    """

    def __init__(self, duel_id: int) -> None:
        """Initialize the logger for a duel."""
        self.duel_id = duel_id
        self._log = CombatLog(duel_id=duel_id)
        self._order_counter = 0

    def _next_order(self) -> int:
        """Get the next timestamp order value."""
        self._order_counter += 1
        return self._order_counter

    def get_log(self) -> CombatLog:
        """Get the complete combat log."""
        return self._log

    def clear(self) -> None:
        """Clear all log entries."""
        self._log.entries.clear()
        self._order_counter = 0

    @staticmethod
    def snapshot_state(state: Any) -> StateSnapshot:
        """Create a snapshot from a CombatState object."""
        return StateSnapshot(
            participant_id=state.participant_id,
            current_hp=state.current_hp,
            max_hp=state.max_hp,
            current_special_points=state.current_special_points,
            max_special_points=state.max_special_points,
            attribute_stacks=dict(state.attribute_stacks),
            incoming_damage_reduction=state.incoming_damage_reduction,
            pending_damage=state.pending_damage,
        )

    def log_turn_start(self, turn_number: int, states: dict[int, Any]) -> None:
        """Log the start of a turn with initial state snapshot."""
        self._log.entries.append(
            LogEntry(
                event_type=LogEventType.TURN_START,
                turn_number=turn_number,
                timestamp_order=self._next_order(),
                all_states={pid: self.snapshot_state(state) for pid, state in states.items()},
            )
        )

    def log_turn_end(self, turn_number: int, states: dict[int, Any]) -> None:
        """Log the end of a turn with final state snapshot."""
        self._log.entries.append(
            LogEntry(
                event_type=LogEventType.TURN_END,
                turn_number=turn_number,
                timestamp_order=self._next_order(),
                all_states={pid: self.snapshot_state(state) for pid, state in states.items()},
            )
        )

    def log_phase_start(self, turn_number: int, phase: ConditionPhase) -> None:
        """Log the start of a phase."""
        self._log.entries.append(
            LogEntry(
                event_type=LogEventType.PHASE_START,
                turn_number=turn_number,
                phase=phase,
                timestamp_order=self._next_order(),
            )
        )

    def log_phase_end(self, turn_number: int, phase: ConditionPhase) -> None:
        """Log the end of a phase."""
        self._log.entries.append(
            LogEntry(
                event_type=LogEventType.PHASE_END,
                turn_number=turn_number,
                phase=phase,
                timestamp_order=self._next_order(),
            )
        )

    def log_effect_evaluated(
        self,
        turn_number: int,
        phase: ConditionPhase,
        participant_id: int,
        effect_name: str,
        condition_type: str,
        condition_data: dict[str, Any],
        condition_result: bool,
    ) -> None:
        """Log an effect condition evaluation."""
        self._log.entries.append(
            LogEntry(
                event_type=LogEventType.EFFECT_EVALUATED,
                turn_number=turn_number,
                phase=phase,
                timestamp_order=self._next_order(),
                participant_id=participant_id,
                effect_name=effect_name,
                condition_type=condition_type,
                condition_data=condition_data,
                condition_result=condition_result,
            )
        )

    def log_effect_skipped(
        self,
        turn_number: int,
        phase: ConditionPhase,
        participant_id: int,
        effect_name: str,
        reason: str,
    ) -> None:
        """Log an effect that was skipped."""
        self._log.entries.append(
            LogEntry(
                event_type=LogEventType.EFFECT_SKIPPED,
                turn_number=turn_number,
                phase=phase,
                timestamp_order=self._next_order(),
                participant_id=participant_id,
                effect_name=effect_name,
                reason=reason,
            )
        )

    def log_action_executed(
        self,
        turn_number: int,
        phase: ConditionPhase,
        participant_id: int,
        target_participant_id: int,
        effect_name: str,
        action_type: str,
        action_data: dict[str, Any],
        value: int,
        description: str,
        state_before: Any,
        state_after: Any,
    ) -> None:
        """Log an action execution with before/after state."""
        self._log.entries.append(
            LogEntry(
                event_type=LogEventType.ACTION_EXECUTED,
                turn_number=turn_number,
                phase=phase,
                timestamp_order=self._next_order(),
                participant_id=participant_id,
                target_participant_id=target_participant_id,
                effect_name=effect_name,
                action_type=action_type,
                action_data=action_data,
                value=value,
                description=description,
                state_before=self.snapshot_state(state_before),
                state_after=self.snapshot_state(state_after),
            )
        )

    def log_pending_damage_applied(
        self,
        turn_number: int,
        target_participant_id: int,
        value: int,
        state_before: Any,
        state_after: Any,
    ) -> None:
        """Log pending damage application."""
        self._log.entries.append(
            LogEntry(
                event_type=LogEventType.PENDING_DAMAGE_APPLIED,
                turn_number=turn_number,
                phase=ConditionPhase.PRE_DAMAGE,
                timestamp_order=self._next_order(),
                target_participant_id=target_participant_id,
                value=value,
                description=f"Applied {value} pending damage",
                state_before=self.snapshot_state(state_before),
                state_after=self.snapshot_state(state_after),
            )
        )

    def log_state_snapshot(self, turn_number: int, phase: ConditionPhase | None, states: dict[int, Any]) -> None:
        """Log a state snapshot for all participants."""
        self._log.entries.append(
            LogEntry(
                event_type=LogEventType.STATE_SNAPSHOT,
                turn_number=turn_number,
                phase=phase,
                timestamp_order=self._next_order(),
                all_states={pid: self.snapshot_state(state) for pid, state in states.items()},
            )
        )

    def log_winner(self, turn_number: int, winner_participant_id: int) -> None:
        """Log the winner determination."""
        self._log.entries.append(
            LogEntry(
                event_type=LogEventType.WINNER_DETERMINED,
                turn_number=turn_number,
                timestamp_order=self._next_order(),
                winner_participant_id=winner_participant_id,
            )
        )
