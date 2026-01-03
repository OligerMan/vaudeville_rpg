"""Duel system models."""

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import DuelActionType, DuelStatus


class Duel(Base, TimestampMixin):
    """A duel between two players (PvP or PvE).

    Tracks the overall duel state including status, current turn, and winner.
    """

    __tablename__ = "duels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setting_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("settings.id"), nullable=False, index=True
    )

    # Duel state
    status: Mapped[DuelStatus] = mapped_column(
        SQLEnum(DuelStatus, name="duel_status"), nullable=False, default=DuelStatus.PENDING
    )
    current_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Winner (null until duel is completed)
    winner_participant_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("duel_participants.id", use_alter=True), nullable=True
    )

    # Relationships
    setting: Mapped["Setting"] = relationship("Setting")
    participants: Mapped[list["DuelParticipant"]] = relationship(
        "DuelParticipant",
        back_populates="duel",
        foreign_keys="DuelParticipant.duel_id",
        cascade="all, delete-orphan",
    )
    actions: Mapped[list["DuelAction"]] = relationship(
        "DuelAction", back_populates="duel", cascade="all, delete-orphan"
    )
    combat_states: Mapped[list["PlayerCombatState"]] = relationship(
        "PlayerCombatState", back_populates="duel", cascade="all, delete-orphan"
    )
    winner: Mapped["DuelParticipant | None"] = relationship(
        "DuelParticipant", foreign_keys=[winner_participant_id], post_update=True
    )

    def __repr__(self) -> str:
        return f"<Duel(id={self.id}, status={self.status}, turn={self.current_turn})>"


class DuelParticipant(Base, TimestampMixin):
    """A participant in a duel.

    Tracks which player is in the duel and their ready state for the current turn.
    """

    __tablename__ = "duel_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    duel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("duels.id"), nullable=False, index=True
    )
    player_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("players.id"), nullable=False, index=True
    )

    # Turn order (1 or 2) - determines effect resolution order when tied
    turn_order: Mapped[int] = mapped_column(Integer, nullable=False)

    # Has this participant submitted their action for the current turn?
    is_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    duel: Mapped["Duel"] = relationship(
        "Duel", back_populates="participants", foreign_keys=[duel_id]
    )
    player: Mapped["Player"] = relationship("Player")
    actions: Mapped[list["DuelAction"]] = relationship(
        "DuelAction", back_populates="participant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DuelParticipant(duel={self.duel_id}, player={self.player_id}, order={self.turn_order})>"


class DuelAction(Base, TimestampMixin):
    """An action taken by a participant in a duel turn.

    Actions are persisted to database to survive bot restarts.
    """

    __tablename__ = "duel_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    duel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("duels.id"), nullable=False, index=True
    )
    participant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("duel_participants.id"), nullable=False, index=True
    )

    # Which turn this action is for
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # What action was taken
    action_type: Mapped[DuelActionType] = mapped_column(
        SQLEnum(DuelActionType, name="duel_action_type"), nullable=False
    )

    # Which item was used (null for SKIP action)
    item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("items.id"), nullable=True
    )

    # Relationships
    duel: Mapped["Duel"] = relationship("Duel", back_populates="actions")
    participant: Mapped["DuelParticipant"] = relationship(
        "DuelParticipant", back_populates="actions"
    )
    item: Mapped["Item | None"] = relationship("Item")

    def __repr__(self) -> str:
        return f"<DuelAction(duel={self.duel_id}, turn={self.turn_number}, type={self.action_type})>"


# Forward references for type hints
from .items import Item  # noqa: E402, F401
from .players import Player, PlayerCombatState  # noqa: E402, F401
from .settings import Setting  # noqa: E402, F401
