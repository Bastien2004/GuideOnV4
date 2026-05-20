"""
cogs/api/api_app.py — API FastAPI pour piloter la boutique depuis le site web.

Remplace l'ancien `boutique_id_api.py` V3 (qui écrivait dans un JSON).
Ici on écrit en DB via le boutique_manager, et le cache du bot est invalidé
automatiquement après chaque écriture (add_entry / remove_entry).

Sécurité :
- Auth : Bearer token (settings.api_token). PLUS de token en dur (SEC-001/002).
- Rate limiting : slowapi (déjà dans les deps).

Lancement : appelé par run_api_server(bot) dans un thread daemon depuis bot.py.

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
    docs_url=None,       # pas de Swagger public sur une API à token
    redoc_url=None,
    openapi_url=None,
)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Trop de requêtes, réessayez plus tard.",
    )


# ──────────────────────────────────────────────────────────────────────────
# Auth Bearer
# ──────────────────────────────────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=True)


def require_token(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> None:
    """Vérifie le Bearer token contre settings.api_token."""
    if creds.scheme.lower() != "bearer" or creds.credentials != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide.",
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
        # Lève si inconnu → FastAPI renvoie 422
        bm.role_from_str(v)
        return v

    @field_validator("discord_id")
    @classmethod
    def _valid_id(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit():
            raise ValueError("discord_id doit être un identifiant numérique.")
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
        # None tant que le cache n'est pas chargé (inf n'est pas JSON-compliant)
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
# Runner — thread daemon avec sa propre loop uvicorn
# ──────────────────────────────────────────────────────────────────────────
def run_api_server() -> threading.Thread:
    """
    Démarre uvicorn dans un thread daemon.

    Le thread a sa PROPRE event loop (uvicorn la crée), distincte de celle du
    bot. Les écritures DB passent par get_session() qui crée ses propres
    connexions asyncpg → pas de partage de session entre les deux loops, donc
    pas de souci de thread-safety SQLAlchemy.

    NB : le cache mémoire (_cache du boutique_manager) est partagé entre les
    deux loops car c'est une structure Python en mémoire process. Les écritures
    API appellent refresh_cache() qui réassigne _cache de façon atomique au
    niveau Python (rebinding d'un dict) → les lectures sync côté bot voient
    soit l'ancien, soit le nouveau, jamais un état partiel.
    """
    import uvicorn

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
    log.info("API boutique démarrée sur %s:%s", settings.api_host, settings.api_port)
    return thread