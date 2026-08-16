"""
utils/managers/mod_automod_general_manager.py — CRUD des paramètres généraux
d'auto-modération.

Une ligne par guild. Cache TTL 60s sur load : la config change rarement (une
poignée de fois par jour au grand max côté admin) alors qu'elle est lue à
chaque message reçu — sans cache, c'est un round-trip DB par message.
"""
from __future__ import annotations

import time

from sqlalchemy import select

from utils.db.models.mod_automod_general import ModAutomodGeneral
from utils.db.session import get_session

# ═══ Cache ═════════════════════════════════════════════════════════
_CACHE_TTL = 60  # secondes
_cache: dict[int, tuple[dict, float]] = {}


def _fresh(guild_id: int) -> dict | None:
    entry = _cache.get(guild_id)
    if entry is None:
        return None
    payload, ts = entry
    if time.monotonic() - ts > _CACHE_TTL:
        return None
    return dict(payload)


def _prime(guild_id: int, payload: dict) -> None:
    _cache[guild_id] = (dict(payload), time.monotonic())


def _invalidate(guild_id: int) -> None:
    _cache.pop(guild_id, None)


_DEFAULTS: dict = {
    "guild_id": None,
    "alert_channel_id": None,
    "notify_in_channel": True,
}


# ═══ Lectures ══════════════════════════════════════════════════════

async def load_general(guild_id: int) -> dict:
    """Retourne la config générale (defaults si absente en DB)."""
    cached = _fresh(guild_id)
    if cached is not None:
        return cached

    async with get_session() as session:
        row = await session.get(ModAutomodGeneral, guild_id)
        payload = row.to_dict() if row else {**_DEFAULTS, "guild_id": guild_id}

    _prime(guild_id, payload)
    return dict(payload)


# ═══ Écritures ═════════════════════════════════════════════════════

async def save_general(guild_id: int, **fields) -> dict:
    """
    Upsert des paramètres. Seules les clés `alert_channel_id` et
    `notify_in_channel` sont acceptées — tout autre kwarg est ignoré
    silencieusement pour empêcher un caller de setter des colonnes qu'il
    n'aurait pas identifiées.
    """
    allowed = {"alert_channel_id", "notify_in_channel"}
    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return await load_general(guild_id)

    async with get_session() as session:
        row = await session.get(ModAutomodGeneral, guild_id)
        if row is None:
            row = ModAutomodGeneral(guild_id=guild_id, **clean)
            session.add(row)
        else:
            for k, v in clean.items():
                setattr(row, k, v)
        await session.flush()
        payload = row.to_dict()

    _prime(guild_id, payload)
    return dict(payload)


async def reset_general(guild_id: int) -> None:
    """Supprime la ligne : retour aux defaults."""
    async with get_session() as session:
        row = await session.get(ModAutomodGeneral, guild_id)
        if row is not None:
            await session.delete(row)
    _invalidate(guild_id)