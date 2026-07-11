"""
utils/managers/alpha_onu_manager.py — Gestion du système ONU Alpha.

API :
    await load_onu_config(guild_id) -> dict
    await save_onu_config(guild_id, **fields) -> dict
    await list_all_onu_configs() -> list[dict]
    await get_onu_ping_members(guild_id) -> list[int]
    await add_onu_ping_member(guild_id, discord_id) -> bool
    await remove_onu_ping_member(guild_id, discord_id) -> bool

"""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import delete, select

from utils.db.models.alpha_onu_config import AlphaONUConfig, AlphaONUPingMember
from utils.db.session import get_session

log = logging.getLogger(__name__)


# ============================================================
# 📦 Gestion du cache
# ============================================================

CACHE_TTL = 60
_cache: dict[int, tuple[dict, float]] = {}
_lock = asyncio.Lock()


# ============================================================
# 📋 Constantes
# ============================================================

_FIELDS = {
    "channel_id", "role_id", "jour_onu",
    "pre_heure", "pre_minute", "ann_heure", "ann_minute",
    "timezone", "ping_mp", "image_name", "join_url", "enabled",
}

_DEFAULTS: dict = {
    "channel_id": None, "role_id": None, "jour_onu": None,
    "pre_heure": None, "pre_minute": None,
    "ann_heure": None, "ann_minute": None,
    "timezone": "Europe/Paris", "ping_mp": False,
    "image_name": None, "join_url": None, "enabled": True,
}


# ============================================================
# 🔩 Fonctions utilitaires (cache)
# ============================================================

def _is_valid(guild_id: int) -> bool:
    """Vérifie que le cache est valide."""
    c = _cache.get(guild_id)
    return c is not None and (time.monotonic() - c[1]) < CACHE_TTL


def _invalidate(guild_id: int) -> None:
    """Supprime le cache."""
    _cache.pop(guild_id, None)


# ============================================================
# 🧩 Fonctions principales
# ============================================================

async def load_onu_config(guild_id: int) -> dict:
    """Charge la configuration ONU."""
    if _is_valid(guild_id):
        return dict(_cache[guild_id][0])
    async with get_session() as session:
        row = await session.get(AlphaONUConfig, guild_id)
        cfg = row.to_dict() if row else {"guild_id": guild_id, **_DEFAULTS.copy()}
    _cache[guild_id] = (cfg, time.monotonic())
    return dict(cfg)


async def save_onu_config(guild_id: int, **fields: object) -> dict:
    """Sauvegarde la configuration ONU."""
    clean = {k: v for k, v in fields.items() if k in _FIELDS}
    if not clean:
        return await load_onu_config(guild_id)
    async with _lock:
        async with get_session() as session:
            row = await session.get(AlphaONUConfig, guild_id)
            if row is None:
                merged = {**_DEFAULTS.copy(), **clean}
                row = AlphaONUConfig(guild_id=guild_id, **merged)
                session.add(row)
            else:
                for k, v in clean.items():
                    setattr(row, k, v)
            await session.flush()
            result = row.to_dict()
        _cache[guild_id] = (result, time.monotonic())
    return dict(result)


async def list_all_onu_configs() -> list[dict]:
    """Renvoie la liste de toutes les configurations ONU."""
    async with get_session() as session:
        rows = (await session.execute(select(AlphaONUConfig))).scalars().all()
    return [r.to_dict() for r in rows]


# ============================================================
# 👥 Fonctions utilitaires (ping-list)
# ============================================================

async def get_onu_ping_members(guild_id: int) -> list[int]:
    """Retourne la liste des discord_id à pinger en MP."""
    async with get_session() as session:
        rows = (await session.execute(
            select(AlphaONUPingMember.discord_id).where(
                AlphaONUPingMember.guild_id == guild_id
            )
        )).scalars().all()
    return list(rows)


async def add_onu_ping_member(guild_id: int, discord_id: int) -> bool:
    """Ajoute un membre à la ping-list."""
    async with get_session() as session:
        exists = await session.scalar(
            select(AlphaONUPingMember.id).where(
                AlphaONUPingMember.guild_id == guild_id,
                AlphaONUPingMember.discord_id == discord_id,
            )
        )
        if exists is not None:
            return False
        session.add(AlphaONUPingMember(guild_id=guild_id, discord_id=discord_id))
    log.info("[ONU PING-LIST] Membre ajouté : guild=%d user=%d", guild_id, discord_id)
    return True


async def remove_onu_ping_member(guild_id: int, discord_id: int) -> bool:
    """Retire un membre de la ping-list."""
    async with get_session() as session:
        result = await session.execute(
            delete(AlphaONUPingMember).where(
                AlphaONUPingMember.guild_id == guild_id,
                AlphaONUPingMember.discord_id == discord_id,
            )
        )
        deleted = result.rowcount > 0
        
    if deleted:
        log.info("[ONU PING-LIST] Membre retiré : guild=%d user=%d", guild_id, discord_id)
    return deleted