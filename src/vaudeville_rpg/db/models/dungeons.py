"""Dungeon system models."""

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import DungeonDifficulty, DungeonStatus


class Dungeon(Base, TimestampMixin):
    """A dungeon run by a player.

    A dungeon is a series of duels against computer enemies.
    Player progresses through stages until completion or defeat.
    """

    __tablename__ = "dungeons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    setting_id: Mapped[int] = mapped_column(Integer, ForeignKey("settings.id"), nullable=False, index=True)

    # Dungeon configuration
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[DungeonDifficulty] = mapped_column(
        SQLEnum(DungeonDifficulty, name="dungeon_difficulty"),
        nullable=False,
        default=DungeonDifficulty.NORMAL,
    )
    total_stages: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # Progress
    current_stage: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[DungeonStatus] = mapped_column(
        SQLEnum(DungeonStatus, name="dungeon_status"),
        nullable=False,
        default=DungeonStatus.IN_PROGRESS,
    )

    # Current duel (if any)
    current_duel_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("duels.id"), nullable=True)

    # Relationships
    player: Mapped["Player"] = relationship("Player")
    setting: Mapped["Setting"] = relationship("Setting")
    current_duel: Mapped["Duel | None"] = relationship("Duel")
    enemies: Mapped[list["DungeonEnemy"]] = relationship("DungeonEnemy", back_populates="dungeon", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Dungeon(id={self.id}, stage={self.current_stage}/{self.total_stages}, status={self.status})>"


class DungeonEnemy(Base, TimestampMixin):
    """An enemy in a dungeon stage.

    Each stage has one enemy (a bot player) that must be defeated.
    """

    __tablename__ = "dungeon_enemies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dungeon_id: Mapped[int] = mapped_column(Integer, ForeignKey("dungeons.id"), nullable=False, index=True)
    stage: Mapped[int] = mapped_column(Integer, nullable=False)

    # Enemy is a bot player
    enemy_player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)

    # Was this enemy defeated?
    defeated: Mapped[bool] = mapped_column(Integer, nullable=False, default=False)

    # Relationships
    dungeon: Mapped["Dungeon"] = relationship("Dungeon", back_populates="enemies")
    enemy_player: Mapped["Player"] = relationship("Player")

    def __repr__(self) -> str:
        return f"<DungeonEnemy(dungeon={self.dungeon_id}, stage={self.stage}, defeated={self.defeated})>"


# Forward references
from .duels import Duel  # noqa: E402, F401
from .players import Player  # noqa: E402, F401
from .settings import Setting  # noqa: E402, F401
