"""
utils/managers/mod_automod_antiflood_manager.py — CRUD Anti Flood.

Même structure que mod_automod_antifullcaps_manager.py : une config simple
(enabled + deux seuils numériques), cache TTL 60s (lu à chaque message).
"""
from __future__ import annotations

import time

from utils.db.models.mod_automod_antiflood import ModAutomodAntifloodConfig
from utils.db.session import get_session

_TTL = 60
_cache: dict[int, tuple[dict, float]] = {}

_DEFAULTS: dict = {
    "guild_id": None,
    "enabled": False,
    "min_length": 20,
    "min_vowel_ratio": 0.2,
}

_ALLOWED_FIELDS = {"enabled", "min_length", "min_vowel_ratio"}


def _fresh(guild_id: int) -> dict | None:
    entry = _cache.get(guild_id)
    if entry is None:
        return None
    payload, ts = entry
    if time.monotonic() - ts > _TTL:
        return None
    return dict(payload)


def _prime(guild_id: int, payload: dict) -> None:
    _cache[guild_id] = (dict(payload), time.monotonic())


def _invalidate(guild_id: int) -> None:
    _cache.pop(guild_id, None)


async def load_config(guild_id: int) -> dict:
    """Retourne la config (defaults si absente)."""
    cached = _fresh(guild_id)
    if cached is not None:
        return cached

    async with get_session() as session:
        row = await session.get(ModAutomodAntifloodConfig, guild_id)
        payload = row.to_dict() if row else {**_DEFAULTS, "guild_id": guild_id}

    _prime(guild_id, payload)
    return dict(payload)


async def save_config(guild_id: int, **fields) -> dict:
    """Upsert des paramètres. Champs autorisés : enabled, min_length, min_vowel_ratio."""
    clean = {k: v for k, v in fields.items() if k in _ALLOWED_FIELDS}
    if not clean:
        return await load_config(guild_id)

    async with get_session() as session:
        row = await session.get(ModAutomodAntifloodConfig, guild_id)
        if row is None:
            row = ModAutomodAntifloodConfig(guild_id=guild_id, **clean)
            session.add(row)
        else:
            for k, v in clean.items():
                setattr(row, k, v)
        await session.flush()
        payload = row.to_dict()

    _prime(guild_id, payload)
    return dict(payload)


async def set_enabled(guild_id: int, enabled: bool) -> dict:
    return await save_config(guild_id, enabled=enabled)