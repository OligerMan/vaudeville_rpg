"""Admin models - pending operations and admin state."""

from datetime import datetime, timedelta

from sqlalchemy import BigInteger, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

# Expiry time for pending generations (5 minutes)
PENDING_GENERATION_EXPIRY_MINUTES = 5


class PendingGeneration(Base):
    """Stores pending setting generation requests awaiting confirmation."""

    __tablename__ = "pending_generations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def is_expired(self) -> bool:
        """Check if this pending generation has expired."""
        expiry = self.created_at + timedelta(minutes=PENDING_GENERATION_EXPIRY_MINUTES)
        return datetime.now(self.created_at.tzinfo) > expiry
