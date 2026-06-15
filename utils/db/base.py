"""
utils/db/base.py — Base de tous les modèles SQLAlchemy.
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Classe parente de tous les modèles."""
    pass


class TimestampMixin:
    """Ajoute created_at et updated_at automatiquement à une table."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )