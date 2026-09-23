"""
utils/db/models/bot_guild_event.py — historique des ajouts/retraits du BOT
sur des serveurs Discord (croissance produit, pas activité communautaire —
voir guild_stats.py pour les arrivées/départs de MEMBRES sur un serveur).
"""
from __future__ import annotations

from sqlalchemy import BigInteger, String, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class BotGuildEvent(Base, TimestampMixin):
    __tablename__ = "bot_guild_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "join" ou "leave"
    guild_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_bot_guild_events_guild_date", "guild_id", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "event_type": self.event_type,
            "guild_name": self.guild_name,
            "member_count": self.member_count,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return f"<BotGuildEvent guild_id={self.guild_id} type={self.event_type}>"