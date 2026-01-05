"""Duel engine module - handles turn processing, action resolution, and damage calculation."""

from .actions import ActionExecutor
from .conditions import ConditionEvaluator
from .duel import DuelEngine, DuelResult
from .effects import EffectProcessor
from .interrupts import DamageInterruptHandler, DamageResult
from .logging import CombatLog, CombatLogger, LogEntry, LogEventType, StateSnapshot
from .turn import ParticipantAction, PreMoveResult, TurnResolver

__all__ = [
    "ConditionEvaluator",
    "ActionExecutor",
    "EffectProcessor",
    "DamageInterruptHandler",
    "DamageResult",
    "TurnResolver",
    "ParticipantAction",
    "PreMoveResult",
    "DuelEngine",
    "DuelResult",
    "CombatLogger",
    "CombatLog",
    "LogEntry",
    "LogEventType",
    "StateSnapshot",
]
