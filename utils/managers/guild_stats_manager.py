"""
utils/managers/guild_stats_manager.py — Lecture/écriture des stats
serveur quotidiennes pour le dashboard GuideOn Iris (arrivées/départs/
vocal/messages/membres actifs/classement message).

Alimenté par cogs/events/guild_stats_listener.py. Bastien consomme les
fonctions de lecture ci-dessous côté API (cogs/api/*) — ce module ne
fait QUE du stockage/agrégation, aucune route HTTP ici.

API publique :

  Écriture (upserts atomiques, cf. command_stats_manager.py — même
  pattern ON CONFLICT DO UPDATE, pas de race condition) :
    await record_arrival(guild_id, on_date=None) -> None
    await record_departure(guild_id, on_date=None) -> None
    await record_voice_minutes(guild_id, minutes, on_date=None) -> None
    await record_message(guild_id, user_id, on_date=None) -> None

  Lecture :
    await get_activity_totals(guild_id, start_date, end_date) -> dict
        {"arrivals", "departures", "voice_minutes", "messages"} sur une
        plage de dates arbitraire (bornes incluses).
    await get_period_totals(guild_id, period) -> dict
        Idem, pour une période nommée : "today" / "yesterday" / "week"
        (semaine ISO, lundi→aujourd'hui) / "month" (mois calendaire en
        cours) / "year" (année calendaire en cours). Ajoute "period",
        "start_date", "end_date" au dict renvoyé par get_activity_totals.
    await get_daily_series(guild_id, days=30) -> list[dict]
        Un point par jour sur les `days` derniers jours (aujourd'hui
        inclus), même à 0 — pas de trou dans le graphique (même
        principe que command_stats_manager.get_daily_series).
    await get_monthly_series(guild_id, months=12) -> list[dict]
        Un point par mois calendaire sur les `months` derniers mois
        (mois en cours inclus), même à 0 — pour la vue "12 mois".
    await get_active_members_count(guild_id, days=7) -> int
        Nombre de membres distincts ayant envoyé au moins un message
        dans les `days` derniers jours (fenêtre glissante, bornes
        incluses, "aujourd'hui" compte comme un des `days` jours).
    await get_message_leaderboard(guild_id, period, limit=10) -> list[tuple[int, int]]
        [(user_id, total_messages), ...] triés décroissant, sur une
        période nommée ("day" / "week" / "month" / "year" — mêmes bornes
        que get_period_totals ci-dessus, "day" = aujourd'hui uniquement).

Aucun cache mémoire ici (comme command_stats_manager.py) : ces données
sont lues à la demande côté API/dashboard, pas dans une boucle de
commande chaude — elles doivent refléter l'état exact de la DB.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta, timezone, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from utils.db.models.guild_stats import GuildActivityStatDaily, GuildMessageStatDaily
from utils.db.session import get_session

log = logging.getLogger(__name__)

_VALID_PERIODS = ("today", "yesterday", "week", "month", "year")


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _period_bounds(period: str, today: date | None = None) -> tuple[date, date]:
    """Bornes (incluses) d'une période nommée, ancrée sur `today` (UTC)."""
    if period not in _VALID_PERIODS:
        raise ValueError(f"Période inconnue : {period!r} (attendu : {_VALID_PERIODS})")

    today = today or _today_utc()

    if period == "today":
        return today, today
    if period == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if period == "week":
        start = today - timedelta(days=today.weekday())  # lundi de la semaine en cours
        return start, today
    if period == "month":
        return today.replace(day=1), today
    # period == "year"
    return today.replace(month=1, day=1), today


# ════════════════════════════════════════════════════════════
# ✍️ Écriture
# ════════════════════════════════════════════════════════════

async def _bump_activity(
    guild_id: int, on_date: date | None, *, arrivals: int = 0, departures: int = 0, voice_minutes: int = 0,
) -> None:
    target_date = on_date or _today_utc()

    stmt = pg_insert(GuildActivityStatDaily).values(
        guild_id=guild_id,
        stat_date=target_date,
        arrivals=arrivals,
        departures=departures,
        voice_minutes=voice_minutes,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["guild_id", "stat_date"],
        set_={
            "arrivals": GuildActivityStatDaily.arrivals + stmt.excluded.arrivals,
            "departures": GuildActivityStatDaily.departures + stmt.excluded.departures,
            "voice_minutes": GuildActivityStatDaily.voice_minutes + stmt.excluded.voice_minutes,
        },
    )
    async with get_session() as session:
        await session.execute(stmt)


