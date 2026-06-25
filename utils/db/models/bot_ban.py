"""
utils/db/models/bot_ban.py — Modèle BotBan, bans globaux d'utilisation du bot.

Tous les bans sont des tempbans (durée en jours) — pas de notion de ban
"permanent" distincte en DB ; la convention pour un ban effectivement
permanent est une durée de 9999 jours (voir cogs/dev/botban.py).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class BotBan(Base, TimestampMixin):
    """Un ban actif (ou passé) d'utilisation du bot. Clé unique : discord_id."""

    __tablename__ = "bot_bans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    raison: Mapped[str] = mapped_column(String(512), nullable=False)
    moderator_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    date_ban: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expiration: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def to_dict(self) -> dict:
        return {
            "discord_id": self.discord_id,
            "raison": self.raison,
            "moderator_id": self.moderator_id,
            "date_ban": self.date_ban,
            "expiration": self.expiration,
        }

    def __repr__(self) -> str:
        return f"<BotBan discord_id={self.discord_id} expiration={self.expiration}>"