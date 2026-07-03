"""
utils/managers/staff_manager.py — Manager API pour StaffConfig.

⚠️ Non câblé actuellement : aucune route API ni commande Discord n'importe
ce module (vérifié par recherche exhaustive le 2026-07-03). La table
staff_config existe en DB (migration déjà appliquée) mais rien ne la lit
ni ne l'écrit en pratique. Candidat à suppression ou à finir de câbler.
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import select

from utils.db.models.staff import StaffConfig
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

_cache: dict | None = None
_cache_loaded_at: float = 0.0
_cache_ready: bool = False
_refresh_lock = asyncio.Lock()


# ══════════════════════════════════════════════════════════════════════════
# 🔄 REFRESH (async)
# ══════════════════════════════════════════════════════════════════════════

async def refresh_cache() -> None:
    """Recharge la config Staff depuis la DB."""
    global _cache, _cache_loaded_at, _cache_ready

    async with _refresh_lock:
        try:
            async with get_session() as session:
                row = await session.scalar(select(StaffConfig).limit(1))
        except Exception:
            log.exception("Refresh cache staff échoué")
            return

        _cache = row.to_dict() if row is not None else None
        _cache_loaded_at = time.monotonic()
        _cache_ready = True


async def cache_refresher_loop(interval: int = CACHE_TTL_SECONDS) -> None:
    """Boucle de refresh automatique."""
    log.info("Démarrage de la boucle de refresh staff (toutes les %ds)", interval)
    while True:
        await asyncio.sleep(interval)
        await refresh_cache()


def cache_is_ready() -> bool:
    return _cache_ready


def cache_age_seconds() -> float:
    if not _cache_ready:
        return float("inf")
    return time.monotonic() - _cache_loaded_at


# ══════════════════════════════════════════════════════════════════════════
# 📖 LECTURES SYNC
# ══════════════════════════════════════════════════════════════════════════

def get_config_sync() -> dict | None:
    """Lecture sync pure cache."""
    if not _cache_ready:
        log.warning("get_config_sync() appelé avant que le cache staff soit prêt")
        return None
    return _cache.copy() if _cache is not None else None


# ══════════════════════════════════════════════════════════════════════════
# 📚 LECTURES ASYNC (pour l'API)
# ══════════════════════════════════════════════════════════════════════════

async def get_config() -> dict | None:
    """Renvoie la config Staff depuis la DB."""
    async with get_session() as session:
        row = await session.scalar(select(StaffConfig).limit(1))
    return row.to_dict() if row is not None else None


# ══════════════════════════════════════════════════════════════════════════
# ✍️ ÉCRITURES ASYNC
# ══════════════════════════════════════════════════════════════════════════

async def update_full_config(data: dict) -> dict:
    """Écrase la config complète (upsert sur id=1)."""
    async with get_session() as session:
        row = await session.get(StaffConfig, 1)
        if row is None:
            row = StaffConfig(**data, id=1)
            session.add(row)
        else:
            for key, value in data.items():
                if hasattr(row, key):
                    setattr(row, key, value)

        await session.flush()
        result = row.to_dict()

    await refresh_cache()
    log.info("Config staff mise à jour complète")
    return result


async def update_partial(partial: dict) -> dict:
    """Met à jour uniquement les champs fournis."""
    async with get_session() as session:
        row = await session.get(StaffConfig, 1)
        if row is None:
            raise ValueError(
                "Aucune config staff en DB — utilisez update_full_config() d'abord."
            )

        for key, value in partial.items():
            if hasattr(row, key):
                setattr(row, key, value)

        await session.flush()
        result = row.to_dict()

    await refresh_cache()
    log.info("Config staff mise à jour partielle : %s", list(partial.keys()))
    return result