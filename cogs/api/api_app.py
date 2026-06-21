"""
cogs/api/api_app.py — API Boutique + Notations + ONU - site web.

Endpoints :
    GET  /health                      -> état + âge du cache
    GET  /boutique                    -> {"VIP": [...], "Gold+": [...]}
    GET  /boutique/{role}             -> [discord_id, ...]
    POST /boutique/add                -> {role, discord_id}
    POST /boutique/remove             -> {role, discord_id}
    GET  /notations                   -> config complète
    POST /notations/update_all        -> mise à jour complète
    POST /notations/set_ids           -> mise à jour partielle des IDs
    POST /notations/set_time          -> mise à jour d'un créneau horaire
    GET  /onu/{guild_id}              -> config ONU
    POST /onu/update_all              -> mise à jour complète ONU
    POST /onu/{guild_id}/ping/add     -> ajouter un ping
    POST /onu/{guild_id}/ping/remove  -> retirer un ping
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uvicorn

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from utils.managers import boutique_manager as bm
from utils.managers import notations_manager as nm
from utils.managers import onu_manager as om
from utils.managers.boutique_manager import ShopRole
from utils.settings import settings

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# App + rate limiter
# ──────────────────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="GuideON — API",
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


def require_token(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> None:
    """Vérification du Token."""
    if creds.scheme.lower() != "bearer" or creds.credentials != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token **invalide**.",
        )


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
# Schémas — Notations
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
# Endpoints — Notations
# ──────────────────────────────────────────────────────────────────────────

@app.get("/notations", dependencies=[Depends(require_token)])
@limiter.limit("10/minute")
async def get_notation_config(request: Request):
    return await nm.get_config()


@app.post("/notations/update_all", dependencies=[Depends(require_token)])
@limiter.limit("10/minute")
async def update_full_config(request: Request, config: NotationConfigUpdate):
    return await nm.update_full_config(config.dict())


@app.post("/notations/set_ids", dependencies=[Depends(require_token)])
@limiter.limit("10/minute")
async def set_ids(request: Request, payload: SetIdsPayload):
    mapping = {
        "id_guild_notations":         payload.guild_id,
        "id_channel_staff_notations": payload.staff_chan_id,
        "id_channel_notations":       payload.notif_chan_id,
        "id_channel_logs":            payload.logs_chan_id,
        "id_role_notation":           payload.role_id,
    }
    partial = {k: v for k, v in mapping.items() if v is not None}
    if not partial:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Au moins un champ doit être fourni.",
        )
    return await nm.update_partial(partial)


@app.post("/notations/set_time", dependencies=[Depends(require_token)])
@limiter.limit("10/minute")
async def set_specific_time(request: Request, payload: SetTimePayload):
    if payload.key not in _VALID_TIME_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Clé invalide. Valeurs acceptées : {_VALID_TIME_KEYS}",
        )
    return await nm.update_partial({payload.key: payload.schedule.dict()})


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
    """Démarre le serveur API."""

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
