"""
utils/db/models/alpha_role_react.py — Modèles du système Rôle Réaction Alpha.

AlphaRoleReactConfig  : config principale par guild (salon cible + message_id)
AlphaRoleReactEntry   : jusqu'à 10 rôles configurables (label, emoji, description)
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from cogs.api.base import Base, TimestampMixin

MAX_ROLES = 10


class AlphaRoleReactConfig(Base, TimestampMixin):
    __tablename__ = "alpha_role_react_configs"

    guild_id:   Mapped[int]       = mapped_column(BigInteger, primary_key=True)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    def to_dict(self) -> dict:
        return {
            "guild_id":   self.guild_id,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
        }


class AlphaRoleReactEntry(Base, TimestampMixin):
    """Un rôle dans la liste. position détermine l'ordre d'affichage (0–9)."""
    __tablename__ = "alpha_role_react_entries"

    id:          Mapped[int]       = mapped_column(primary_key=True, autoincrement=True)
    guild_id:    Mapped[int]       = mapped_column(BigInteger, nullable=False)
    position:    Mapped[int]       = mapped_column(Integer,    nullable=False)
    role_id:     Mapped[int]       = mapped_column(BigInteger, nullable=False)
    label:       Mapped[str]       = mapped_column(String(80),  nullable=False)
    emoji:       Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint("guild_id", "position", name="uq_role_react_pos"),
        UniqueConstraint("guild_id", "role_id",  name="uq_role_react_role"),
        Index("ix_role_react_guild", "guild_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "guild_id":    self.guild_id,
            "position":    self.position,
            "role_id":     self.role_id,
            "label":       self.label,
            "emoji":       self.emoji,
            "description": self.description,
        }