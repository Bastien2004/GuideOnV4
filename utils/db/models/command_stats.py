"""
utils/db/models/command_stats.py — Modèle CommandStatDaily, compteur
d'utilisation quotidien par commande.

Une ligne par (command_name, stat_date), incrémentée à chaque usage via
upsert (ON CONFLICT DO UPDATE count = count + 1). Permet à la fois le
total all-time (somme sur toutes les dates) et un graphique d'évolution
(group by date).
"""
from __future__ import annotations

from datetime import date as date_type

from sqlalchemy import BigInteger, Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from cogs.api.base import Base, TimestampMixin


class CommandStatDaily(Base, TimestampMixin):
    """Compteur d'utilisation d'une commande pour un jour donné (UTC)."""

    __tablename__ = "command_stats_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    command_name: Mapped[str] = mapped_column(String(64), nullable=False)
    stat_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        UniqueConstraint("command_name", "stat_date", name="uq_command_stats_daily_cmd_date"),
        Index("ix_command_stats_daily_date", "stat_date"),
        Index("ix_command_stats_daily_command", "command_name"),
    )

    def to_dict(self) -> dict:
        return {
            "command_name": self.command_name,
            "stat_date": self.stat_date,
            "count": self.count,
        }

    def __repr__(self) -> str:
        return f"<CommandStatDaily {self.command_name!r} {self.stat_date} count={self.count}>"