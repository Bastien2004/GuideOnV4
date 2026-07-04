"""
utils/db/base.py — Base SQLAlchemy pour tous les modèles
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):

    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)


class TimestampMixin:
    """Ajout de created_at et updated_at à tous les modèles."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False
    )