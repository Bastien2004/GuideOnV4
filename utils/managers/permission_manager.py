"""
utils/managers/permission_manager.py.
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import delete, select

from utils.db.models.permission import PermissionEntry, PermissionRole
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

_cache: dict[PermissionRole, set[str]] = {role: set() for role in PermissionRole}
_cache_loaded_at: float = 0.0
_cache_ready: bool = False
_refresh_lock = asyncio.Lock()


# ══════════════════════════════════════════════════════════════════════════
# 🔄 REFRESH (async)
# ══════════════════════════════════════════════════════════════════════════

async def refresh_cache() -> None:
    """Recharge tout le cache depuis la DB. Garde l'ancien cache si erreur."""
    global _cache, _cache_loaded_at, _cache_ready

    async with _refresh_lock:
        try:
            async with get_session() as session:
                rows = (
                    await session.execute(
                        select(PermissionEntry.role, PermissionEntry.discord_id)
                    )
                ).all()
        except Exception:
            log.exception("Refresh cache permissions échoué — on garde l'ancien cache")
            return

        new_cache: dict[PermissionRole, set[str]] = {r: set() for r in PermissionRole}
        for role, discord_id in rows:
            new_cache[role].add(discord_id)

        _cache = new_cache
        _cache_loaded_at = time.monotonic()
        _cache_ready = True


async def cache_refresher_loop(interval: int = CACHE_TTL_SECONDS) -> None:
    """Boucle de fond : refresh toutes les `interval` secondes."""
    log.info("Démarrage de la boucle de refresh permissions (toutes les %ds)", interval)
    while True:
        await asyncio.sleep(interval)
        await refresh_cache()


def cache_is_ready() -> bool:
    return _cache_ready


# ══════════════════════════════════════════════════════════════════════════
# 📖 LECTURES SYNC (compat V3)
# ══════════════════════════════════════════════════════════════════════════

def get_ids_sync(role: PermissionRole) -> list[str]:
    """Liste des discord_id (str) d'un rôle, depuis le cache."""
    if not _cache_ready:
        log.warning("get_ids_sync appelé avant que le cache permissions soit prêt")
        return []
    return sorted(_cache[role])


def has_role_sync(role: PermissionRole, discord_id: int | str) -> bool:
    """True si discord_id possède ce rôle. Lecture sync instantanée."""
    if not _cache_ready:
        log.warning("has_role_sync appelé avant cache prêt (role=%s)", role.value)
        return False
    return str(discord_id) in _cache[role]


# ══════════════════════════════════════════════════════════════════════════
# 📚 LECTURES ASYNC (commande /dev permissions)
# ══════════════════════════════════════════════════════════════════════════

async def list_all() -> dict[str, list[str]]:
    """{role_value: [discord_id, ...]} depuis la DB."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(PermissionEntry.role, PermissionEntry.discord_id)
            )
        ).all()
    out: dict[str, list[str]] = {r.value: [] for r in PermissionRole}
    for role, discord_id in rows:
        out[role.value].append(discord_id)
    return out


# ══════════════════════════════════════════════════════════════════════════
# ✍️ ÉCRITURES ASYNC (invalident le cache)
# ══════════════════════════════════════════════════════════════════════════

async def add_entry(role: PermissionRole, discord_id: int | str) -> bool:
    """Ajoute (role, discord_id). Idempotent. True si créé."""
    discord_id = str(discord_id)
    created = False
    async with get_session() as session:
        exists = await session.scalar(
            select(PermissionEntry.id).where(
                PermissionEntry.role == role,
                PermissionEntry.discord_id == discord_id,
            )
        )
        if exists is None:
            session.add(PermissionEntry(role=role, discord_id=discord_id))
            created = True
    if created:
        await refresh_cache()
        log.info("Ajout permission : %s -> %s", role.value, discord_id)
    return created


async def remove_entry(role: PermissionRole, discord_id: int | str) -> bool:
    """Retire (role, discord_id). True si supprimé."""
    discord_id = str(discord_id)
    async with get_session() as session:
        result = await session.execute(
            delete(PermissionEntry).where(
                PermissionEntry.role == role,
                PermissionEntry.discord_id == discord_id,
            )
        )
        deleted = result.rowcount > 0
    if deleted:
        await refresh_cache()
        log.info("Retrait permission : %s -> %s", role.value, discord_id)
    return deleted


def role_from_str(value: str) -> PermissionRole:
    """Convertit 'DEV' / 'STAFF_GUIDEON' / ... en PermissionRole (insensible casse)."""
    v = value.strip().upper()
    for role in PermissionRole:
        if role.value == v:
            return role
    raise ValueError(f"Rôle de permission inconnu : {value!r}")