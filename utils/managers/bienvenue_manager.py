"""
utils/managers/bienvenue_manager.py — Gestion DB config bienvenue.

    await load_bienvenue_config(guild_id) -> dict
    await save_bienvenue_config(guild_id, partial_dict)
    await reset_bienvenue_config(guild_id)
    await delete_bienvenue_config(guild_id) -> bool
"""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import delete, select

from utils.db.session import get_session
from utils.db.models.bienvenue import (DEFAULT_ARRIVE_MESSAGE, DEFAULT_DEPART_MESSAGE, BienvenueConfig, BienvenueFormat)


# ============================================================
# 📦 Constantes
# ============================================================

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

DEFAULT_CONFIG: dict = {
    "system_active": False,
    "arrive_active": False,
    "depart_active": False,
    "arrive_channel_id": None,
    "depart_channel_id": None,
    "arrive_message": DEFAULT_ARRIVE_MESSAGE,
    "depart_message": DEFAULT_DEPART_MESSAGE,
    "arrive_format": BienvenueFormat.EMBED.value,
    "depart_format": BienvenueFormat.EMBED.value,
    "arrive_image_url": None,
    "depart_image_url": None,
}

_cache: dict[int, tuple[dict, float]] = {}
_lock = asyncio.Lock()


# ============================================================
# 🔩 Fonctions utilitaire
# ============================================================

def _default() -> dict:
    """Renvoie la config par défaut."""
    return DEFAULT_CONFIG.copy()


async def load_bienvenue_config(guild_id: int) -> dict:
    """Charge la config d'un serveur."""

    now = time.monotonic()
    cached = _cache.get(guild_id)
    if cached is not None and (now - cached[1]) < CACHE_TTL_SECONDS:
        return cached[0].copy()

    async with get_session() as session:
        row = await session.get(BienvenueConfig, guild_id)
        cfg = row.to_dict() if row is not None else _default()

    _cache[guild_id] = (cfg, now)
    return cfg.copy()


async def save_bienvenue_config(guild_id: int, partial: dict) -> dict:
    """Met à jour la config d'un serveur."""

    allowed = set(DEFAULT_CONFIG.keys())
    clean = {k: v for k, v in partial.items() if k in allowed}

    async with _lock:
        async with get_session() as session:
            row = await session.get(BienvenueConfig, guild_id)
            if row is None:
                merged = {**_default(), **clean}
                row = BienvenueConfig(guild_id=guild_id, **merged)
                session.add(row)
            else:
                for k, v in clean.items():
                    setattr(row, k, v)
            await session.flush()
            result = row.to_dict()

        _cache[guild_id] = (result, time.monotonic())

    return result.copy()


async def reset_bienvenue_config(guild_id: int) -> dict:
    """Remet la config aux valeurs par défaut."""
    return await save_bienvenue_config(guild_id, _default())


async def delete_bienvenue_config(guild_id: int) -> bool:
    """Supprime la config d'un serveur."""

    async with _lock:
        async with get_session() as session:
            res = await session.execute(
                delete(BienvenueConfig).where(BienvenueConfig.guild_id == guild_id)
            )
            deleted = res.rowcount > 0
        _cache.pop(guild_id, None)
    return deleted


async def all_active_configs() -> list[dict]:
    """Renvoie toutes les configs du système de bienvenue activés."""

    async with get_session() as session:
        rows = (
            await session.execute(
                select(BienvenueConfig).where(BienvenueConfig.system_active.is_(True))
            )
        ).scalars().all()

    out = []
    for r in rows:
        d = r.to_dict()
        d["guild_id"] = r.guild_id
        out.append(d)
    return out