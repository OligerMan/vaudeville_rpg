"""Effect system models - Conditions, Actions, and Effects."""

from typing import Any

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import ActionType, ConditionType, EffectCategory, TargetType


class Condition(Base, TimestampMixin):
    """A condition that determines when an effect triggers.

    Conditions can be:
    - Simple: phase check or stack check
    - Composite: AND/OR of multiple conditions

    Stored as JSON for flexibility. Examples:
    - {"type": "phase", "phase": "pre_attack"}
    - {"type": "has_stacks", "attribute": "poison", "min_count": 1}
    - {"type": "and", "conditions": [{"type": "phase", "phase": "pre_move"}, {"type": "has_stacks", "attribute": "poison", "min_count": 1}]}
    """

    __tablename__ = "conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    condition_type: Mapped[ConditionType] = mapped_column(SQLEnum(ConditionType, name="condition_type"), nullable=False)

    # JSON structure for condition data
    # For PHASE: {"phase": "pre_attack"}
    # For HAS_STACKS: {"attribute": "poison", "min_count": 1}
    # For AND/OR: {"condition_ids": [1, 2, 3]}
    condition_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Relationships
    effects: Mapped[list["Effect"]] = relationship("Effect", back_populates="condition")

    def __repr__(self) -> str:
        return f"<Condition(name={self.name}, type={self.condition_type})>"


class Action(Base, TimestampMixin):
    """An action that an effect performs.

    Actions operate on attributes (HP, special points, or generatable attributes).

    Examples:
    - {"type": "damage", "value": 10}
    - {"type": "add_stacks", "attribute": "poison", "value": 3}
    - {"type": "heal", "value": 5}
    """

    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    action_type: Mapped[ActionType] = mapped_column(SQLEnum(ActionType, name="action_type"), nullable=False)

    # JSON structure for action data
    # Common fields:
    # - "value": int (flat value, will become formula later)
    # - "attribute": str (for stack-based actions)
    action_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Relationships
    effects: Mapped[list["Effect"]] = relationship("Effect", back_populates="action")

    def __repr__(self) -> str:
        return f"<Action(name={self.name}, type={self.action_type})>"


class Effect(Base, TimestampMixin):
    """An effect that combines a condition, target, and action.

    Effects can be:
    - Item effects: Attached to items, triggered by item usage
    - World rules: Attached to settings, apply globally

    Effects are ordered alphabetically by name when multiple trigger at the same phase.
    """

    __tablename__ = "effects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # What triggers this effect
    condition_id: Mapped[int] = mapped_column(Integer, ForeignKey("conditions.id"), nullable=False)

    # Who is affected
    target: Mapped[TargetType] = mapped_column(SQLEnum(TargetType, name="target_type"), nullable=False)

    # Where this effect is defined
    category: Mapped[EffectCategory] = mapped_column(SQLEnum(EffectCategory, name="effect_category"), nullable=False)

    # What happens
    action_id: Mapped[int] = mapped_column(Integer, ForeignKey("actions.id"), nullable=False)

    # Ownership - either belongs to a setting (world rule) or an item
    setting_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("settings.id"), nullable=True, index=True)
    item_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("items.id"), nullable=True, index=True)

    # Relationships
    condition: Mapped["Condition"] = relationship("Condition", back_populates="effects")
    action: Mapped["Action"] = relationship("Action", back_populates="effects")
    setting: Mapped["Setting | None"] = relationship("Setting", back_populates="world_rules", foreign_keys=[setting_id])
    item: Mapped["Item | None"] = relationship("Item", back_populates="effects")

    def __repr__(self) -> str:
        return f"<Effect(name={self.name}, target={self.target}, category={self.category})>"


# Forward references for type hints
from .items import Item  # noqa: E402, F401
from .settings import Setting  # noqa: E402, F401
