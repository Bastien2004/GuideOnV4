"""
utils/managers/ng_role_react_manager.py — CRUD système Rôle Réaction multi-serveurs.

Refonte multi-serveurs phase 10 : remplace alpha_role_react_manager.py.
Même API, clé `server` (nom NGServer) au lieu de `guild_id`.

Différence notable avec l'original : NGRoleReactCouple.server porte
désormais une vraie FK vers NGRoleReaction.server (ON DELETE CASCADE, cf.
docstring de utils/db/models/ng_role_react.py). add_rr_entry() fait donc un
get-or-create de la ligne NGRoleReaction avant d'insérer un couple, pour
préserver le flux existant où un rôle pouvait être ajouté avant même qu'un
salon/message soit configuré.

Cache TTL 60s (config + entrées). Invalidé à chaque écriture.

API publique :
    load_rr_config(server)                              -> dict
    save_rr_config(server, **fields)                    -> dict
    get_rr_entries(server)                              -> list[dict]
    add_rr_entry(server, role_id, label, emoji, desc)   -> bool (False si > MAX ou déjà présent)
    remove_rr_entry(server, entry_id)                   -> bool
    update_rr_entry(server, entry_id, **fields)         -> bool
    get_rr_entry_count(server)                          -> int
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import delete, select

from utils.db.models.ng_role_react import MAX_ROLES, NGRoleReactCouple, NGRoleReaction
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL = 60

# Caches séparés
_cfg_cache:  dict[str, tuple[dict, float]]        = {}
_list_cache: dict[str, tuple[list[dict], float]]  = {}
_lock = asyncio.Lock()


def _cfg_valid(server: str) -> bool:
    c = _cfg_cache.get(server)
    return c is not None and (time.monotonic() - c[1]) < CACHE_TTL


def _list_valid(server: str) -> bool:
    c = _list_cache.get(server)
    return c is not None and (time.monotonic() - c[1]) < CACHE_TTL


def _inv(server: str) -> None:
    _cfg_cache.pop(server, None)
    _list_cache.pop(server, None)


# ════════════════════════════════════════════════════════════
# 📋 Config
# ════════════════════════════════════════════════════════════

async def load_rr_config(server: str) -> dict:
    if _cfg_valid(server):
        return dict(_cfg_cache[server][0])
    async with get_session() as session:
        row = await session.get(NGRoleReaction, server)
        cfg = row.to_dict() if row else {"server": server, "channel_id": None, "message_id": None}
    _cfg_cache[server] = (cfg, time.monotonic())
    return dict(cfg)


async def save_rr_config(server: str, **fields: object) -> dict:
    allowed = {"channel_id", "message_id"}
    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return await load_rr_config(server)
    async with _lock:
        async with get_session() as session:
            row = await session.get(NGRoleReaction, server)
            if row is None:
                defaults = {"channel_id": None, "message_id": None}
                defaults.update(clean)
                row = NGRoleReaction(server=server, **defaults)
                session.add(row)
            else:
                for k, v in clean.items():
                    setattr(row, k, v)
            await session.flush()
            result = row.to_dict()
        _cfg_cache[server] = (result, time.monotonic())
    return dict(result)


async def _ensure_parent_row(session, server: str) -> None:
    """Get-or-create la ligne NGRoleReaction — requis par la FK cascade sur
    NGRoleReactCouple.server. Doit être appelé DANS la même session/transaction
    que l'insertion du couple qui suit, sous le verrou _lock (voir add_rr_entry)."""
    existing = await session.get(NGRoleReaction, server)
    if existing is None:
        session.add(NGRoleReaction(server=server, channel_id=None, message_id=None))
        await session.flush()


# ════════════════════════════════════════════════════════════
# 🎭 Entrées
# ════════════════════════════════════════════════════════════

async def get_rr_entries(server: str) -> list[dict]:
    if _list_valid(server):
        return list(_list_cache[server][0])
    async with get_session() as session:
        rows = (await session.execute(
            select(NGRoleReactCouple)
            .where(NGRoleReactCouple.server == server)
            .order_by(NGRoleReactCouple.position)
        )).scalars().all()
    entries = [r.to_dict() for r in rows]
    _list_cache[server] = (entries, time.monotonic())
    return list(entries)


async def get_rr_entry_count(server: str) -> int:
    return len(await get_rr_entries(server))


async def add_rr_entry(
    server: str, role_id: int, label: str,
    emoji: str | None = None, description: str | None = None,
) -> bool:
    """Ajoute une entrée. Retourne False si déjà 10 rôles ou rôle déjà présent."""
    async with _lock:
        async with get_session() as session:
            entries_now = (await session.execute(
                select(NGRoleReactCouple)
                .where(NGRoleReactCouple.server == server)
                .order_by(NGRoleReactCouple.position)
            )).scalars().all()

            if len(entries_now) >= MAX_ROLES:
                return False

            # Vérif doublon role_id
            if any(e.role_id == role_id for e in entries_now):
                return False

            # Position = prochain disponible
            used_positions = {e.position for e in entries_now}
            position = next(i for i in range(MAX_ROLES) if i not in used_positions)

            # FK cascade : la ligne parente doit exister avant d'insérer le couple.
            await _ensure_parent_row(session, server)

            session.add(NGRoleReactCouple(
                server=server, position=position, role_id=role_id,
                label=label, emoji=emoji, description=description,
            ))
        _inv(server)
    log.info("[ROLE_REACT] Entrée ajoutée : server=%s role=%d label=%r", server, role_id, label)
    return True


async def remove_rr_entry(server: str, entry_id: int) -> bool:
    async with _lock:
        async with get_session() as session:
            result = await session.execute(
                delete(NGRoleReactCouple).where(
                    NGRoleReactCouple.id == entry_id,
                    NGRoleReactCouple.server == server,
                )
            )
            deleted = result.rowcount > 0
        if deleted:
            _inv(server)
    if deleted:
        log.info("[ROLE_REACT] Entrée supprimée : server=%s id=%d", server, entry_id)
    return deleted


async def update_rr_entry(server: str, entry_id: int, **fields: object) -> bool:
    allowed = {"label", "emoji", "description"}
    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return False
    async with _lock:
        async with get_session() as session:
            row = await session.scalar(
                select(NGRoleReactCouple).where(
                    NGRoleReactCouple.id == entry_id,
                    NGRoleReactCouple.server == server,
                )
            )
            if row is None:
                return False
            for k, v in clean.items():
                setattr(row, k, v)
        _inv(server)
    return True
