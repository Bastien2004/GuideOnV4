"""
utils/managers/mod_automod_nolink_manager.py — CRUD du système No Link.

Deux niveaux d'API, sur le même modèle que mod_automod_banword_manager.py :
  - config globale (enabled) via load_config / save_config / set_enabled
  - liste des salons whitelistés via list_whitelist / add_channel /
    remove_channel / clear_whitelist

Cache TTL 60s sur la config ET sur la whitelist — les deux sont lues à
chaque message reçu quand le système est activé (le listener a besoin de
savoir si le salon du message est whitelisté AVANT même d'appeler le
détecteur).
"""
from __future__ import annotations

import time

from sqlalchemy import delete, select

from utils.db.models.mod_automod_nolink import (
    ModAutomodNolinkConfig,
    ModAutomodNolinkWhitelist,
)
from utils.db.session import get_session

# ═══ Cache config ══════════════════════════════════════════════════
_CFG_TTL = 60
_cfg_cache: dict[int, tuple[dict, float]] = {}

# ═══ Cache whitelist ═════════════════════════════════════════════════
_WL_TTL = 60
_wl_cache: dict[int, tuple[list[int], float]] = {}


def _cfg_fresh(guild_id: int) -> dict | None:
    entry = _cfg_cache.get(guild_id)
    if entry is None:
        return None
    payload, ts = entry
    if time.monotonic() - ts > _CFG_TTL:
        return None
    return dict(payload)


def _cfg_prime(guild_id: int, payload: dict) -> None:
    _cfg_cache[guild_id] = (dict(payload), time.monotonic())


def _wl_fresh(guild_id: int) -> list[int] | None:
    entry = _wl_cache.get(guild_id)
    if entry is None:
        return None
    channel_ids, ts = entry
    if time.monotonic() - ts > _WL_TTL:
        return None
    return list(channel_ids)


def _wl_prime(guild_id: int, channel_ids: list[int]) -> None:
    _wl_cache[guild_id] = (list(channel_ids), time.monotonic())


def _wl_invalidate(guild_id: int) -> None:
    _wl_cache.pop(guild_id, None)


# ═══ Config (enabled) ═══════════════════════════════════════════════

async def load_config(guild_id: int) -> dict:
    """Retourne {'guild_id', 'enabled', 'bypass_gif'}. Defaults: False/False."""
    cached = _cfg_fresh(guild_id)
    if cached is not None:
        return cached

    async with get_session() as session:
        row = await session.get(ModAutomodNolinkConfig, guild_id)
        payload = row.to_dict() if row else {
            "guild_id": guild_id, "enabled": False, "bypass_gif": False,
        }

    _cfg_prime(guild_id, payload)
    return dict(payload)


async def set_enabled(guild_id: int, enabled: bool) -> dict:
    """Active ou désactive le système pour un serveur."""
    async with get_session() as session:
        row = await session.get(ModAutomodNolinkConfig, guild_id)
        if row is None:
            row = ModAutomodNolinkConfig(guild_id=guild_id, enabled=enabled)
            session.add(row)
        else:
            row.enabled = enabled
        await session.flush()
        payload = row.to_dict()

    _cfg_prime(guild_id, payload)
    return dict(payload)


async def set_bypass_gif(guild_id: int, bypass_gif: bool) -> dict:
    """Active ou désactive le bypass des liens GIF (Tenor/Giphy/.gif) pour un serveur."""
    async with get_session() as session:
        row = await session.get(ModAutomodNolinkConfig, guild_id)
        if row is None:
            row = ModAutomodNolinkConfig(guild_id=guild_id, enabled=False, bypass_gif=bypass_gif)
            session.add(row)
        else:
            row.bypass_gif = bypass_gif
        await session.flush()
        payload = row.to_dict()

    _cfg_prime(guild_id, payload)
    return dict(payload)


# ═══ Salons whitelistés ═══════════════════════════════════════════════

async def list_whitelist(guild_id: int) -> list[int]:
    """Retourne les ids des salons whitelistés d'un serveur, triés."""
    cached = _wl_fresh(guild_id)
    if cached is not None:
        return cached

    async with get_session() as session:
        rows = (await session.execute(
            select(ModAutomodNolinkWhitelist.channel_id)
            .where(ModAutomodNolinkWhitelist.guild_id == guild_id)
            .order_by(ModAutomodNolinkWhitelist.channel_id)
        )).scalars().all()

    channel_ids = list(rows)
    _wl_prime(guild_id, channel_ids)
    return list(channel_ids)


async def is_whitelisted(guild_id: int, channel_id: int) -> bool:
    """
    True si `channel_id` est whitelisté. Passe par le cache de
    list_whitelist (pas de requête DB dédiée : la whitelist entière tient
    largement en mémoire et est déjà rafraîchie régulièrement).
    """
    return channel_id in await list_whitelist(guild_id)


async def add_channel(guild_id: int, channel_id: int) -> bool:
    """Ajoute un salon à la whitelist. Retourne True si ajouté, False si déjà présent."""
    async with get_session() as session:
        existing = await session.scalar(
            select(ModAutomodNolinkWhitelist.id).where(
                ModAutomodNolinkWhitelist.guild_id == guild_id,
                ModAutomodNolinkWhitelist.channel_id == channel_id,
            )
        )
        if existing is not None:
            return False
        session.add(ModAutomodNolinkWhitelist(guild_id=guild_id, channel_id=channel_id))

    _wl_invalidate(guild_id)
    return True


async def remove_channel(guild_id: int, channel_id: int) -> bool:
    """Retire un salon de la whitelist. Retourne True si retiré, False si absent."""
    async with get_session() as session:
        row = await session.scalar(
            select(ModAutomodNolinkWhitelist).where(
                ModAutomodNolinkWhitelist.guild_id == guild_id,
                ModAutomodNolinkWhitelist.channel_id == channel_id,
            )
        )
        if row is None:
            return False
        await session.delete(row)

    _wl_invalidate(guild_id)
    return True


async def clear_whitelist(guild_id: int) -> int:
    """Supprime tous les salons whitelistés d'un serveur. Retourne le nombre supprimé."""
    async with get_session() as session:
        result = await session.execute(
            delete(ModAutomodNolinkWhitelist).where(
                ModAutomodNolinkWhitelist.guild_id == guild_id
            )
        )
        deleted = result.rowcount or 0

    _wl_invalidate(guild_id)
    return int(deleted)