"""
utils/managers/onu_manager.py
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import delete, select

from utils.db.models.onu import OnuConfig, OnuPingEntry, ONU_SETTABLE_KEYS
from utils.db.session import get_session

log = logging.getLogger(__name__)

# Durée de vie du cache avant qu'un refresh soit considéré comme "périmé".
CACHE_TTL_SECONDS = 60

# ──────────────────────────────────────────────────────────────────────────
# État du cache (module-level, partagé dans le process)
#   _cache_config  -> dict brut de la config (None si pas encore chargée)
#   _cache_pings   -> dict {discord_id: name}
# ──────────────────────────────────────────────────────────────────────────
_cache_config: dict | None = None
_cache_pings: dict[str, str] = {}
_cache_loaded_at: float = 0.0          # time.monotonic() du dernier refresh OK
_cache_ready: bool = False             # True dès qu'un refresh a réussi une fois
_refresh_lock = asyncio.Lock()         # évite deux refresh concurrents


# ══════════════════════════════════════════════════════════════════════════
# 🔄 REFRESH (async) — remplit le cache depuis la DB
# ══════════════════════════════════════════════════════════════════════════

async def refresh_cache() -> None:
    """
    Recharge la config + la ping_list depuis la DB.
    """
    global _cache_config, _cache_pings, _cache_loaded_at, _cache_ready

    async with _refresh_lock:
        try:
            async with get_session() as session:
                config_row = await session.scalar(select(OnuConfig))
                ping_rows = (
                    await session.execute(
                        select(OnuPingEntry.discord_id, OnuPingEntry.name)
                    )
                ).all()
        except Exception:
            log.exception("Refresh cache ONU échoué — on garde l'ancien cache")
            return

        _cache_config = config_row.to_dict() if config_row is not None else None
        _cache_pings = {discord_id: name for discord_id, name in ping_rows}
        _cache_loaded_at = time.monotonic()
        _cache_ready = True


async def cache_refresher_loop(interval: int = CACHE_TTL_SECONDS) -> None:
    """
    Boucle de fond : refresh toutes les `interval` secondes.
    À lancer via bot.loop.create_task() dans setup_hook().
    """
    log.info("Démarrage de la boucle de refresh ONU (toutes les %ds)", interval)
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
    Renvoie None si pas de config ou si le cache n'est pas prêt.
    """
    if not _cache_ready:
        log.warning("get_config_sync() appelé avant que le cache ONU soit prêt → None")
        return None
    return _cache_config.copy() if _cache_config is not None else None


def get_ping_list_sync() -> dict[str, str]:
    """
    Renvoie une copie du dict {discord_id: name} depuis le cache.
    Ne fait JAMAIS d'I/O ni d'await.
    """
    if not _cache_ready:
        log.warning("get_ping_list_sync() appelé avant que le cache ONU soit prêt → {}")
        return {}
    return dict(_cache_pings)


# ══════════════════════════════════════════════════════════════════════════
# 📚 LECTURES ASYNC — tapent la DB directement (pour l'API)
# ══════════════════════════════════════════════════════════════════════════

async def get_config() -> dict | None:
    """
    Renvoie la config complète (+ ping_list) depuis la DB.
    Renvoie None si aucune config n'est enregistrée.
    """
    async with get_session() as session:
        config_row = await session.scalar(select(OnuConfig))
        if config_row is None:
            return None
        ping_rows = (
            await session.execute(
                select(OnuPingEntry.discord_id, OnuPingEntry.name)
            )
        ).all()

    result = config_row.to_dict()
    result["ping_list"] = {discord_id: name for discord_id, name in ping_rows}
    return result


# ══════════════════════════════════════════════════════════════════════════
# ✍️ ÉCRITURES ASYNC — appelées par l'API ; invalident le cache ensuite
# ══════════════════════════════════════════════════════════════════════════

async def update_full_config(data: dict) -> dict:
    """
    Écrase la config complète (upsert sur la PK guild_id).
    La ping_list n'est pas touchée par cette méthode.
    Renvoie la config telle qu'elle est en DB après écriture.
    Rafraîchit le cache après écriture.
    """
    guild_id = data["guild_id"]

    async with get_session() as session:
        row = await session.get(OnuConfig, guild_id)
        if row is None:
            row = OnuConfig(**data)
            session.add(row)
        else:
            for key, value in data.items():
                setattr(row, key, value)
        await session.flush()
        result = row.to_dict()

    await refresh_cache()
    log.info("Config ONU mise à jour complète (guild=%s)", guild_id)
    return result


async def update_partial(partial: dict) -> dict:
    """
    Met à jour uniquement les champs fournis dans `partial`.
    Seules les clés présentes dans ONU_SETTABLE_KEYS sont acceptées.
    La config doit déjà exister en DB (sinon lève ValueError).
    Rafraîchit le cache après écriture.
    """
    invalid = set(partial) - ONU_SETTABLE_KEYS
    if invalid:
        raise ValueError(f"Clés non autorisées : {invalid}")

    async with get_session() as session:
        row = await session.scalar(select(OnuConfig))
        if row is None:
            raise ValueError(
                "Aucune config ONU en DB — utilisez update_full_config() d'abord."
            )
        for key, value in partial.items():
            setattr(row, key, value)
        await session.flush()
        result = row.to_dict()

    await refresh_cache()
    log.info("Config ONU mise à jour partielle : %s", list(partial.keys()))
    return result


async def add_ping(discord_id: str, name: str) -> bool:
    """
    Ajoute ou met à jour un utilisateur dans la ping_list.
    Renvoie True si créé, False si mis à jour (déjà existant).
    Rafraîchit le cache après écriture.
    """
    async with get_session() as session:
        # Récupère le guild_id depuis la config existante
        config_row = await session.scalar(select(OnuConfig))
        if config_row is None:
            raise ValueError(
                "Aucune config ONU en DB — créez la config avant d'ajouter des pings."
            )
        guild_id = config_row.guild_id

        existing = await session.scalar(
            select(OnuPingEntry).where(
                OnuPingEntry.guild_id == guild_id,
                OnuPingEntry.discord_id == discord_id,
            )
        )
        if existing is None:
            session.add(OnuPingEntry(guild_id=guild_id, discord_id=discord_id, name=name))
            created = True
        else:
            existing.name = name
            created = False

    await refresh_cache()
    log.info("Ping ONU %s : discord_id=%s name=%s", "ajouté" if created else "mis à jour", discord_id, name)
    return created


async def remove_ping(discord_id: str) -> bool:
    """
    Retire un utilisateur de la ping_list.
    Renvoie True si supprimé, False si introuvable.
    Rafraîchit le cache après écriture.
    """
    async with get_session() as session:
        result = await session.execute(
            delete(OnuPingEntry).where(
                OnuPingEntry.discord_id == discord_id
            )
        )
        deleted = result.rowcount > 0

    if deleted:
        await refresh_cache()
        log.info("Ping ONU retiré : discord_id=%s", discord_id)
    return deleted