"""
utils/managers/notations_manager.py — Manager API pour NGNotaConfig.

Miroir en cache sync de la config notations, pour des lectures rapides
côté API (cogs/api/notation_api_app.py) sans aller-retour DB à chaque
requête. Séparé du manager Discord (ng_nota_manager.py) qui a son propre
cache TTL indépendant sur le même modèle.

Refonte multi-serveurs phase 9 : ce module — comme l'API `/notations/*`
qu'il alimente — a TOUJOURS été conçu pour un unique serveur : `GET
/notations`, `/notations/set_ids` et `/notations/set_time` ne prennent
aucun `guild_id`/identifiant de serveur en entrée, il n'existe donc aucun
signal pour router vers un serveur NG en particulier (contrairement à
`onu_manager.py` où chaque endpoint reçoit un `guild_id` explicite). Ce
module reste donc volontairement mono-serveur : `SERVER = "alpha"` en dur.
Une vraie API notations multi-serveurs nécessiterait de faire évoluer le
contrat externe (ajouter un identifiant de serveur à chaque endpoint) —
hors périmètre de cette phase, à traiter avec la généralisation de
`/ngstaff` (§13 du prompt, phase 12).
"""
from __future__ import annotations

import asyncio
import logging
import time

from utils.db.models.ng_nota_config import NGNotaConfig
from utils.db.session import get_session
from utils.managers.ng_server_manager import get_server_by_name

log = logging.getLogger(__name__)

# Refonte multi-serveurs phase 9 : voir docstring du module.
SERVER = "alpha"

# Durée de vie du cache avant qu'un refresh soit considéré comme "périmé".
CACHE_TTL_SECONDS = 60

# ──────────────────────────────────────────────────────────────────────────
# État du cache (module-level, partagé dans le process)
# ──────────────────────────────────────────────────────────────────────────
_cache: dict | None = None
_cache_loaded_at: float = 0.0          # time.monotonic() du dernier refresh OK
_cache_ready: bool = False             # True dès qu'un refresh a réussi une fois
_refresh_lock = asyncio.Lock()         # évite deux refresh concurrents


def _with_guild_id(result: dict) -> dict:
    """Ajoute 'guild_id' au résultat pour compat avec le contrat externe du
    site (qui n'a aucune notion de 'server'), résolu depuis ng_servers."""
    ng_server = get_server_by_name(SERVER)
    result = dict(result)
    result["guild_id"] = ng_server.discord_guild_id if ng_server is not None else None
    return result


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
                row = await session.get(NGNotaConfig, SERVER)
        except Exception:
            log.exception("Refresh cache notations échoué — on garde l'ancien cache")
            return

        _cache = _with_guild_id(row.to_dict()) if row is not None else None
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
        row = await session.get(NGNotaConfig, SERVER)
    return _with_guild_id(row.to_dict()) if row is not None else None


# ══════════════════════════════════════════════════════════════════════════
# ✍️ ÉCRITURES ASYNC — appelées par l'API ; invalident le cache ensuite
# ══════════════════════════════════════════════════════════════════════════

async def update_full_config(data: dict) -> dict:
    """Met à jour la config complète des notations (toujours server='alpha')."""
    async with get_session() as session:
        row = await session.get(NGNotaConfig, SERVER)
        if row is None:
            # Créer une nouvelle config
            row = NGNotaConfig(server=SERVER)
        else:
            # Mettre à jour les champs existants
            for key, value in data.items():
                if key not in ("guild_id", "id_guild_notations", "server") and hasattr(row, key):
                    setattr(row, key, value)

        session.add(row)
        await session.flush()
        result = row.to_dict()

    await refresh_cache()
    log.info("Config notations mise à jour complète (server=%s)", SERVER)
    return _with_guild_id(result)


async def update_partial(partial: dict) -> dict:
    """Met à jour partiellement la config des notations (toujours server='alpha')."""
    async with get_session() as session:
        row = await session.get(NGNotaConfig, SERVER)
        if row is None:
            raise ValueError(
                "Aucune config notations en DB — utilisez update_full_config() d'abord."
            )
        for key, value in partial.items():
            if key not in ("guild_id", "id_guild_notations", "server") and hasattr(row, key):
                setattr(row, key, value)

        await session.flush()
        result = row.to_dict()

    await refresh_cache()
    log.info("Config notations mise à jour partielle : %s", list(partial.keys()))
    return _with_guild_id(result)
