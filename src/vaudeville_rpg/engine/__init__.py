"""Duel engine module - handles turn processing, action resolution, and damage calculation."""

from .actions import ActionExecutor
from .conditions import ConditionEvaluator
from .duel import DuelEngine, DuelResult
from .effects import EffectProcessor
from .logging import CombatLog, CombatLogger, LogEntry, LogEventType, StateSnapshot
from .turn import TurnResolver

__all__ = [
    "ConditionEvaluator",
    "ActionExecutor",
    "EffectProcessor",
    "TurnResolver",
    "DuelEngine",
    "DuelResult",
    "CombatLogger",
    "CombatLog",
    "LogEntry",
    "LogEventType",
    "StateSnapshot",
]
