"""
utils/managers/alpha_rank_config_manager.py — Config du système rank Alpha.

Cache mémoire TTL 1 min par guild. Invalidé à chaque écriture.

API publique :
    await load_rank_config(guild_id) -> dict
    await save_rank_config(guild_id, **fields) -> dict
    await get_rank_config_obj(guild_id) -> AlphaRankConfig | None
"""
from __future__ import annotations

import asyncio
import logging
import time

from utils.db.models.alpha_rank_config import AlphaRankConfig
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

_cache: dict[int, tuple[dict, float]] = {}
_lock = asyncio.Lock()

_FIELDS = {
    "rank_channel_id", "journaliste_channel_id", "dev_channel_id",
    "journaliste_ping_id", "dev_ping_id",
    "role_journaliste_id", "role_guide_id",
    "role_moderateur_test_id", "role_moderateur_confirme_id",
    "role_moderateur_plus_id", "role_super_moderateur_id", "role_administrateur_id",
    # Contenu Discord
    "content_nous_rejoindre_channel_id", "content_nous_rejoindre_ping_id",
    "content_nous_rejoindre_emoji",
    "content_index_channel_id", "content_index_emoji",
    "content_regle_interne_channel_id", "content_regle_interne_emoji",
    "content_stafflist_channel_id",
}

_DEFAULT: dict = {f: None for f in _FIELDS}


def _default() -> dict:
    return _DEFAULT.copy()


def _is_valid(guild_id: int) -> bool:
    cached = _cache.get(guild_id)
    return cached is not None and (time.monotonic() - cached[1]) < CACHE_TTL_SECONDS


def _invalidate(guild_id: int) -> None:
    _cache.pop(guild_id, None)


async def load_rank_config(guild_id: int) -> dict:
    """Retourne la config complète (avec guild_id inclus). Valeurs None si non configurée."""
    if _is_valid(guild_id):
        return dict(_cache[guild_id][0])

    async with get_session() as session:
        row = await session.get(AlphaRankConfig, guild_id)
        cfg = row.to_dict() if row is not None else {"guild_id": guild_id, **_default()}

    _cache[guild_id] = (cfg, time.monotonic())
    return dict(cfg)


async def get_rank_config_obj(guild_id: int) -> AlphaRankConfig | None:
    """Retourne l'objet ORM brut (sans cache). Utile pour les accès directs aux attributs."""
    async with get_session() as session:
        return await session.get(AlphaRankConfig, guild_id)


async def save_rank_config(guild_id: int, **fields: object) -> dict:
    """
    Upsert partiel : ne touche que les clés fournies.
    Invalide le cache. Retourne la config complète à jour.
    """
    clean = {k: v for k, v in fields.items() if k in _FIELDS}
    if not clean:
        return await load_rank_config(guild_id)

    async with _lock:
        async with get_session() as session:
            row = await session.get(AlphaRankConfig, guild_id)
            if row is None:
                merged = {**_default(), **clean}
                row = AlphaRankConfig(guild_id=guild_id, **merged)
                session.add(row)
            else:
                for k, v in clean.items():
                    setattr(row, k, v)
            await session.flush()
            result = row.to_dict()

        _cache[guild_id] = (result, time.monotonic())
    return dict(result)