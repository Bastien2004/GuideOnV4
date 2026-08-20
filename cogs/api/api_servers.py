"""
cogs/api/api_servers.py — API Serveurs (ng_servers).

Expose la liste des serveurs NG connus, et permet à un admin (via le
tableau de gestion Laravel) d'en ajouter ou d'en modifier.
"""
from __future__ import annotations

import logging
from sqlalchemy import select

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel

from utils.db.session import get_session
from utils.db.models.ng_server import NGServer
from utils.managers.ng_server_manager import (
    dev_create_server,
    dev_update_server,
    dev_delete_server_by_guild,
    NGServerNameConflictError,
    NGServerGuildConflictError,
    NGServerNotFoundError,
)

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


class ServerCreate(BaseModel):
    name: str
    display_name: str
    edition: str
    discord_guild_id: int
    active: bool = True


class ServerUpdate(BaseModel):
    discord_guild_id: int
    display_name: str | None = None
    edition: str | None = None
    active: bool | None = None


# ══════════════════════════════════════════════════════════════════════════
# 🔄 ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════

@app.get("/servers", dependencies=[Depends(require_token)])
async def get_servers(request: Request, active_only: bool = True):
    """
    Retourne la liste des serveurs NG (pour sync/admin Laravel).

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


@app.post("/servers/add", dependencies=[Depends(require_token)])
async def add_server(request: Request, payload: ServerCreate):
    """Crée un nouveau serveur NG (utilisé par le tableau admin Laravel)."""
    try:
        server = await dev_create_server(
            name=payload.name,
            display_name=payload.display_name,
            edition=payload.edition,
            discord_guild_id=payload.discord_guild_id,
            active=payload.active,
        )
    except NGServerNameConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except NGServerGuildConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "message": f"Serveur {server.display_name!r} créé.",
        "server": ServerOut(
            name=server.name,
            display_name=server.display_name,
            edition=server.edition,
            discord_guild_id=int(server.discord_guild_id),
            active=server.active,
        ).model_dump(),
    }


@app.post("/servers/update", dependencies=[Depends(require_token)])
async def update_server(request: Request, payload: ServerUpdate):
    """Met à jour display_name / edition / active d'un serveur NG existant."""
    try:
        server = await dev_update_server(
            discord_guild_id=payload.discord_guild_id,
            display_name=payload.display_name,
            edition=payload.edition,
            active=payload.active,
        )
    except NGServerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "message": f"Serveur {server.display_name!r} mis à jour.",
        "server": ServerOut(
            name=server.name,
            display_name=server.display_name,
            edition=server.edition,
            discord_guild_id=int(server.discord_guild_id),
            active=server.active,
        ).model_dump(),
    }


@app.delete("/servers/{discord_guild_id}", dependencies=[Depends(require_token)])
async def delete_server(request: Request, discord_guild_id: int):
    """Supprime un serveur NG (utilisé par le tableau admin Laravel)."""
    server = await dev_delete_server_by_guild(discord_guild_id)
    if server is None:
        raise HTTPException(
            status_code=404,
            detail=f"Aucun serveur NG connu pour guild_id={discord_guild_id}",
        )

    return {
        "message": f"Serveur {server.display_name!r} supprimé.",
        "server": ServerOut(
            name=server.name,
            display_name=server.display_name,
            edition=server.edition,
            discord_guild_id=int(server.discord_guild_id),
            active=server.active,
        ).model_dump(),
    }