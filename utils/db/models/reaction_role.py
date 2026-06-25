"""
utils/db/models/reaction_role.py — Modèles du système de rôle-réaction.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cogs.api.base import Base, TimestampMixin


class ReactionRoleMessage(Base, TimestampMixin):
    """Un message rôle-réaction posté dans un salon."""

    __tablename__ = "reaction_role_messages"

    message_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    couples: Mapped[list["ReactionRoleCouple"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    def to_dict(self) -> dict:
        """Crée une représentation dict du message."""

        return {
            "message_id": self.message_id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "description": self.description,
            "reactions": [
                {"emoji": c.emoji, "role_id": c.role_id}
                for c in sorted(self.couples, key=lambda c: c.id)
            ],
        }

    def __repr__(self) -> str:
        return (
            f"<ReactionRoleMessage message_id={self.message_id} "
            f"guild_id={self.guild_id} couples={len(self.couples)}>"
        )


class ReactionRoleCouple(Base):
    """Un couple emoji → rôle rattaché à un message rôle-réaction."""

    __tablename__ = "reaction_role_couples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    message_fk: Mapped[int] = mapped_column(
        ForeignKey("reaction_role_messages.message_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    emoji: Mapped[str] = mapped_column(String(100), nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    message: Mapped["ReactionRoleMessage"] = relationship(back_populates="couples")

    __table_args__ = (
        UniqueConstraint("message_fk", "emoji", name="uq_reaction_role_couple_emoji"),
        Index("ix_reaction_role_couple_lookup", "message_fk", "emoji"),
    )

    def __repr__(self) -> str:
        return (
            f"<ReactionRoleCouple msg_fk={self.message_fk} "
            f"emoji={self.emoji!r} role_id={self.role_id}>"
        )