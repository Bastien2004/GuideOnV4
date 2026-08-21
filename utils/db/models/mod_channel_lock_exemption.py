"""
utils/db/models/mod_channel_lock_exemption.py — Traçabilité des exemptions de lock.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class ModChannelLockExemption(Base, TimestampMixin):
    """Un rôle exempté par /mod lock sur un salon précis, à retirer par /mod unlock."""

    __tablename__ = "mod_channel_lock_exemptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("channel_id", "role_id", name="uq_lock_exemption_channel_role"),
        Index("ix_lock_exemption_channel", "channel_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "role_id": self.role_id,
        }