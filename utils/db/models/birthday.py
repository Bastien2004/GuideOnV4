"""
utils/db/models/birthday.py — Modèles du système d'anniversaires utilisateurs.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class BirthdayConfig(Base, TimestampMixin):
    """Configuration du système d'anniversaires pour un serveur."""

    __tablename__ = "birthday_configs"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "channel_id": self.channel_id,
            "role_id": self.role_id,
        }

    def __repr__(self) -> str:
        return (
            f"<BirthdayConfig guild_id={self.guild_id} enabled={self.enabled} "
            f"channel={self.channel_id} role={self.role_id}>"
        )


class BirthdayUser(Base, TimestampMixin):
    """Date d'anniversaire d'un utilisateur sur un serveur."""

    __tablename__ = "birthday_users"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    day: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (Index("ix_birthday_users_guild_month_day", "guild_id", "month", "day"),)

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "user_id": self.user_id,
            "day": self.day,
            "month": self.month,
            "year": self.year,
        }

    def __repr__(self) -> str:
        return (
            f"<BirthdayUser guild_id={self.guild_id} user_id={self.user_id} "
            f"date={self.day:02d}/{self.month:02d}"
            f"{('/' + str(self.year)) if self.year else ''}>"
        )