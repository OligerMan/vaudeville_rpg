"""Player system models."""

from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Player(Base, TimestampMixin):
    """A player in a specific chat/setting.

    Players are per-chat - the same Telegram user has separate player
    profiles in different chats/settings.
    """

    __tablename__ = "players"
    __table_args__ = (
        UniqueConstraint("telegram_user_id", "setting_id", name="uq_player_user_setting"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    setting_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("settings.id"), nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Base stats
    max_hp: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    max_special_points: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    # PvP rating
    rating: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)

    # Bot flag for PvE enemies
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Equipped items (one per slot, nullable = no item equipped)
    attack_item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True
    )
    defense_item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True
    )
    misc_item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    setting: Mapped["Setting"] = relationship("Setting", back_populates="players")
    attack_item: Mapped["Item | None"] = relationship(
        "Item", foreign_keys=[attack_item_id], lazy="joined"
    )
    defense_item: Mapped["Item | None"] = relationship(
        "Item", foreign_keys=[defense_item_id], lazy="joined"
    )
    misc_item: Mapped["Item | None"] = relationship(
        "Item", foreign_keys=[misc_item_id], lazy="joined"
    )
    combat_states: Mapped[list["PlayerCombatState"]] = relationship(
        "PlayerCombatState", back_populates="player", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Player(id={self.id}, name={self.display_name}, rating={self.rating})>"


class PlayerCombatState(Base, TimestampMixin):
    """Combat state for a player in an active duel.

    Persisted to database to survive bot restarts.
    """

    __tablename__ = "player_combat_states"
    __table_args__ = (
        UniqueConstraint("player_id", "duel_id", name="uq_combat_state_player_duel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("players.id"), nullable=False, index=True
    )
    duel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("duels.id"), nullable=False, index=True
    )

    # Current stats
    current_hp: Mapped[int] = mapped_column(Integer, nullable=False)
    current_special_points: Mapped[int] = mapped_column(Integer, nullable=False)

    # Current attribute stacks (e.g., {"poison": 3, "armor": 2})
    attribute_stacks: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # Relationships
    player: Mapped["Player"] = relationship("Player", back_populates="combat_states")
    duel: Mapped["Duel"] = relationship("Duel", back_populates="combat_states")

    def __repr__(self) -> str:
        return f"<PlayerCombatState(player={self.player_id}, hp={self.current_hp})>"


# Forward references for type hints
from .duels import Duel  # noqa: E402, F401
from .items import Item  # noqa: E402, F401
from .settings import Setting  # noqa: E402, F401
