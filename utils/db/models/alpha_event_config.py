"""
utils/db/models/alpha_event_config.py — Config du système Events Alpha.
Stocke uniquement le salon d'annonce et le rôle de ping.
Les données des events (nom, warp, image, statut) sont dans events_alpha.json.
"""
from __future__ import annotations

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from cogs.api.base import Base, TimestampMixin


class AlphaEventConfig(Base, TimestampMixin):
    __tablename__ = "alpha_event_configs"

    guild_id:     Mapped[int]       = mapped_column(BigInteger, primary_key=True)
    channel_id:   Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ping_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    def to_dict(self) -> dict:
        return {
            "guild_id":     self.guild_id,
            "channel_id":   self.channel_id,
            "ping_role_id": self.ping_role_id,
        }