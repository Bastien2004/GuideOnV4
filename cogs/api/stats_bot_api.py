"""
cogs/api/api_stats.py — API Stats.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Literal

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel

from utils.managers import guild_stats_manager as gsm
from cogs.api.base import app, require_token

from utils.managers import ticket_manager as tm

log = logging.getLogger(__name__)

PeriodTotalsName = Literal["today", "yesterday", "week", "month", "year"]
LeaderboardPeriodName = Literal["day", "week", "month", "year"]


# ══════════════════════════════════════════════════════════════════════════
# 📋 MODÈLES PYDANTIC
# ══════════════════════════════════════════════════════════════════════════

class StatsResponse(BaseModel):
    total_guilds: int
    total_members: int
    ping: int


class ActivityTotalsResponse(BaseModel):
    arrivals: int
    departures: int
    voice_minutes: int
    messages: int


class PeriodTotalsResponse(ActivityTotalsResponse):
    period: str
    start_date: date
    end_date: date


class DailyStatPoint(BaseModel):
    date: date
    arrivals: int
    departures: int
    voice_minutes: int
    messages: int


class MonthlyStatPoint(BaseModel):
    year: int
    month: int
    arrivals: int
    departures: int
    voice_minutes: int
    messages: int


class ActiveMembersResponse(BaseModel):
    guild_id: int
    days: int
    active_members: int


class LeaderboardEntry(BaseModel):
    user_id: int
    message_count: int


class LeaderboardResponse(BaseModel):
    guild_id: int
    period: str
    entries: list[LeaderboardEntry]


class TicketStatsResponse(BaseModel):
    guild_id: int
    open: int
    closed: int
    deleted: int


# ══════════════════════════════════════════════════════════════════════════
# 🔄 ENDPOINTS — Bot (global)
# ══════════════════════════════════════════════════════════════════════════

@app.get("/stats", dependencies=[Depends(require_token)], response_model=StatsResponse)
async def get_stats(request: Request):
    bot = request.app.state.bot
    guilds = bot.guilds

    total_guilds = len(guilds)
    total_members = sum(g.member_count or 0 for g in guilds)

    latency = bot.latency
    ping = round(latency * 1000) if latency == latency else 0

    return {"total_guilds": total_guilds, "total_members": total_members, "ping": ping}


# ══════════════════════════════════════════════════════════════════════════
# 🔄 ENDPOINTS — Stats serveur (guild_stats_manager)
# ══════════════════════════════════════════════════════════════════════════

@app.get(
    "/stats/{guild_id}/activity/{period}",
    dependencies=[Depends(require_token)],
    response_model=PeriodTotalsResponse,
)
async def get_guild_period_totals(request: Request, guild_id: int, period: PeriodTotalsName):
    """Totaux arrivées/départs/vocal/messages pour une période nommée."""
    try:
        return await gsm.get_period_totals(guild_id, period)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/stats/{guild_id}/daily",
    dependencies=[Depends(require_token)],
    response_model=list[DailyStatPoint],
)
async def get_guild_daily_series(request: Request, guild_id: int, days: int = 30):
    """Série quotidienne (30J par défaut) pour les graphiques."""
    if days <= 0:
        raise HTTPException(status_code=400, detail="`days` doit être un entier positif.")
    return await gsm.get_daily_series(guild_id, days=days)


@app.get(
    "/stats/{guild_id}/monthly",
    dependencies=[Depends(require_token)],
    response_model=list[MonthlyStatPoint],
)
async def get_guild_monthly_series(request: Request, guild_id: int, months: int = 12):
    """Série mensuelle (12 mois par défaut) pour les graphiques."""
    if months <= 0:
        raise HTTPException(status_code=400, detail="`months` doit être un entier positif.")
    return await gsm.get_monthly_series(guild_id, months=months)


@app.get(
    "/stats/{guild_id}/active-members",
    dependencies=[Depends(require_token)],
    response_model=ActiveMembersResponse,
)
async def get_guild_active_members(request: Request, guild_id: int, days: int = 7):
    """Nombre de membres distincts actifs (>= 1 message) sur les `days` derniers jours."""
    if days <= 0:
        raise HTTPException(status_code=400, detail="`days` doit être un entier positif.")
    count = await gsm.get_active_members_count(guild_id, days=days)
    return {"guild_id": guild_id, "days": days, "active_members": count}


@app.get(
    "/stats/{guild_id}/leaderboard/{period}",
    dependencies=[Depends(require_token)],
    response_model=LeaderboardResponse,
)
async def get_guild_message_leaderboard(
    request: Request, guild_id: int, period: LeaderboardPeriodName, limit: int = 10,
):
    """Classement des membres par nombre de messages sur une période nommée."""
    if not (1 <= limit <= 100):
        raise HTTPException(status_code=400, detail="`limit` doit être compris entre 1 et 100.")
    try:
        rows = await gsm.get_message_leaderboard(guild_id, period, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    entries = [{"user_id": user_id, "message_count": count} for user_id, count in rows]
    return {"guild_id": guild_id, "period": period, "entries": entries}

@app.get(
    "/stats/{guild_id}/tickets",
    dependencies=[Depends(require_token)],
    response_model=TicketStatsResponse,
)
async def get_guild_ticket_stats(request: Request, guild_id: int):
    """Statistiques actuelles des tickets d'une guilde."""

    open_count = await tm.count_open_tickets(guild_id)
    closed_count = await tm.count_closed_tickets(guild_id)
    deleted_count = await tm.count_deleted_tickets(guild_id)

    return {
        "guild_id": guild_id,
        "open": open_count,
        "closed": closed_count,
        "deleted": deleted_count,
    }