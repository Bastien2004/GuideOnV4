"""
utils/managers/command_stats_manager.py — Lecture/écriture des stats
quotidiennes d'usage de commandes (table command_stats_daily).

API publique :
    await increment_command_stat(command_name, on_date=None) -> None
        Incrémente le compteur du jour (upsert atomique). on_date=None = aujourd'hui (UTC).
    await get_totals_by_command() -> list[dict]
        [{"command_name": str, "total": int}], triés par total décroissant.
    await get_podium(top_n=3) -> list[dict]
        Les top_n commandes les plus utilisées (total all-time).
    await get_daily_series(days=7) -> list[dict]
        [{"date": date, "total": int}] pour les `days` derniers jours
        (incluant aujourd'hui), un point par jour même si total=0,
        triés chronologiquement.
    await get_grand_total() -> int
        Somme de tous les usages, toutes commandes confondues.

Pas de cache mémoire ici : ces données sont lues à la demande (commande
dev peu fréquente) et doivent refléter l'état exact de la DB sans délai TTL.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta, timezone, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from utils.db.models.command_stats import CommandStatDaily
from utils.db.session import get_session

log = logging.getLogger(__name__)


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


# ════════════════════════════════════════════════════════════
# ✍️ Écriture
# ════════════════════════════════════════════════════════════

async def increment_command_stat(command_name: str, on_date: date | None = None) -> None:
    """
    Incrémente (ou crée) le compteur du jour pour `command_name`.
    Upsert atomique côté DB — pas de race condition même avec des
    incréments concurrents sur le même (command_name, date).
    """
    target_date = on_date or _today_utc()

    stmt = pg_insert(CommandStatDaily).values(
        command_name=command_name,
        stat_date=target_date,
        count=1,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["command_name", "stat_date"],
        set_={"count": CommandStatDaily.count + 1},
    )

    async with get_session() as session:
        await session.execute(stmt)


# ════════════════════════════════════════════════════════════
# 📖 Lecture
# ════════════════════════════════════════════════════════════

async def get_totals_by_command() -> list[dict]:
    """Total all-time par commande, triés par total décroissant puis nom."""
    stmt = (
        select(
            CommandStatDaily.command_name,
            func.sum(CommandStatDaily.count).label("total"),
        )
        .group_by(CommandStatDaily.command_name)
        .order_by(func.sum(CommandStatDaily.count).desc(), CommandStatDaily.command_name.asc())
    )
    async with get_session() as session:
        rows = (await session.execute(stmt)).all()
    return [{"command_name": r.command_name, "total": int(r.total)} for r in rows]


async def get_podium(top_n: int = 3) -> list[dict]:
    """Top `top_n` commandes les plus utilisées (total all-time)."""
    totals = await get_totals_by_command()
    return totals[:top_n]


async def get_daily_series(days: int = 7) -> list[dict]:
    """
    Série temporelle de l'usage TOTAL (toutes commandes confondues) sur les
    `days` derniers jours (incluant aujourd'hui). Un point par jour, même
    si le total est 0 ce jour-là (pas de trou dans le graphique).
    """
    today = _today_utc()
    start = today - timedelta(days=days - 1)

    stmt = (
        select(
            CommandStatDaily.stat_date,
            func.sum(CommandStatDaily.count).label("total"),
        )
        .where(CommandStatDaily.stat_date >= start, CommandStatDaily.stat_date <= today)
        .group_by(CommandStatDaily.stat_date)
    )
    async with get_session() as session:
        rows = (await session.execute(stmt)).all()

    by_date = {r.stat_date: int(r.total) for r in rows}
    return [
        {"date": start + timedelta(days=i), "total": by_date.get(start + timedelta(days=i), 0)}
        for i in range(days)
    ]


async def get_grand_total() -> int:
    """Somme de tous les usages, toutes commandes et toutes dates confondues."""
    stmt = select(func.coalesce(func.sum(CommandStatDaily.count), 0))
    async with get_session() as session:
        result = await session.execute(stmt)
        return int(result.scalar_one())