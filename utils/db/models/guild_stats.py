"""
utils/db/models/guild_stats.py — Statistiques serveur pour le dashboard
GuideOn Iris (arrivées/départs/vocal/messages/membres actifs/classement).

Deux tables en rollup quotidien (même principe que command_stats.py, avec
guild_id en plus puisqu'ici c'est PAR serveur NationsGlory) :

- GuildActivityStatDaily : 1 ligne par (guild_id, stat_date). Compteurs
  agrégés au niveau du serveur : arrivées, départs, minutes de vocal
  cumulées (tous membres confondus). Alimente les compteurs du haut du
  dashboard et le "Graphique".

- GuildMessageStatDaily : 1 ligne par (guild_id, user_id, stat_date).
  Nombre de messages envoyés par CE membre CE jour-là. Une seule table
  à granularité fine (par membre) plutôt que trois tables séparées :
  toute agrégation moins fine s'obtient par simple GROUP BY depuis
  celle-ci (cf. utils/managers/guild_stats_manager.py) —
    - total "Messages envoyés" du serveur : SUM sur tous les membres,
    - "Membres actifs" : COUNT DISTINCT user_id sur une fenêtre glissante,
    - "Classement message" (jour/semaine/mois/année) : GROUP BY user_id.

Toutes les dates sont bucketées en UTC (même convention que
command_stats_manager.py) — la conversion en fuseau d'affichage reste
une responsabilité du site/API, pas du bot.
"""
from __future__ import annotations

from datetime import date as date_type

from sqlalchemy import BigInteger, Date, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class GuildActivityStatDaily(Base, TimestampMixin):
    """Compteurs serveur agrégés (arrivées/départs/vocal) pour un jour donné (UTC)."""

    __tablename__ = "guild_activity_stats_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stat_date: Mapped[date_type] = mapped_column(Date, nullable=False)

    arrivals: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    departures: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    voice_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        UniqueConstraint("guild_id", "stat_date", name="uq_guild_activity_stats_daily_guild_date"),
        Index("ix_guild_activity_stats_daily_guild_date", "guild_id", "stat_date"),
    )

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "stat_date": self.stat_date,
            "arrivals": self.arrivals,
            "departures": self.departures,
            "voice_minutes": self.voice_minutes,
        }

    def __repr__(self) -> str:
        return (
            f"<GuildActivityStatDaily guild={self.guild_id} {self.stat_date} "
            f"arrivals={self.arrivals} departures={self.departures} voice_minutes={self.voice_minutes}>"
        )


class GuildMessageStatDaily(Base, TimestampMixin):
    """Nombre de messages envoyés par un membre, pour un jour donné (UTC)."""

    __tablename__ = "guild_message_stats_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stat_date: Mapped[date_type] = mapped_column(Date, nullable=False)

    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", "stat_date", name="uq_guild_message_stats_daily_guild_user_date"),
        Index("ix_guild_message_stats_daily_guild_date", "guild_id", "stat_date"),
        Index("ix_guild_message_stats_daily_guild_user", "guild_id", "user_id"),
    )

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "user_id": self.user_id,
            "stat_date": self.stat_date,
            "message_count": self.message_count,
        }

    def __repr__(self) -> str:
        return (
            f"<GuildMessageStatDaily guild={self.guild_id} user={self.user_id} "
            f"{self.stat_date} count={self.message_count}>"
        )