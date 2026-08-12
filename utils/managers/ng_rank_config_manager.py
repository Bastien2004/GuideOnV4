"""
utils/managers/ng_rank_config_manager.py — Config du système rank, multi-
serveurs (refonte multi-serveurs, phase 7, ex-alpha_rank_config_manager.py).

Cache mémoire TTL 1 min par serveur NG. Invalidé à chaque écriture.

API publique :
    await load_rank_config(server) -> dict
    await save_rank_config(server, **fields) -> dict
    await get_rank_config_obj(server) -> NGRankConfig | None
"""
from __future__ import annotations

import asyncio
import logging
import time

from utils.db.models.ng_rank_config import NGRankConfig
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

_cache: dict[str, tuple[dict, float]] = {}
_lock = asyncio.Lock()

_FIELDS = {
    "rank_channel_id", "journaliste_channel_id", "dev_channel_id",
    "journaliste_ping_id", "dev_ping_id",
    "role_journaliste_id", "role_guide_id",
    "role_moderateur_test_id", "role_moderateur_confirme_id",
    "role_moderateur_plus_id", "role_super_moderateur_id", "role_administrateur_id",
    "role_affilie_id", "role_builder_id", "role_equipe_id",
    "content_nous_rejoindre_channel_id", "content_nous_rejoindre_ping_id",
    "content_nous_rejoindre_emoji",
    "content_index_channel_id", "content_index_emoji",
    "content_regle_interne_channel_id", "content_regle_interne_emoji",
    "content_stafflist_channel_id",
    "rank_emoji",
}

_DEFAULT: dict = {f: None for f in _FIELDS}


def _default() -> dict:
    return _DEFAULT.copy()


def _is_valid(server: str) -> bool:
    cached = _cache.get(server)
    return cached is not None and (time.monotonic() - cached[1]) < CACHE_TTL_SECONDS


def _invalidate(server: str) -> None:
    _cache.pop(server, None)


async def load_rank_config(server: str) -> dict:
    """Retourne la config complète (avec `server` inclus). Valeurs None si non configurée."""
    if _is_valid(server):
        return dict(_cache[server][0])

    async with get_session() as session:
        row = await session.get(NGRankConfig, server)
        cfg = row.to_dict() if row is not None else {"server": server, **_default()}

    _cache[server] = (cfg, time.monotonic())
    return dict(cfg)


async def get_rank_config_obj(server: str) -> NGRankConfig | None:
    """Retourne l'objet ORM brut (sans cache). Utile pour les accès directs aux attributs."""
    async with get_session() as session:
        return await session.get(NGRankConfig, server)


async def save_rank_config(server: str, **fields: object) -> dict:
    """
    Upsert partiel : ne touche que les clés fournies.
    Invalide le cache. Retourne la config complète à jour.
    """
    clean = {k: v for k, v in fields.items() if k in _FIELDS}
    if not clean:
        return await load_rank_config(server)

    async with _lock:
        async with get_session() as session:
            row = await session.get(NGRankConfig, server)
            if row is None:
                merged = {**_default(), **clean}
                row = NGRankConfig(server=server, **merged)
                session.add(row)
            else:
                for k, v in clean.items():
                    setattr(row, k, v)
            await session.flush()
            result = row.to_dict()

        _cache[server] = (result, time.monotonic())
    return dict(result)
