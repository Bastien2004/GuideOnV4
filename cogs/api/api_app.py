"""
cogs/api/api_app.py — API Boutique + ONU
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uvicorn

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from utils.managers import boutique_manager as bm
from utils.managers import onu_manager as om
from utils.managers.boutique_manager import ShopRole
from utils.settings import settings

# ✅ Importer l'app partagée
from utils.db.base import app, limiter, require_token

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Schémas — Boutique
# ──────────────────────────────────────────────────────────────────────────

class ShopPayload(BaseModel):
    role: str
    discord_id: str

    @field_validator("role")
    @classmethod
    def _valid_role(cls, v: str) -> str:
        bm.role_from_str(v)
        return v

    @field_validator("discord_id")
    @classmethod
    def _valid_id(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit():
            raise ValueError("discord_id doit être un **identifiant numérique**.")
        return v


# ──────────────────────────────────────────────────────────────────────────
# Schémas — ONU
# ──────────────────────────────────────────────────────────────────────────

class TimeModel(BaseModel):
    heure: int
    minute: int


class ONUConfigUpdate(BaseModel):
    guild_id: int
    jour_onu: int
    pre_annonce: TimeModel
    annonce: TimeModel
    timezone: str
    ping_mp: bool
    ping_list: dict[str, str]
    role_id: int
    channel_id: int
    image_name: str


class ONUPingPayload(BaseModel):
    discord_id: str
    name: str


# ──────────────────────────────────────────────────────────────────────────
# Endpoints — Health
# ──────────────────────────────────────────────────────────────────────────

@app.get("/health")
@limiter.limit("10/minute")
async def health(request: Request):
    age = bm.cache_age_seconds()
    return {
        "status": "ok",
        "cache_ready": bm.cache_is_ready(),
        "cache_age_seconds": None if age == float("inf") else round(age, 1),
    }


# ──────────────────────────────────────────────────────────────────────────
# Endpoints — Boutique
# ──────────────────────────────────────────────────────────────────────────

@app.get("/boutique", dependencies=[Depends(require_token)])
@limiter.limit("10/minute")
async def get_all(request: Request):
    return await bm.list_entries()


@app.get("/boutique/{role}", dependencies=[Depends(require_token)])
@limiter.limit("10/minute")
async def get_role(request: Request, role: str):
    try:
        shop_role = bm.role_from_str(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Rôle inconnu : {role!r}")
    data = await bm.list_entries(shop_role)
    return data[shop_role.value]


@app.post("/boutique/add", dependencies=[Depends(require_token)])
@limiter.limit("10/minute")
async def add(request: Request, payload: ShopPayload):
    role: ShopRole = bm.role_from_str(payload.role)
    created = await bm.add_entry(role, payload.discord_id)
    return {
        "created": created,
        "role": role.value,
        "discord_id": payload.discord_id,
    }


@app.post("/boutique/remove", dependencies=[Depends(require_token)])
@limiter.limit("10/minute")
async def remove(request: Request, payload: ShopPayload):
    role: ShopRole = bm.role_from_str(payload.role)
    deleted = await bm.remove_entry(role, payload.discord_id)
    return {
        "deleted": deleted,
        "role": role.value,
        "discord_id": payload.discord_id,
    }


# ──────────────────────────────────────────────────────────────────────────
# Endpoints — ONU
# ──────────────────────────────────────────────────────────────────────────

@app.get("/onu/{guild_id}", dependencies=[Depends(require_token)])
@limiter.limit("10/minute")
async def get_onu_config(request: Request, guild_id: int):
    config = await om.get_config(guild_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config ONU non trouvée")
    return config


@app.post("/onu/update_all", dependencies=[Depends(require_token)])
@limiter.limit("10/minute")
async def update_onu_config(request: Request, config: ONUConfigUpdate):
    return await om.update_full_config(config.dict())


@app.post("/onu/{guild_id}/ping/add", dependencies=[Depends(require_token)])
@limiter.limit("10/minute")
async def add_onu_ping(request: Request, guild_id: int, ping: ONUPingPayload):
    return await om.add_ping(guild_id, ping.discord_id, ping.name)


@app.post("/onu/{guild_id}/ping/remove", dependencies=[Depends(require_token)])
@limiter.limit("10/minute")
async def remove_onu_ping(request: Request, guild_id: int, discord_id: str):
    return await om.remove_ping(guild_id, discord_id)


# ──────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────

def run_api_server() -> threading.Thread:
    """Démarre le serveur API unifiée."""

    def _serve() -> None:
        config = uvicorn.Config(
            app,
            host=settings.api_host,
            port=settings.api_port,
            log_level=settings.log_level.lower(),
            loop="asyncio",
        )
        server = uvicorn.Server(config)
        asyncio.run(server.serve())

    thread = threading.Thread(target=_serve, name="guideon-api", daemon=True)
    thread.start()
    log.info("[API] API démarrée sur %s:%s", settings.api_host, settings.api_port)
    return thread