"""
utils/db/models/join_to_create.py — Config et suivi du système "Join to Create".
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class JoinToCreateConfig(Base, TimestampMixin):
    """Configuration d'une voc déclencheur."""

    __tablename__ = "join_to_create_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    trigger_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trigger_channel_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        UniqueConstraint("guild_id", "category_id", name="uq_join_to_create_guild_category"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "trigger_channel_id": self.trigger_channel_id,
            "trigger_channel_name": self.trigger_channel_name,
            "category_id": self.category_id,
        }


class JoinToCreateChannel(Base, TimestampMixin):
    """Un salon vocal généré par le système, à supprimer automatiquement une fois vide."""

    __tablename__ = "join_to_create_channels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("channel_id", name="uq_join_to_create_channel_id"),
        Index("ix_join_to_create_channel_guild", "guild_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "owner_id": self.owner_id,
        }