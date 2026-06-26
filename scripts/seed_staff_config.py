"""
utils/db/models/staff.py — Modèle Staff pour la V4
"""
from __future__ import annotations

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base  # ✅ AJOUTER


class StaffConfig(Base):
    """Configuration et liste du staff."""

    __tablename__ = "staff_config"

    # PK = toujours 1 (une seule config par bot)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # Configuration (String pour les IDs Discord qui sont trop longs)
    guild_id: Mapped[str] = mapped_column(String(20), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(20), nullable=False)
    message_id: Mapped[str] = mapped_column(String(20), default="0")
    update_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)

    # Listes JSON
    grades_order: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    staff: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "update_interval_minutes": self.update_interval_minutes,
            "grades_order": self.grades_order or [],
            "staff": self.staff or [],
        }

    def __repr__(self) -> str:
        return f"<StaffConfig guild={self.guild_id} staff_count={len(self.staff or [])}>"