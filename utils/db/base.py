"""
utils/db/base.py — Base SQLAlchemy pour tous les modèles
"""

from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.orm import declarative_base, Mapped, mapped_column

Base = declarative_base()


class TimestampMixin:
    """Mixin pour ajouter created_at et updated_at à tous les modèles."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )