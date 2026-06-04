"""
cogs/api/api_notations.py — API Notations - site web.

Endpoints :
    GET  /health                         -> état + âge du cache
    GET  /notations                      -> config complète
    POST /notations/update_all           -> mise à jour complète de la config
    POST /notations/set_ids              -> mise à jour partielle des IDs
    POST /notations/set_time             -> mise à jour d'un créneau horaire
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

from utils.managers import notations_manager as nm
from utils.settings import settings

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# App + rate limiter
# ──────────────────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="GuideON — API Notations",
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

_VALID_TIME_KEYS = [
    "time_ask_availability",
    "time_ask_beginning",
    "time_ask_finish",
    "time_send_notations",
]


class TimeSchedule(BaseModel):
    weekday: int
    hour: int
    minute: int


class NotationConfigUpdate(BaseModel):
    id_guild_notations: int
    id_channel_staff_notations: int
    id_channel_notations: int
    id_channel_logs: int
    id_role_notation: int
    time_ask_availability: TimeSchedule
    time_ask_beginning: TimeSchedule
    time_ask_finish: TimeSchedule
    time_send_notations: TimeSchedule


class SetIdsPayload(BaseModel):
    guild_id: int | None = None
    staff_chan_id: int | None = None
    notif_chan_id: int | None = None
    logs_chan_id: int | None = None
    role_id: int | None = None


class SetTimePayload(BaseModel):
    key: str
    schedule: TimeSchedule


# ──────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────

@app.get("/health")
@limiter.limit("10/minute")
async def health(request: Request):
    age = nm.cache_age_seconds()
    return {
        "status": "ok",
        "cache_ready": nm.cache_is_ready(),
        "cache_age_seconds": None if age == float("inf") else round(age, 1),
    }


@app.get("/notations", dependencies=[Depends(require_token)])
@limiter.limit("2/minute")
async def get_notation_config(request: Request):
    return await nm.get_config()


@app.post("/notations/update_all", dependencies=[Depends(require_token)])
@limiter.limit("1/minute")
async def update_full_config(request: Request, config: NotationConfigUpdate):
    updated = await nm.update_full_config(config.dict())
    return updated


@app.post("/notations/set_ids", dependencies=[Depends(require_token)])
@limiter.limit("1/minute")
async def set_ids(request: Request, payload: SetIdsPayload):
    mapping = {
        "id_guild_notations": payload.guild_id,
        "id_channel_staff_notations": payload.staff_chan_id,
        "id_channel_notations": payload.notif_chan_id,
        "id_channel_logs": payload.logs_chan_id,
        "id_role_notation": payload.role_id,
    }
    partial = {k: v for k, v in mapping.items() if v is not None}
    if not partial:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Au moins un champ doit être fourni.",
        )
    updated = await nm.update_partial(partial)
    return updated


@app.post("/notations/set_time", dependencies=[Depends(require_token)])
@limiter.limit("1/minute")
async def set_specific_time(request: Request, payload: SetTimePayload):
    if payload.key not in _VALID_TIME_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Clé de temps **invalide**. Valeurs acceptées : {_VALID_TIME_KEYS}",
        )
    updated = await nm.update_partial({payload.key: payload.schedule.dict()})
    return updated


# ──────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────

def run_api_server() -> threading.Thread:
    """Démarre le serveur API Notations."""

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

    thread = threading.Thread(target=_serve, name="guideon-api-notations", daemon=True)
    thread.start()
    log.info("[API] API notations démarrée sur %s:%s", settings.api_host, settings.api_port)
    return thread