async def record_arrival(guild_id: int, on_date: date | None = None) -> None:
    """Incrémente le compteur d'arrivées du jour pour ce serveur."""
    await _bump_activity(guild_id, on_date, arrivals=1)


async def record_departure(guild_id: int, on_date: date | None = None) -> None:
    """Incrémente le compteur de départs du jour pour ce serveur."""
    await _bump_activity(guild_id, on_date, departures=1)


async def record_voice_minutes(guild_id: int, minutes: int, on_date: date | None = None) -> None:
    """Ajoute `minutes` au cumul vocal du jour pour ce serveur. No-op si <= 0."""
    if minutes <= 0:
        return
    await _bump_activity(guild_id, on_date, voice_minutes=minutes)


async def record_message(guild_id: int, user_id: int, on_date: date | None = None) -> None:
    """Incrémente le compteur de messages du jour pour ce membre."""
    target_date = on_date or _today_utc()

    stmt = pg_insert(GuildMessageStatDaily).values(
        guild_id=guild_id,
        user_id=user_id,
        stat_date=target_date,
        message_count=1,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["guild_id", "user_id", "stat_date"],
        set_={"message_count": GuildMessageStatDaily.message_count + 1},
    )
    async with get_session() as session:
        await session.execute(stmt)


# ════════════════════════════════════════════════════════════
# 📖 Lecture
# ════════════════════════════════════════════════════════════

async def get_activity_totals(guild_id: int, start_date: date, end_date: date) -> dict:
    """Totaux (arrivées/départs/vocal/messages) sur [start_date, end_date] (bornes incluses)."""
    async with get_session() as session:
        activity_stmt = select(
            func.coalesce(func.sum(GuildActivityStatDaily.arrivals), 0),
            func.coalesce(func.sum(GuildActivityStatDaily.departures), 0),
            func.coalesce(func.sum(GuildActivityStatDaily.voice_minutes), 0),
        ).where(
            GuildActivityStatDaily.guild_id == guild_id,
            GuildActivityStatDaily.stat_date >= start_date,
            GuildActivityStatDaily.stat_date <= end_date,
        )
        arrivals, departures, voice_minutes = (await session.execute(activity_stmt)).one()

        messages_stmt = select(
            func.coalesce(func.sum(GuildMessageStatDaily.message_count), 0)
        ).where(
            GuildMessageStatDaily.guild_id == guild_id,
            GuildMessageStatDaily.stat_date >= start_date,
            GuildMessageStatDaily.stat_date <= end_date,
        )
        messages = (await session.execute(messages_stmt)).scalar_one()

    return {
        "arrivals": int(arrivals),
        "departures": int(departures),
        "voice_minutes": int(voice_minutes),
        "messages": int(messages),
    }


async def get_period_totals(guild_id: int, period: str) -> dict:
    """Comme get_activity_totals, pour une période nommée (cf. _period_bounds)."""
    start, end = _period_bounds(period)
    totals = await get_activity_totals(guild_id, start, end)
    totals.update({"period": period, "start_date": start, "end_date": end})
    return totals


async def get_daily_series(guild_id: int, days: int = 30) -> list[dict]:
    """Série quotidienne (arrivées/départs/vocal/messages) sur les `days`
    derniers jours (aujourd'hui inclus), un point par jour même à 0."""
    today = _today_utc()
    start = today - timedelta(days=days - 1)

    async with get_session() as session:
        activity_rows = (await session.execute(
            select(
                GuildActivityStatDaily.stat_date,
                GuildActivityStatDaily.arrivals,
                GuildActivityStatDaily.departures,
                GuildActivityStatDaily.voice_minutes,
            ).where(
                GuildActivityStatDaily.guild_id == guild_id,
                GuildActivityStatDaily.stat_date >= start,
                GuildActivityStatDaily.stat_date <= today,
            )
        )).all()

        message_rows = (await session.execute(
            select(
                GuildMessageStatDaily.stat_date,
                func.sum(GuildMessageStatDaily.message_count).label("total"),
            ).where(
                GuildMessageStatDaily.guild_id == guild_id,
                GuildMessageStatDaily.stat_date >= start,
                GuildMessageStatDaily.stat_date <= today,
            ).group_by(GuildMessageStatDaily.stat_date)
        )).all()

    activity_by_date = {r.stat_date: r for r in activity_rows}
    messages_by_date = {r.stat_date: int(r.total) for r in message_rows}

    series = []
    for i in range(days):
        d = start + timedelta(days=i)
        a = activity_by_date.get(d)
        series.append({
            "date": d,
            "arrivals": a.arrivals if a else 0,
            "departures": a.departures if a else 0,
            "voice_minutes": a.voice_minutes if a else 0,
            "messages": messages_by_date.get(d, 0),
        })
    return series


