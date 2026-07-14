"""
cogs/api/api_stats.py — API Stats pour V4
"""
from __future__ import annotations

import logging

from fastapi import Depends, Request
from pydantic import BaseModel

from cogs.api.base import app, require_token

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# 📋 MODÈLES PYDANTIC
# ══════════════════════════════════════════════════════════════════════════

class StatsResponse(BaseModel):
    total_guilds: int
    total_members: int
    ping: int


# ══════════════════════════════════════════════════════════════════════════
# 🔄 ENDPOINTS
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