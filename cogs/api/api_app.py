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

from cogs.api.base import app, require_token

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

class ONUConfigUpdate(BaseModel):
    """Modèle pour mise à jour config ONU (accepte anciens ET nouveaux champs)"""
    guild_id: int
    jour_onu: int | None = None
    pre_heure: int | None = None
    pre_minute: int | None = None
    ann_heure: int | None = None
    ann_minute: int | None = None
    timezone: str = "Europe/Paris"
    ping_mp: bool = False
    ping_list: dict | list | None = None
    role_id: int | None = None
    channel_id: int | None = None
    image_name: str | None = None
    join_url: str | None = None
    enabled: bool = True

    @field_validator("ping_list", mode="before")
    @classmethod
    def convert_ping_list(cls, v):
        """Convertir list en dict vide si nécessaire"""
        if isinstance(v, list):
            return {}
        return v or {}


class ONUPingPayload(BaseModel):
    discord_id: int
    name: str | None = None

    @field_validator("discord_id", mode="before")
    @classmethod
    def convert_discord_id(cls, v):
        """Convertir string en int si nécessaire"""
        if isinstance(v, str):
            return int(v)
        return v


# ──────────────────────────────────────────────────────────────────────────
# Endpoints — Health
# ──────────────────────────────────────────────────────────────────────────

@app.get("/health")
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
async def get_all(request: Request):
    return await bm.list_entries()


@app.get("/boutique/{role}", dependencies=[Depends(require_token)])
async def get_role(request: Request, role: str):
    try:
        shop_role = bm.role_from_str(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Rôle inconnu : {role!r}")
    data = await bm.list_entries(shop_role)
    return data[shop_role.value]


@app.post("/boutique/add", dependencies=[Depends(require_token)])
async def add(request: Request, payload: ShopPayload):
    role: ShopRole = bm.role_from_str(payload.role)
    created = await bm.add_entry(role, payload.discord_id)
    return {
        "created": created,
        "role": role.value,
        "discord_id": payload.discord_id,
    }


@app.post("/boutique/remove", dependencies=[Depends(require_token)])
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
async def get_onu_config(request: Request, guild_id: int):
    config = await om.get_config(guild_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config ONU non trouvée")
    return config


@app.post("/onu/update_all", dependencies=[Depends(require_token)])
async def update_onu_config(request: Request, config: ONUConfigUpdate):
    return await om.update_full_config(config.model_dump(exclude_none=True))


@app.post("/onu/{guild_id}/ping/add", dependencies=[Depends(require_token)])
async def add_onu_ping(request: Request, guild_id: int, ping: ONUPingPayload):
    return await om.add_ping(guild_id, ping.discord_id, ping.name or "Unknown")


@app.post("/onu/{guild_id}/ping/remove", dependencies=[Depends(require_token)])
async def remove_onu_ping(request: Request, guild_id: int, discord_id: int):
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