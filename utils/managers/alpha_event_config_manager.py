"""
utils/managers/alpha_event_config_manager.py — Gestion config events M+ Alpha.

API : 
    await load_event_config(guild_id) -> dict
    await save_event_config(guild_id, **fields) -> dict

"""

from __future__ import annotations

import asyncio, logging, time
from utils.db.models.alpha_event_config import AlphaEventConfig
from utils.db.session import get_session

log = logging.getLogger(__name__)


# ============================================================
# 📦 Gestion du cache
# ============================================================

CACHE_TTL = 60
_cache: dict[int, tuple[dict, float]] = {}
_lock = asyncio.Lock()
_DEFAULTS = {"channel_id": None, "ping_role_id": None}


# ============================================================
# 🔩 Fonctions utilitaires
# ============================================================

def _valid(gid):
    """Vérifie que le cache est valide."""
    c = _cache.get(gid); return c and (time.monotonic()-c[1]) < CACHE_TTL


async def load_event_config(guild_id: int) -> dict:
    """Charge la configuration du serveur."""
    if _valid(guild_id): return dict(_cache[guild_id][0])
    async with get_session() as s:
        row = await s.get(AlphaEventConfig, guild_id)
        cfg = row.to_dict() if row else {"guild_id": guild_id, **_DEFAULTS}
    _cache[guild_id] = (cfg, time.monotonic())
    return dict(cfg)


async def save_event_config(guild_id: int, **fields) -> dict:
    """Sauvegarde la configuration du serveur."""
    clean = {k: v for k, v in fields.items() if k in {"channel_id", "ping_role_id"}}
    if not clean: return await load_event_config(guild_id)
    async with _lock:
        async with get_session() as s:
            row = await s.get(AlphaEventConfig, guild_id)
            if row is None:
                row = AlphaEventConfig(guild_id=guild_id, **{**_DEFAULTS, **clean})
                s.add(row)
            else:
                for k, v in clean.items(): setattr(row, k, v)
            await s.flush(); result = row.to_dict()
        _cache[guild_id] = (result, time.monotonic())
    return dict(result)