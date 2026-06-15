"""
utils/managers/command_toggle_manager.py — Cache + accès DB pour CommandControl.

Système de maintenance GLOBAL (pas par serveur) : une commande togglée est
désactivée pour tous les guilds. Cache mémoire TTL 60s, invalidé à chaque toggle.

API publique :
    await is_command_enabled(command_name) -> bool
        True si activée OU absente de la table (= activée par défaut).
    await get_all_commands() -> dict[str, bool]
        {command_name: enabled} pour toutes les entrées en DB.
    await toggle_command(command_name) -> dict[str, bool]
        Inverse l'état (crée la ligne désactivée si absente).
        Retourne le dict complet à jour.
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import select

from utils.db.models.control_admin import CommandControl
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

_cache: dict[str, bool] | None = None
_cache_at: float = 0.0
_lock = asyncio.Lock()


# ════════════════════════════════════════════════════════════
# 🔄 Cache interne
# ════════════════════════════════════════════════════════════

def _is_valid() -> bool:
    return _cache is not None and (time.monotonic() - _cache_at) < CACHE_TTL_SECONDS


def _invalidate() -> None:
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0


async def _load_from_db() -> dict[str, bool]:
    async with get_session() as session:
        rows = (await session.execute(select(CommandControl))).scalars().all()
    return {row.command_name: row.enabled for row in rows}


async def _get_cache() -> dict[str, bool]:
    global _cache, _cache_at
    if _is_valid():
        return dict(_cache)
    async with _lock:
        if _is_valid():
            return dict(_cache)
        _cache = await _load_from_db()
        _cache_at = time.monotonic()
    return dict(_cache)


# ════════════════════════════════════════════════════════════
# 📖 Lectures
# ════════════════════════════════════════════════════════════

async def get_all_commands() -> dict[str, bool]:
    """Retourne {command_name: enabled} pour toutes les entrées en DB."""
    return await _get_cache()


async def is_command_enabled(command_name: str) -> bool:
    """
    True si la commande est activée.
    Une commande absente de la table CommandControl est considérée comme
    activée par défaut (seules les commandes explicitement désactivées
    bloquent l'exécution).
    """
    data = await _get_cache()
    return data.get(command_name, True)


# ════════════════════════════════════════════════════════════
# ✍️ Écriture
# ════════════════════════════════════════════════════════════

async def toggle_command(command_name: str) -> dict[str, bool]:
    """
    Inverse l'état d'une commande.
    Crée la ligne (désactivée) si elle n'existe pas encore.
    Invalide le cache. Retourne le dict complet à jour.
    """
    new_state: bool | None = None
    async with _lock:
        async with get_session() as session:
            row = await session.scalar(
                select(CommandControl).where(CommandControl.command_name == command_name)
            )
            if row is None:
                row = CommandControl(command_name=command_name, enabled=False)
                session.add(row)
            else:
                row.enabled = not row.enabled
            await session.flush()
            new_state = row.enabled
        _invalidate()

    log.info("[MAINTENANCE] %s -> %s", command_name, "ON" if new_state else "OFF")
    return await get_all_commands()