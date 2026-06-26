"""
utils/managers/notations_manager.py
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import select

from utils.db.models.notations import NotationConfig
from utils.db.engine import get_session


log = logging.getLogger(__name__)

# Durée de vie du cache avant qu'un refresh soit considéré comme "périmé".
CACHE_TTL_SECONDS = 60

# ──────────────────────────────────────────────────────────────────────────
# État du cache (module-level, partagé dans le process)
#   _cache -> dict brut de la config (None si pas encore chargé)
# ──────────────────────────────────────────────────────────────────────────
_cache: dict | None = None
_cache_loaded_at: float = 0.0          # time.monotonic() du dernier refresh OK
_cache_ready: bool = False             # True dès qu'un refresh a réussi une fois
_refresh_lock = asyncio.Lock()         # évite deux refresh concurrents


# ══════════════════════════════════════════════════════════════════════════
# 🔄 REFRESH (async) — remplit le cache depuis la DB
# ══════════════════════════════════════════════════════════════════════════

async def refresh_cache() -> None:
    """
    Recharge la config depuis la DB.
    Si aucune ligne n'existe, le cache reste None mais _cache_ready passe True.
    """
    global _cache, _cache_loaded_at, _cache_ready

    async with _refresh_lock:
        try:
            async with get_session() as session:
                row = await session.scalar(select(NotationConfig))
        except Exception:
            log.exception("Refresh cache notations échoué — on garde l'ancien cache")
            return

        _cache = row.to_dict() if row is not None else None
        _cache_loaded_at = time.monotonic()
        _cache_ready = True


async def cache_refresher_loop(interval: int = CACHE_TTL_SECONDS) -> None:
    """
    Boucle de fond : refresh toutes les `interval` secondes.
    À lancer via bot.loop.create_task() dans setup_hook().
    """
    log.info("Démarrage de la boucle de refresh notations (toutes les %ds)", interval)
    while True:
        await asyncio.sleep(interval)
        await refresh_cache()


def cache_is_ready() -> bool:
    """True si au moins un refresh a réussi (cache exploitable)."""
    return _cache_ready


def cache_age_seconds() -> float:
    """Âge du cache en secondes (utile pour du monitoring/healthcheck)."""
    if not _cache_ready:
        return float("inf")
    return time.monotonic() - _cache_loaded_at


# ══════════════════════════════════════════════════════════════════════════
# 📖 LECTURES SYNC (compat bot interne) — tapent uniquement le cache mémoire
# ══════════════════════════════════════════════════════════════════════════

def get_config_sync() -> dict | None:
    """
    Lecture sync pure cache. Ne fait JAMAIS d'I/O ni d'await.
    Renvoie None si aucune config n'est enregistrée ou si le cache n'est pas prêt.
    """
    if not _cache_ready:
        log.warning("get_config_sync() appelé avant que le cache notations soit prêt → None")
        return None
    return _cache.copy() if _cache is not None else None


# ══════════════════════════════════════════════════════════════════════════
# 📚 LECTURES ASYNC — tapent la DB directement (pour l'API)
# ══════════════════════════════════════════════════════════════════════════

async def get_config() -> dict | None:
    """
    Renvoie la config complète depuis la DB (pas le cache).
    Renvoie None si aucune config n'est enregistrée.
    """
    async with get_session() as session:
        row = await session.scalar(select(NotationConfig))
    return row.to_dict() if row is not None else None


# ══════════════════════════════════════════════════════════════════════════
# ✍️ ÉCRITURES ASYNC — appelées par l'API ; invalident le cache ensuite
# ══════════════════════════════════════════════════════════════════════════

async def update_full_config(data: dict) -> dict:
    guild_id = data["id_guild_notations"]

    async with get_session() as session:
        row = await session.get(NotationConfig, guild_id)
        if row is None:
            row = NotationConfig(**data)
            session.add(row)
        else:
            for key, value in data.items():
                setattr(row, key, value)

        await session.flush()
        await session.commit()
        result = row.to_dict()

    await refresh_cache()
    log.info("Config notations mise à jour complète (guild=%s)", guild_id)
    return result


async def update_partial(partial: dict) -> dict:
    async with get_session() as session:
        row = await session.scalar(select(NotationConfig))
        if row is None:
            raise ValueError(
                "Aucune config notations en DB — utilisez update_full_config() d'abord."
            )
        for key, value in partial.items():
            setattr(row, key, value)

        await session.flush()
        await session.commit()
        result = row.to_dict()

    await refresh_cache()
    log.info("Config notations mise à jour partielle : %s", list(partial.keys()))
    return result