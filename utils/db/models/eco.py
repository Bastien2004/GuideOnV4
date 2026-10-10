"""
utils/db/models/eco.py — Modèles du système d'économie (/eco).
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin

DEFAULT_DAILY_AMOUNT = 200
DEFAULT_LEADERBOARD_ENABLED = True


class EcoTransactionType(str, enum.Enum):
    """Type d'action logguée."""

    DAILY = "daily"
    ADMIN_ADD = "admin_add"
    ADMIN_REMOVE = "admin_remove"


class EcoConfig(Base, TimestampMixin):
    """Configuration du système d'économie pour un serveur."""

    __tablename__ = "eco_configs"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    daily_amount: Mapped[int] = mapped_column(Integer, default=DEFAULT_DAILY_AMOUNT, nullable=False, server_default=str(DEFAULT_DAILY_AMOUNT))
    leaderboard_enabled: Mapped[bool] = mapped_column(Boolean, default=DEFAULT_LEADERBOARD_ENABLED, nullable=False, server_default="true")

    def to_dict(self) -> dict:
        """Représentation dict de la config."""

        return {
            "daily_amount": self.daily_amount,
            "leaderboard_enabled": self.leaderboard_enabled,
        }

    def __repr__(self) -> str:
        return (
            f"<EcoConfig guild_id={self.guild_id} daily_amount={self.daily_amount} "
            f"leaderboard_enabled={self.leaderboard_enabled}>"
        )


class EcoAccount(Base, TimestampMixin):
    """Solde d'un membre sur un serveur donné."""

    __tablename__ = "eco_accounts"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False, server_default="0")
    last_daily_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_eco_accounts_guild", "guild_id"),
    )

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "user_id": self.user_id,
            "balance": self.balance,
            "last_daily_at": self.last_daily_at,
        }

    def __repr__(self) -> str:
        return (
            f"<EcoAccount guild_id={self.guild_id} user_id={self.user_id} "
            f"balance={self.balance} last_daily_at={self.last_daily_at}>"
        )


class EcoTransactionLog(Base, TimestampMixin):
    """Historique des actions."""

    __tablename__ = "eco_transaction_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    type: Mapped[EcoTransactionType] = mapped_column(
        Enum(EcoTransactionType, name="eco_transaction_type", native_enum=False, length=16),
        nullable=False,
    )

    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_eco_tx_guild_user", "guild_id", "user_id"),
        Index("ix_eco_tx_guild_created", "guild_id", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "user_id": self.user_id,
            "type": self.type.value,
            "amount": self.amount,
            "balance_after": self.balance_after,
            "actor_id": self.actor_id,
            "reason": self.reason,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"<EcoTransactionLog id={self.id} guild_id={self.guild_id} "
            f"user_id={self.user_id} type={self.type.value} amount={self.amount} "
            f"balance_after={self.balance_after}>"
        )