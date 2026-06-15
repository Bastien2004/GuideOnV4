"""
utils/managers/autorole_manager.py

    await load_autorole_config(guild_id) -> dict
    await save_autorole_config(guild_id, config_dict)
    await reset_autorole_config(guild_id) -> dict
    await delete_autorole_config(guild_id) -> bool
    await all_active_configs() -> list[dict]
"""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import delete, select

from utils.db.models.autorole import AutoRoleConfig
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60
DEFAULT_CONFIG: dict = {
    "auto_role_active": False,
    "role_id_1": None,
    "role_id_2": None,
    "role_id_3": None,
}


_KEY_TO_COLUMN = {
    "auto_role_active": "active",
    "role_id_1": "role_id_1",
    "role_id_2": "role_id_2",
    "role_id_3": "role_id_3",
}


_cache: dict[int, tuple[dict, float]] = {}
_lock = asyncio.Lock()


def _default() -> dict:
    return DEFAULT_CONFIG.copy()


async def load_autorole_config(guild_id: int) -> dict:
    """Charge la config auto-rôle d'un serveur."""

    now = time.monotonic()
    cached = _cache.get(guild_id)
    if cached is not None and (now - cached[1]) < CACHE_TTL_SECONDS:
        return cached[0].copy()

    async with get_session() as session:
        row = await session.get(AutoRoleConfig, guild_id)
        cfg = row.to_dict() if row is not None else _default()

    _cache[guild_id] = (cfg, now)
    return cfg.copy()


async def save_autorole_config(guild_id: int, config: dict) -> dict:
    """Sauvegarde la configuration auto-rôle d'un serveur. """

    clean = {
        _KEY_TO_COLUMN[k]: v
        for k, v in config.items()
        if k in _KEY_TO_COLUMN
    }

    async with _lock:
        async with get_session() as session:
            row = await session.get(AutoRoleConfig, guild_id)
            if row is None:
                row = AutoRoleConfig(guild_id=guild_id)
                row.active = clean.get("active", False)
                row.role_id_1 = clean.get("role_id_1")
                row.role_id_2 = clean.get("role_id_2")
                row.role_id_3 = clean.get("role_id_3")
                session.add(row)
            else:
                for col, val in clean.items():
                    setattr(row, col, val)
            await session.flush()
            result = row.to_dict()

        _cache[guild_id] = (result, time.monotonic())

    return result.copy()


async def reset_autorole_config(guild_id: int) -> dict:
    """Remet la config aux valeurs par défaut."""

    return await save_autorole_config(guild_id, _default())


async def delete_autorole_config(guild_id: int) -> bool:
    """Supprime la config d'un serveur."""

    async with _lock:
        async with get_session() as session:
            res = await session.execute(
                delete(AutoRoleConfig).where(AutoRoleConfig.guild_id == guild_id)
            )
            deleted = res.rowcount > 0
        _cache.pop(guild_id, None)
    return deleted


async def all_active_configs() -> list[dict]:
    """Retourne la liste des configs auto-rôle actives sur tout les serveurs."""
    
    async with get_session() as session:
        rows = (
            await session.execute(
                select(AutoRoleConfig).where(AutoRoleConfig.active.is_(True))
            )
        ).scalars().all()

    out = []
    for r in rows:
        d = r.to_dict()
        d["guild_id"] = r.guild_id
        out.append(d)
    return out