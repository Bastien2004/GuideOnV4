"""
utils/db/models/invite.py — Modèles du système d'invite tracking.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin

DEFAULT_REWARD_THRESHOLD = 10


class InviteConfig(Base, TimestampMixin):
    """Configuration du système d'invitations pour un serveur."""

    __tablename__ = "invite_configs"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    reward_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reward_threshold: Mapped[int] = mapped_column(Integer, default=DEFAULT_REWARD_THRESHOLD, nullable=False)

    def to_dict(self) -> dict:
        """Représentation dict de la config."""
        return {
            "enabled": self.enabled,
            "reward_role_id": self.reward_role_id,
            "reward_threshold": self.reward_threshold,
        }

    def __repr__(self) -> str:
        return (
            f"<InviteConfig guild_id={self.guild_id} enabled={self.enabled} "
            f"reward_role_id={self.reward_role_id} threshold={self.reward_threshold}>"
        )


class InviteStat(Base, TimestampMixin):
    """Compteurs d'invitations d'un membre sur un serveur."""

    __tablename__ = "invite_stats"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    regular: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fake: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    left: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (Index("ix_invite_stats_guild", "guild_id"),)

    @property
    def total(self) -> int:
        """Total effectif : regular + bonus - fake - left ."""
        return self.regular + self.bonus - self.fake - self.left

    def to_dict(self) -> dict:
        """Représentation dict."""
        return {
            "regular": self.regular,
            "fake": self.fake,
            "bonus": self.bonus,
            "left": self.left,
            "total": self.total,
        }

    def __repr__(self) -> str:
        return (
            f"<InviteStat guild_id={self.guild_id} user_id={self.user_id} "
            f"total={self.total} (reg={self.regular} bonus={self.bonus} "
            f"fake={self.fake} left={self.left})>"
        )


class InviteLink(Base, TimestampMixin):
    """Lien d'invitation : quel membre a été invité par qui."""

    __tablename__ = "invite_links"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    member_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    inviter_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    invite_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    is_fake: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    counted_left: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (Index("ix_invite_links_inviter", "guild_id", "inviter_id"),)

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "member_id": self.member_id,
            "inviter_id": self.inviter_id,
            "invite_code": self.invite_code,
            "is_fake": self.is_fake,
            "counted_left": self.counted_left,
        }

    def __repr__(self) -> str:
        return (
            f"<InviteLink guild_id={self.guild_id} member_id={self.member_id} "
            f"inviter_id={self.inviter_id} code={self.invite_code!r} "
            f"is_fake={self.is_fake} counted_left={self.counted_left}>"
        )