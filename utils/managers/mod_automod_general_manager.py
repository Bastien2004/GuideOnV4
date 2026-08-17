"""
utils/managers/mod_automod_general_manager.py — CRUD paramètres généraux automod.

Cache TTL 60s (lu à chaque message reçu, très fréquent).
"""
from __future__ import annotations

import time

from utils.db.models.mod_automod_general import ModAutomodGeneral
from utils.db.session import get_session

_TTL = 60
_cache: dict[int, tuple[dict, float]] = {}

# Bornes de sécurité pour notification_window_seconds (10s → 3min).
WINDOW_MIN = 10
WINDOW_MAX = 180
WINDOW_DEFAULT = 60

_DEFAULTS: dict = {
    "guild_id": None,
    "alert_channel_id": None,
    "staff_role_id": None,
    "notify_in_channel": True,
    "notification_window_seconds": WINDOW_DEFAULT,
}

_ALLOWED_FIELDS = {
    "alert_channel_id",
    "staff_role_id",
    "notify_in_channel",
    "notification_window_seconds",
}


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


async def load_general(guild_id: int) -> dict:
    """Retourne la config (defaults si absente)."""
    cached = _fresh(guild_id)
    if cached is not None:
        return cached

    async with get_session() as session:
        row = await session.get(ModAutomodGeneral, guild_id)
        payload = row.to_dict() if row else {**_DEFAULTS, "guild_id": guild_id}

    _prime(guild_id, payload)
    return dict(payload)


async def save_general(guild_id: int, **fields) -> dict:
    """
    Upsert. Champs autorisés : alert_channel_id, staff_role_id,
    notify_in_channel, notification_window_seconds.

    notification_window_seconds est clampé automatiquement à [WINDOW_MIN, WINDOW_MAX]
    pour éviter les valeurs absurdes.
    """
    clean = {k: v for k, v in fields.items() if k in _ALLOWED_FIELDS}
    if not clean:
        return await load_general(guild_id)

    if "notification_window_seconds" in clean and clean["notification_window_seconds"] is not None:
        clean["notification_window_seconds"] = max(
            WINDOW_MIN, min(WINDOW_MAX, int(clean["notification_window_seconds"])),
        )

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