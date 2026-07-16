"""
cogs/api/base.py — App FastAPI unifiée partagée par tous les modules.
"""

from __future__ import annotations

import logging
import discord

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import Depends
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from utils.settings import settings
from fastapi.responses import JSONResponse


log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────
# App + Rate Limiter (singleton partagé)
# ──────────────────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="GuideON",
    version="4.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Trop de **requêtes**, réessayez plus tard."},
    )


# ──────────────────────────────────────────────────────────────────────────
# Auth Bearer (partagé)
# ──────────────────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=True)


def require_token(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> None:
    """Vérification du Token."""
    if creds.scheme.lower() != "bearer" or creds.credentials != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token **invalide**.",
        )