async def get_monthly_series(guild_id: int, months: int = 12) -> list[dict]:
    """Série mensuelle (arrivées/départs/vocal/messages) sur les `months`
    derniers mois calendaires (mois en cours inclus), un point par mois
    même à 0 — pour la vue "12 mois" du dashboard."""
    today = _today_utc()

    year, month = today.year, today.month
    for _ in range(months - 1):
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    range_start = date(year, month, 1)

    async with get_session() as session:
        activity_rows = (await session.execute(
            select(
                GuildActivityStatDaily.stat_date,
                GuildActivityStatDaily.arrivals,
                GuildActivityStatDaily.departures,
                GuildActivityStatDaily.voice_minutes,
            ).where(
                GuildActivityStatDaily.guild_id == guild_id,
                GuildActivityStatDaily.stat_date >= range_start,
            )
        )).all()

        message_rows = (await session.execute(
            select(
                GuildMessageStatDaily.stat_date,
                func.sum(GuildMessageStatDaily.message_count).label("total"),
            ).where(
                GuildMessageStatDaily.guild_id == guild_id,
                GuildMessageStatDaily.stat_date >= range_start,
            ).group_by(GuildMessageStatDaily.stat_date)
        )).all()

    buckets: dict[tuple[int, int], dict] = {}
    for r in activity_rows:
        key = (r.stat_date.year, r.stat_date.month)
        b = buckets.setdefault(key, {"arrivals": 0, "departures": 0, "voice_minutes": 0, "messages": 0})
        b["arrivals"] += r.arrivals
        b["departures"] += r.departures
        b["voice_minutes"] += r.voice_minutes
    for r in message_rows:
        key = (r.stat_date.year, r.stat_date.month)
        b = buckets.setdefault(key, {"arrivals": 0, "departures": 0, "voice_minutes": 0, "messages": 0})
        b["messages"] += int(r.total)

    series = []
    year, month = range_start.year, range_start.month
    for _ in range(months):
        b = buckets.get((year, month), {"arrivals": 0, "departures": 0, "voice_minutes": 0, "messages": 0})
        series.append({"year": year, "month": month, **b})
        month += 1
        if month == 13:
            month = 1
            year += 1
    return series


async def get_active_members_count(guild_id: int, days: int = 7) -> int:
    """Nombre de membres distincts ayant envoyé >= 1 message dans les
    `days` derniers jours (fenêtre glissante, bornes incluses)."""
    today = _today_utc()
    start = today - timedelta(days=days - 1)

    stmt = select(func.count(func.distinct(GuildMessageStatDaily.user_id))).where(
        GuildMessageStatDaily.guild_id == guild_id,
        GuildMessageStatDaily.stat_date >= start,
        GuildMessageStatDaily.stat_date <= today,
    )
    async with get_session() as session:
        result = await session.execute(stmt)
        return int(result.scalar_one())


async def get_message_leaderboard(guild_id: int, period: str, limit: int = 10) -> list[tuple[int, int]]:
    """[(user_id, total_messages), ...] triés décroissant, sur une
    période nommée ("day"/"week"/"month"/"year" — cf. _period_bounds ;
    "day" est un alias de "today" pour matcher le vocabulaire du
    dashboard : classement journalier/hebdo/mensuel/annuel)."""
    lookup_period = "today" if period == "day" else period
    start, end = _period_bounds(lookup_period)

    stmt = (
        select(
            GuildMessageStatDaily.user_id,
            func.sum(GuildMessageStatDaily.message_count).label("total"),
        )
        .where(
            GuildMessageStatDaily.guild_id == guild_id,
            GuildMessageStatDaily.stat_date >= start,
            GuildMessageStatDaily.stat_date <= end,
        )
        .group_by(GuildMessageStatDaily.user_id)
        .order_by(func.sum(GuildMessageStatDaily.message_count).desc())
        .limit(limit)
    )
    async with get_session() as session:
        rows = (await session.execute(stmt)).all()
    return [(int(r.user_id), int(r.total)) for r in rows]