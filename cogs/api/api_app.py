"""
cogs/api/api_app.py — API Boutique - site web.

Endpoints :
    GET  /health                      -> état + âge du cache
    GET  /boutique                    -> {"VIP": [...], "Gold+": [...]}
    GET  /boutique/{role}             -> [discord_id, ...]
    POST /boutique/add                -> {role, discord_id}
    POST /boutique/remove             -> {role, discord_id}
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
from utils.managers.boutique_manager import ShopRole
from utils.settings import settings

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# App + rate limiter
# ──────────────────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="GuideON — API Boutique",
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
# Endpoints
# ──────────────────────────────────────────────────────────────────────────

@app.get("/health")
@limiter.limit("60/minute")

async def health(request: Request):
    age = bm.cache_age_seconds()
    return {
        "status": "ok",
        "cache_ready": bm.cache_is_ready(),
        "cache_age_seconds": None if age == float("inf") else round(age, 1),
    }


@app.get("/boutique", dependencies=[Depends(require_token)])
@limiter.limit("30/minute")

async def get_all(request: Request):
    return await bm.list_entries()


@app.get("/boutique/{role}", dependencies=[Depends(require_token)])
@limiter.limit("30/minute")

async def get_role(request: Request, role: str):
    try:
        shop_role = bm.role_from_str(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Rôle inconnu : {role!r}")
    data = await bm.list_entries(shop_role)
    return data[shop_role.value]


@app.post("/boutique/add", dependencies=[Depends(require_token)])
@limiter.limit("20/minute")

async def add(request: Request, payload: ShopPayload):
    role: ShopRole = bm.role_from_str(payload.role)
    created = await bm.add_entry(role, payload.discord_id)
    return {
        "created": created,
        "role": role.value,
        "discord_id": payload.discord_id,
    }


@app.post("/boutique/remove", dependencies=[Depends(require_token)])
@limiter.limit("20/minute")

async def remove(request: Request, payload: ShopPayload):
    role: ShopRole = bm.role_from_str(payload.role)
    deleted = await bm.remove_entry(role, payload.discord_id)
    return {
        "deleted": deleted,
        "role": role.value,
        "discord_id": payload.discord_id,
    }


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
    log.info("[API] API boutique démarrée sur %s:%s", settings.api_host, settings.api_port)
    return thread