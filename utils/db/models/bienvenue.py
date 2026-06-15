"""
utils/db/models/bienvenue.py — Configuration du système de bienvenue par serveur.

Remplace l'ancien fichier unique config_bienvenue.json {guild_id: {...}}.
Une ligne = la config d'un serveur (PK = guild_id).
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin

# Messages par défaut (repris à l'identique de la V3 pour ne rien casser).
DEFAULT_ARRIVE_MESSAGE = (
    "{mention} Bienvenue sur le serveur {server} ! "
    "Nous sommes maintenant {member_count} !"
)
DEFAULT_DEPART_MESSAGE = (
    "{user} a quitté le serveur. Nous sommes maintenant {member_count}."
)


class BienvenueConfig(Base, TimestampMixin):
    __tablename__ = "bienvenue_configs"

    # guild_id en PK : une seule config par serveur. BigInteger car snowflake.
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    system_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    arrive_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    depart_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    arrive_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    depart_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    arrive_message: Mapped[str] = mapped_column(
        Text, default=DEFAULT_ARRIVE_MESSAGE, nullable=False
    )
    depart_message: Mapped[str] = mapped_column(
        Text, default=DEFAULT_DEPART_MESSAGE, nullable=False
    )

    def to_dict(self) -> dict:
        """Représentation dict compatible avec le format de config V3."""
        return {
            "system_active": self.system_active,
            "arrive_active": self.arrive_active,
            "depart_active": self.depart_active,
            "arrive_channel_id": self.arrive_channel_id,
            "depart_channel_id": self.depart_channel_id,
            "arrive_message": self.arrive_message,
            "depart_message": self.depart_message,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"<BienvenueConfig guild_id={self.guild_id} "
            f"system_active={self.system_active}>"
        )