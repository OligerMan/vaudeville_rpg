"""Item system models."""

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import ItemSlot


class Item(Base, TimestampMixin):
    """An item that can be equipped by players.

    Items are containers for effects. Each item can have multiple effects
    that trigger under different conditions.
    """

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    slot: Mapped[ItemSlot] = mapped_column(
        SQLEnum(ItemSlot, name="item_slot"), nullable=False
    )
    rarity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )  # 1=common, 2=uncommon, 3=rare, 4=epic, 5=legendary

    # Which setting this item belongs to
    setting_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("settings.id"), nullable=False, index=True
    )

    # Relationships
    setting: Mapped["Setting"] = relationship("Setting", back_populates="items")
    effects: Mapped[list["Effect"]] = relationship(
        "Effect", back_populates="item", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Item(name={self.name}, slot={self.slot}, rarity={self.rarity})>"


# Forward references for type hints
from .effects import Effect  # noqa: E402, F401
from .settings import Setting  # noqa: E402, F401
