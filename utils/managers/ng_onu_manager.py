"""
utils/managers/ng_onu_manager.py — Gestion du système ONU multi-serveurs.

Refonte multi-serveurs phase 8 : remplace utils/managers/alpha_onu_manager.py.
Même API, clé `server` (nom NGServer) au lieu de `guild_id`.

API :
    await load_onu_config(server) -> dict
    await save_onu_config(server, **fields) -> dict
    await list_all_onu_configs() -> list[dict]
    await get_onu_ping_members(server) -> list[int]
    await add_onu_ping_member(server, discord_id) -> bool
    await remove_onu_ping_member(server, discord_id) -> bool
"""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import delete, select

from utils.db.models.ng_onu_config import NGONUConfig, NGONUPingMember
from utils.db.session import get_session

log = logging.getLogger(__name__)


# ============================================================
# 📦 Gestion du cache
# ============================================================

CACHE_TTL = 60
_cache: dict[str, tuple[dict, float]] = {}
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

def _is_valid(server: str) -> bool:
    """Vérifie que le cache est valide."""
    c = _cache.get(server)
    return c is not None and (time.monotonic() - c[1]) < CACHE_TTL


def _invalidate(server: str) -> None:
    """Supprime le cache."""
    _cache.pop(server, None)


# ============================================================
# 🧩 Fonctions principales
# ============================================================

async def load_onu_config(server: str) -> dict:
    """Charge la configuration ONU d'un serveur."""
    if _is_valid(server):
        return dict(_cache[server][0])
    async with get_session() as session:
        row = await session.get(NGONUConfig, server)
        cfg = row.to_dict() if row else {"server": server, **_DEFAULTS.copy()}
    _cache[server] = (cfg, time.monotonic())
    return dict(cfg)


async def save_onu_config(server: str, **fields: object) -> dict:
    """Sauvegarde la configuration ONU d'un serveur."""
    clean = {k: v for k, v in fields.items() if k in _FIELDS}
    if not clean:
        return await load_onu_config(server)
    async with _lock:
        async with get_session() as session:
            row = await session.get(NGONUConfig, server)
            if row is None:
                merged = {**_DEFAULTS.copy(), **clean}
                row = NGONUConfig(server=server, **merged)
                session.add(row)
            else:
                for k, v in clean.items():
                    setattr(row, k, v)
            await session.flush()
            result = row.to_dict()
        _cache[server] = (result, time.monotonic())
    return dict(result)


async def list_all_onu_configs() -> list[dict]:
    """Renvoie la liste de toutes les configurations ONU (tous serveurs)."""
    async with get_session() as session:
        rows = (await session.execute(select(NGONUConfig))).scalars().all()
    return [r.to_dict() for r in rows]


# ============================================================
# 👥 Fonctions utilitaires (ping-list)
# ============================================================

async def get_onu_ping_members(server: str) -> list[int]:
    """Retourne la liste des discord_id à pinger en MP pour un serveur."""
    async with get_session() as session:
        rows = (await session.execute(
            select(NGONUPingMember.discord_id).where(
                NGONUPingMember.server == server
            )
        )).scalars().all()
    return list(rows)


async def add_onu_ping_member(server: str, discord_id: int) -> bool:
    """Ajoute un membre à la ping-list d'un serveur."""
    async with get_session() as session:
        exists = await session.scalar(
            select(NGONUPingMember.id).where(
                NGONUPingMember.server == server,
                NGONUPingMember.discord_id == discord_id,
            )
        )
        if exists is not None:
            return False
        session.add(NGONUPingMember(server=server, discord_id=discord_id))
    log.info("[ONU PING-LIST] Membre ajouté : server=%s user=%d", server, discord_id)
    return True


async def remove_onu_ping_member(server: str, discord_id: int) -> bool:
    """Retire un membre de la ping-list d'un serveur."""
    async with get_session() as session:
        result = await session.execute(
            delete(NGONUPingMember).where(
                NGONUPingMember.server == server,
                NGONUPingMember.discord_id == discord_id,
            )
        )
        deleted = result.rowcount > 0

    if deleted:
        log.info("[ONU PING-LIST] Membre retiré : server=%s user=%d", server, discord_id)
    return deleted
