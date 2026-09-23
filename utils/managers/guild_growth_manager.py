"""
utils/managers/guild_growth_manager.py — Lecture/écriture des événements
d'ajout/retrait du BOT sur des serveurs Discord (table bot_guild_events).

Pas d'upsert ici (contrairement à command_stats_manager/guild_stats_manager) :
chaque événement est une ligne distincte avec son propre timestamp, nécessaire
pour la rétention par cohorte.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta, timezone, datetime

from sqlalchemy import func, select, case

from utils.db.models.bot_guild_event import BotGuildEvent
from utils.db.session import get_session

log = logging.getLogger(__name__)


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


# ════════════════════════════════════════════════════════════
# ✍️ Écriture
# ════════════════════════════════════════════════════════════

async def record_join(guild_id: int, guild_name: str | None, member_count: int | None) -> None:
    async with get_session() as session:
        session.add(BotGuildEvent(
            guild_id=guild_id, event_type="join",
            guild_name=guild_name, member_count=member_count,
        ))


async def record_leave(guild_id: int, guild_name: str | None, member_count: int | None) -> None:
    async with get_session() as session:
        session.add(BotGuildEvent(
            guild_id=guild_id, event_type="leave",
            guild_name=guild_name, member_count=member_count,
        ))


# ════════════════════════════════════════════════════════════
# 📖 Lecture
# ════════════════════════════════════════════════════════════

async def get_current_guild_count() -> int:
    """Nombre net de serveurs actuellement installés (joins - leaves)."""
    stmt = select(func.sum(case((BotGuildEvent.event_type == "join", 1), else_=-1)))
    async with get_session() as session:
        result = await session.execute(stmt)
        return int(result.scalar_one() or 0)


async def get_growth_series(days: int = 30) -> list[dict]:
    """[{"date", "joins", "leaves"}, ...] un point par jour, sans trou."""
    today = _today_utc()
    start = today - timedelta(days=days - 1)

    stmt = select(
        func.date(BotGuildEvent.created_at).label("d"),
        func.sum(case((BotGuildEvent.event_type == "join", 1), else_=0)).label("joins"),
        func.sum(case((BotGuildEvent.event_type == "leave", 1), else_=0)).label("leaves"),
    ).where(
        func.date(BotGuildEvent.created_at) >= start,
        func.date(BotGuildEvent.created_at) <= today,
    ).group_by(func.date(BotGuildEvent.created_at))

    async with get_session() as session:
        rows = (await session.execute(stmt)).all()

    by_date = {r.d: (int(r.joins), int(r.leaves)) for r in rows}
    return [
        {
            "date": start + timedelta(days=i),
            "joins": by_date.get(start + timedelta(days=i), (0, 0))[0],
            "leaves": by_date.get(start + timedelta(days=i), (0, 0))[1],
        }
        for i in range(days)
    ]


async def get_retention(days: int = 30) -> dict:
    """
    Sur les serveurs dont la PREMIÈRE arrivée du bot date d'au moins `days`
    jours, quelle proportion a toujours le bot aujourd'hui ?
    """
    cutoff = _today_utc() - timedelta(days=days)

    first_join = (
        select(
            BotGuildEvent.guild_id,
            func.min(BotGuildEvent.created_at).label("first_join"),
        )
        .where(BotGuildEvent.event_type == "join")
        .group_by(BotGuildEvent.guild_id)
        .subquery()
    )

    rn = func.row_number().over(
        partition_by=BotGuildEvent.guild_id,
        order_by=BotGuildEvent.created_at.desc(),
    ).label("rn")
    ranked = select(BotGuildEvent.guild_id, BotGuildEvent.event_type, rn).subquery()
    last_status = select(ranked.c.guild_id, ranked.c.event_type).where(ranked.c.rn == 1).subquery()

    async with get_session() as session:
        cohort_size = (await session.execute(
            select(func.count()).select_from(first_join)
            .where(func.date(first_join.c.first_join) <= cutoff)
        )).scalar_one()

        still_present = (await session.execute(
            select(func.count())
            .select_from(first_join.join(last_status, first_join.c.guild_id == last_status.c.guild_id))
            .where(
                func.date(first_join.c.first_join) <= cutoff,
                last_status.c.event_type == "join",
            )
        )).scalar_one()

    rate = (still_present / cohort_size * 100) if cohort_size else None
    return {"days": days, "cohort_size": cohort_size, "still_present": still_present, "retention_rate": rate}