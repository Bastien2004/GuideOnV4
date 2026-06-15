"""
utils/managers/alpha_role_react_manager.py — CRUD système Rôle Réaction Alpha.

Cache TTL 60s (config + entrées). Invalidé à chaque écriture.

API publique :
    load_rr_config(guild_id)                              -> dict
    save_rr_config(guild_id, **fields)                    -> dict
    get_rr_entries(guild_id)                              -> list[dict]
    add_rr_entry(guild_id, role_id, label, emoji, desc)   -> bool (False si > MAX ou déjà présent)
    remove_rr_entry(guild_id, entry_id)                   -> bool
    update_rr_entry(guild_id, entry_id, **fields)         -> bool
    get_rr_entry_count(guild_id)                          -> int
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import delete, select

from utils.db.models.alpha_role_react import (
    AlphaRoleReactConfig, AlphaRoleReactEntry, MAX_ROLES
)
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL = 60

# Caches séparés
_cfg_cache:  dict[int, tuple[dict, float]]        = {}
_list_cache: dict[int, tuple[list[dict], float]]  = {}
_lock = asyncio.Lock()


def _cfg_valid(gid: int) -> bool:
    c = _cfg_cache.get(gid); return c is not None and (time.monotonic() - c[1]) < CACHE_TTL

def _list_valid(gid: int) -> bool:
    c = _list_cache.get(gid); return c is not None and (time.monotonic() - c[1]) < CACHE_TTL

def _inv(gid: int) -> None:
    _cfg_cache.pop(gid, None)
    _list_cache.pop(gid, None)


# ════════════════════════════════════════════════════════════
# 📋 Config
# ════════════════════════════════════════════════════════════

async def load_rr_config(guild_id: int) -> dict:
    if _cfg_valid(guild_id):
        return dict(_cfg_cache[guild_id][0])
    async with get_session() as session:
        row = await session.get(AlphaRoleReactConfig, guild_id)
        cfg = row.to_dict() if row else {"guild_id": guild_id, "channel_id": None, "message_id": None}
    _cfg_cache[guild_id] = (cfg, time.monotonic())
    return dict(cfg)


async def save_rr_config(guild_id: int, **fields: object) -> dict:
    allowed = {"channel_id", "message_id"}
    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return await load_rr_config(guild_id)
    async with _lock:
        async with get_session() as session:
            row = await session.get(AlphaRoleReactConfig, guild_id)
            if row is None:
                row = AlphaRoleReactConfig(guild_id=guild_id,
                                           channel_id=None, message_id=None, **clean)
                session.add(row)
            else:
                for k, v in clean.items():
                    setattr(row, k, v)
            await session.flush()
            result = row.to_dict()
        _cfg_cache[guild_id] = (result, time.monotonic())
    return dict(result)


# ════════════════════════════════════════════════════════════
# 🎭 Entrées
# ════════════════════════════════════════════════════════════

async def get_rr_entries(guild_id: int) -> list[dict]:
    if _list_valid(guild_id):
        return list(_list_cache[guild_id][0])
    async with get_session() as session:
        rows = (await session.execute(
            select(AlphaRoleReactEntry)
            .where(AlphaRoleReactEntry.guild_id == guild_id)
            .order_by(AlphaRoleReactEntry.position)
        )).scalars().all()
    entries = [r.to_dict() for r in rows]
    _list_cache[guild_id] = (entries, time.monotonic())
    return list(entries)


async def get_rr_entry_count(guild_id: int) -> int:
    return len(await get_rr_entries(guild_id))


async def add_rr_entry(
    guild_id: int, role_id: int, label: str,
    emoji: str | None = None, description: str | None = None,
) -> bool:
    """Ajoute une entrée. Retourne False si déjà 10 rôles ou rôle déjà présent."""
    async with _lock:
        async with get_session() as session:
            # Vérif max
            count = await session.scalar(
                select(AlphaRoleReactEntry.id)
                .where(AlphaRoleReactEntry.guild_id == guild_id)
            )
            entries_now = (await session.execute(
                select(AlphaRoleReactEntry)
                .where(AlphaRoleReactEntry.guild_id == guild_id)
                .order_by(AlphaRoleReactEntry.position)
            )).scalars().all()

            if len(entries_now) >= MAX_ROLES:
                return False

            # Vérif doublon role_id
            if any(e.role_id == role_id for e in entries_now):
                return False

            # Position = prochain disponible
            used_positions = {e.position for e in entries_now}
            position = next(i for i in range(MAX_ROLES) if i not in used_positions)

            session.add(AlphaRoleReactEntry(
                guild_id=guild_id, position=position, role_id=role_id,
                label=label, emoji=emoji, description=description,
            ))
        _inv(guild_id)
    log.info("[ROLE_REACT] Entrée ajoutée : guild=%d role=%d label=%r", guild_id, role_id, label)
    return True


async def remove_rr_entry(guild_id: int, entry_id: int) -> bool:
    async with _lock:
        async with get_session() as session:
            result = await session.execute(
                delete(AlphaRoleReactEntry).where(
                    AlphaRoleReactEntry.id == entry_id,
                    AlphaRoleReactEntry.guild_id == guild_id,
                )
            )
            deleted = result.rowcount > 0
        if deleted:
            _inv(guild_id)
    if deleted:
        log.info("[ROLE_REACT] Entrée supprimée : guild=%d id=%d", guild_id, entry_id)
    return deleted


async def update_rr_entry(guild_id: int, entry_id: int, **fields: object) -> bool:
    allowed = {"label", "emoji", "description"}
    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return False
    async with _lock:
        async with get_session() as session:
            row = await session.scalar(
                select(AlphaRoleReactEntry).where(
                    AlphaRoleReactEntry.id == entry_id,
                    AlphaRoleReactEntry.guild_id == guild_id,
                )
            )
            if row is None:
                return False
            for k, v in clean.items():
                setattr(row, k, v)
        _inv(guild_id)
    return True