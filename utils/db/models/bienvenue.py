"""
utils/db/models/bienvenue.py — Configuration du système de bienvenue.
"""

from __future__ import annotations

import enum

from sqlalchemy import BigInteger, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


# ============================================================
# 📦 Constantes
# ============================================================

DEFAULT_ARRIVE_MESSAGE = (
    "{mention} Bienvenue sur le serveur {server} ! "
    "Nous sommes maintenant {member_count} !"
)

DEFAULT_DEPART_MESSAGE = (
    "{user} a quitté le serveur. Nous sommes maintenant {member_count}."
)


# ============================================================
# 🔩 Class utilitaire
# ============================================================

class BienvenueFormat(str, enum.Enum):
    """Format d'affichage du message."""

    EMBED = "embed"
    TEXT = "text"


# ============================================================
# 🧩 Class principale
# ============================================================

class BienvenueConfig(Base, TimestampMixin):
    __tablename__ = "bienvenue_configs"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    system_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    arrive_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    depart_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    arrive_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    depart_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    arrive_message: Mapped[str] = mapped_column(Text, default=DEFAULT_ARRIVE_MESSAGE, nullable=False)
    depart_message: Mapped[str] = mapped_column(Text, default=DEFAULT_DEPART_MESSAGE, nullable=False)

    arrive_format: Mapped[str] = mapped_column(Text, default=BienvenueFormat.EMBED.value, nullable=False)
    depart_format: Mapped[str] = mapped_column(Text, default=BienvenueFormat.EMBED.value, nullable=False)

    arrive_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    depart_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)


    def to_dict(self) -> dict:
        """Représentation dict de la configuration."""

        return {
            "system_active": self.system_active,
            "arrive_active": self.arrive_active,
            "depart_active": self.depart_active,
            "arrive_channel_id": self.arrive_channel_id,
            "depart_channel_id": self.depart_channel_id,
            "arrive_message": self.arrive_message,
            "depart_message": self.depart_message,
            "arrive_format": self.arrive_format,
            "depart_format": self.depart_format,
            "arrive_image_url": self.arrive_image_url,
            "depart_image_url": self.depart_image_url,
        }

    def __repr__(self) -> str:
        return (
            f"<BienvenueConfig guild_id={self.guild_id} "
            f"system_active={self.system_active}>"
        )