"""
cogs/api/api_onu.py — API ONU - site web.

Endpoints :
    GET  /health                  -> état + âge du cache
    GET  /onu                     -> config complète + ping_list
    POST /onu/update              -> mise à jour complète de la config
    POST /onu/set                 -> mise à jour d'un seul champ
    POST /onu/pre_annonce         -> mise à jour du créneau pré-annonce
    POST /onu/annonce             -> mise à jour du créneau annonce
    POST /onu/ping/add            -> {discord_id, name}
    POST /onu/ping/remove         -> {discord_id}
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uvicorn

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from utils.managers import onu_manager as om
from utils.db.models.onu import ONU_SETTABLE_KEYS
from utils.settings import settings

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# App + rate limiter
# ──────────────────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="GuideON — API ONU",
    version="4.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Trop de **requêtes**, réessayez plus tard.",
    )


# ──────────────────────────────────────────────────────────────────────────
# Auth Bearer
# ──────────────────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=True)


def require_token(creds: HTTPAuthorizationCredentials = Depends(_bearer),) -> None:
    """Vérification du Token."""
    if creds.scheme.lower() != "bearer" or creds.credentials != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token **invalide**.",
        )


# ──────────────────────────────────────────────────────────────────────────
# Schémas
# ──────────────────────────────────────────────────────────────────────────

class TimeModel(BaseModel):
    heure: int
    minute: int


class ConfigModel(BaseModel):
    guild_id: int
    jour_onu: int
    pre_annonce: TimeModel
    annonce: TimeModel
    timezone: str
    ping_mp: bool
    role_id: int
    channel_id: int
    image_name: str


class SetValuePayload(BaseModel):
    key: str
    value: str | int | bool | dict


class PingAddPayload(BaseModel):
    discord_id: str
    name: str


class PingRemovePayload(BaseModel):
    discord_id: str


# ──────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────

@app.get("/health")
@limiter.limit("10/minute")
async def health(request: Request):
    age = om.cache_age_seconds()
    return {
        "status": "ok",
        "cache_ready": om.cache_is_ready(),
        "cache_age_seconds": None if age == float("inf") else round(age, 1),
    }


@app.get("/onu", dependencies=[Depends(require_token)])
@limiter.limit("2/minute")
async def get_config(request: Request):
    return await om.get_config()


@app.post("/onu/update", dependencies=[Depends(require_token)])
@limiter.limit("1/minute")
async def update_config(request: Request, config: ConfigModel):
    updated = await om.update_full_config(config.dict())
    return updated


@app.post("/onu/set", dependencies=[Depends(require_token)])
@limiter.limit("1/minute")
async def set_value(request: Request, payload: SetValuePayload):
    if payload.key not in ONU_SETTABLE_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Clé **invalide**. Valeurs acceptées : {sorted(ONU_SETTABLE_KEYS)}",
        )
    try:
        updated = await om.update_partial({payload.key: payload.value})
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return updated


@app.post("/onu/pre_annonce", dependencies=[Depends(require_token)])
@limiter.limit("1/minute")
async def set_pre_annonce(request: Request, time: TimeModel):
    updated = await om.update_partial({"pre_annonce": time.dict()})
    return updated


@app.post("/onu/annonce", dependencies=[Depends(require_token)])
@limiter.limit("1/minute")
async def set_annonce(request: Request, time: TimeModel):
    updated = await om.update_partial({"annonce": time.dict()})
    return updated


@app.post("/onu/ping/add", dependencies=[Depends(require_token)])
@limiter.limit("1/minute")
async def add_ping(request: Request, payload: PingAddPayload):
    try:
        created = await om.add_ping(payload.discord_id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return {
        "created": created,
        "discord_id": payload.discord_id,
        "name": payload.name,
    }


@app.post("/onu/ping/remove", dependencies=[Depends(require_token)])
@limiter.limit("1/minute")
async def remove_ping(request: Request, payload: PingRemovePayload):
    deleted = await om.remove_ping(payload.discord_id)
    return {
        "deleted": deleted,
        "discord_id": payload.discord_id,
    }


# ──────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────

def run_api_server() -> threading.Thread:
    """Démarre le serveur API ONU."""

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

    thread = threading.Thread(target=_serve, name="guideon-api-onu", daemon=True)
    thread.start()
    log.info("[API] API ONU démarrée sur %s:%s", settings.api_host, settings.api_port)
    return thread