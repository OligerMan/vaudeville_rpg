"""Item system models."""

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import AbilityEffect, AbilityType, BuffType, ItemSlot


class BuffDefinition(Base, TimestampMixin):
    """Definition of a buff that can be applied to items."""

    __tablename__ = "buff_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    buff_type: Mapped[BuffType] = mapped_column(
        SQLEnum(BuffType, name="buff_type"), nullable=False
    )
    base_value: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # Base magnitude of the buff

    # Relationships
    item_buffs: Mapped[list["ItemBuff"]] = relationship(
        "ItemBuff", back_populates="buff_definition"
    )

    def __repr__(self) -> str:
        return f"<BuffDefinition(name={self.name}, type={self.buff_type})>"


class AbilityDefinition(Base, TimestampMixin):
    """Definition of an ability that items can have."""

    __tablename__ = "ability_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    ability_type: Mapped[AbilityType] = mapped_column(
        SQLEnum(AbilityType, name="ability_type"), nullable=False
    )
    effect: Mapped[AbilityEffect] = mapped_column(
        SQLEnum(AbilityEffect, name="ability_effect"), nullable=False
    )
    base_power: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10
    )  # Base power/magnitude

    # Relationships
    items: Mapped[list["Item"]] = relationship("Item", back_populates="ability")

    def __repr__(self) -> str:
        return f"<AbilityDefinition(name={self.name}, type={self.ability_type})>"


class Item(Base, TimestampMixin):
    """An item that can be equipped by players."""

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

    # Foreign keys
    ability_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ability_definitions.id"), nullable=False
    )

    # Relationships
    ability: Mapped["AbilityDefinition"] = relationship(
        "AbilityDefinition", back_populates="items"
    )
    buffs: Mapped[list["ItemBuff"]] = relationship(
        "ItemBuff", back_populates="item", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Item(name={self.name}, slot={self.slot}, rarity={self.rarity})>"


class ItemBuff(Base):
    """Association table linking items to their buffs with magnitude."""

    __tablename__ = "item_buffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.id"), nullable=False
    )
    buff_definition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("buff_definitions.id"), nullable=False
    )
    value: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Actual buff value for this item

    # Relationships
    item: Mapped["Item"] = relationship("Item", back_populates="buffs")
    buff_definition: Mapped["BuffDefinition"] = relationship(
        "BuffDefinition", back_populates="item_buffs"
    )

    def __repr__(self) -> str:
        return f"<ItemBuff(item_id={self.item_id}, buff_id={self.buff_definition_id}, value={self.value})>"
