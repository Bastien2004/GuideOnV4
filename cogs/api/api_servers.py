"""
cogs/api/api_servers.py — API Serveurs (ng_servers).

Expose la liste des serveurs NG connus (table ng_servers) pour permettre
au site Laravel de synchroniser sa propre table `guilds` (discord_id, name)
sans avoir à dupliquer manuellement l'information.
"""
from __future__ import annotations

import logging
from sqlalchemy import select

from fastapi import Depends, Request
from pydantic import BaseModel

from utils.db.session import get_session
from utils.db.models.ng_server import NGServer  # ajuster si le nom diffère

from cogs.api.base import app, require_token

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# 📋 MODÈLES PYDANTIC
# ══════════════════════════════════════════════════════════════════════════

class ServerOut(BaseModel):
    name: str
    display_name: str
    edition: str
    discord_guild_id: int
    active: bool


# ══════════════════════════════════════════════════════════════════════════
# 🔄 ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════

@app.get("/servers", dependencies=[Depends(require_token)])
async def get_servers(request: Request, active_only: bool = True):
    """
    Retourne la liste des serveurs NG (pour sync Laravel -> table guilds).

    Query param: ?active_only=false pour inclure aussi les serveurs inactifs.
    """
    async with get_session() as session:
        query = select(NGServer)
        if active_only:
            query = query.where(NGServer.active.is_(True))

        result = await session.execute(query)
        servers = result.scalars().all()

        payload = [
            ServerOut(
                name=s.name,
                display_name=s.display_name,
                edition=s.edition,
                discord_guild_id=int(s.discord_guild_id),
                active=s.active,
            ).model_dump()
            for s in servers
        ]

    return {"servers": payload}