"""
utils/db/models/giveaway.py — Modèles du système de giveaway.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


GIVEAWAY_ID_LENGTH = 8
PRIZE_MAX_LENGTH = 500
REASON_MAX_LENGTH = 500


class Giveaway(Base, TimestampMixin):
    """Métadonnées d'un giveaway."""

    __tablename__ = "giveaways"

    id: Mapped[str] = mapped_column(String(GIVEAWAY_ID_LENGTH), primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    host_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    prize: Mapped[str] = mapped_column(String(PRIZE_MAX_LENGTH), nullable=False)
    winners_count: Mapped[int] = mapped_column(Integer, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    ended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    winners: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    requirements: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_giveaways_guild", "guild_id"),
        Index("ix_giveaways_guild_msg", "guild_id", "message_id"),
        Index("ix_giveaways_guild_ended", "guild_id", "ended"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "host_id": self.host_id,
            "prize": self.prize,
            "winners_count": self.winners_count,
            "end_time": self.end_time,
            "ended": self.ended,
            "winners": list(self.winners or []),
            "requirements": dict(self.requirements or {}),
        }

    def __repr__(self) -> str:
        return (
            f"<Giveaway id={self.id} guild={self.guild_id} prize={self.prize!r} "
            f"ended={self.ended}>"
        )


class GiveawayParticipant(Base, TimestampMixin):
    """Participants d'un giveaway."""

    __tablename__ = "giveaway_participants"

    giveaway_id: Mapped[str] = mapped_column(String(GIVEAWAY_ID_LENGTH), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    __table_args__ = (Index("ix_giveaway_participants_giveaway", "giveaway_id"),)

    def to_dict(self) -> dict:
        return {
            "giveaway_id": self.giveaway_id,
            "user_id": self.user_id,
            "joined_at": self.created_at,
        }

    def __repr__(self) -> str:
        return f"<GiveawayParticipant giveaway={self.giveaway_id} user={self.user_id}>"


class GiveawayBlacklist(Base, TimestampMixin):
    """Liste noire des utilisateurs interdits de giveaway sur un serveur."""

    __tablename__ = "giveaway_blacklist"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    reason: Mapped[str | None] = mapped_column(String(REASON_MAX_LENGTH), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    added_by: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (Index("ix_giveaway_blacklist_guild", "guild_id"),)

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "user_id": self.user_id,
            "reason": self.reason,
            "expires_at": self.expires_at,
            "added_by": self.added_by,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"<GiveawayBlacklist guild={self.guild_id} user={self.user_id} "
            f"expires={self.expires_at}>"
        )