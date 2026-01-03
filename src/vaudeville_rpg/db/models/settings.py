"""Setting and AttributeDefinition models for per-chat configuration."""

from sqlalchemy import BigInteger, Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import AttributeCategory


class Setting(Base, TimestampMixin):
    """A game setting configuration for a specific Telegram chat.

    Each chat can have its own setting with custom attributes and world rules.
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_chat_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Configuration
    special_points_name: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Mana"
    )  # What to call special points in this setting
    special_points_regen: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )  # How much special points regenerate per turn
    max_generatable_attributes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3
    )  # How many generatable attributes this setting has

    # Relationships
    attributes: Mapped[list["AttributeDefinition"]] = relationship(
        "AttributeDefinition", back_populates="setting", cascade="all, delete-orphan"
    )
    world_rules: Mapped[list["Effect"]] = relationship(
        "Effect",
        back_populates="setting",
        foreign_keys="Effect.setting_id",
        cascade="all, delete-orphan",
    )
    items: Mapped[list["Item"]] = relationship(
        "Item", back_populates="setting", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Setting(name={self.name}, chat={self.telegram_chat_id})>"


class AttributeDefinition(Base, TimestampMixin):
    """Definition of an attribute within a setting.

    Attributes can be:
    - Core HP: Universal health, 0 = death
    - Core Special: Mana/Energy/etc., varies by setting
    - Generatable: Stack-based attributes like armor, poison, might
    """

    __tablename__ = "attribute_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setting_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("settings.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    category: Mapped[AttributeCategory] = mapped_column(
        SQLEnum(AttributeCategory, name="attribute_category"), nullable=False
    )

    # Stack configuration (for generatable attributes)
    max_stacks: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # None = unlimited
    default_stacks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # Starting stacks

    # Relationships
    setting: Mapped["Setting"] = relationship("Setting", back_populates="attributes")

    def __repr__(self) -> str:
        return f"<AttributeDefinition(name={self.name}, category={self.category})>"


# Forward references for type hints
from .effects import Effect  # noqa: E402, F401
from .items import Item  # noqa: E402, F401
