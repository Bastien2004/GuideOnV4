"""
utils/managers/bot_ban_manager.py — CRUD des bans globaux du bot.
Cache mémoire TTL 60s, invalidé à chaque écriture.

API publique :
    await is_banned(discord_id) -> tuple[bool, str]
        (True, raison) si banni et ban encore actif, sinon (False, "").
        Un ban expiré (expiration < maintenant) est traité comme absent.
    await get_ban_info(discord_id) -> dict | None
        Détail complet du ban actif, None si absent ou expiré.
    await ban_user(discord_id, raison, moderator_id, duree_jours) -> dict
        Crée ou remplace le ban (upsert). Retourne le ban créé.
    await unban_user(discord_id) -> bool
        Retire le ban. False si l'utilisateur n'était pas banni.
    await list_active_bans() -> list[dict]
        Tous les bans dont l'expiration n'est pas encore passée, triés par
        date d'expiration croissante (les plus proches de l'expiration en premier).
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta

from sqlalchemy import delete, select

from utils.datetime_utils import now_utc
from utils.db.models.bot_ban import BotBan
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

_cache: list[dict] | None = None
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


async def _load_from_db() -> list[dict]:
    async with get_session() as session:
        rows = (await session.execute(select(BotBan))).scalars().all()
    return [r.to_dict() for r in rows]


async def _get_cache() -> list[dict]:
    global _cache, _cache_at
    if _is_valid():
        return list(_cache)
    async with _lock:
        if _is_valid():
            return list(_cache)
        _cache = await _load_from_db()
        _cache_at = time.monotonic()
    return list(_cache)


def _is_active(ban: dict) -> bool:
    """Un ban est actif si son expiration n'est pas encore passée."""
    return ban["expiration"] > now_utc()


# ════════════════════════════════════════════════════════════
# 📖 Lectures
# ════════════════════════════════════════════════════════════

async def is_banned(discord_id: int) -> tuple[bool, str]:
    """(True, raison) si banni et le ban est encore actif, sinon (False, "")."""
    bans = await _get_cache()
    for b in bans:
        if b["discord_id"] == discord_id and _is_active(b):
            return True, b["raison"]
    return False, ""


async def get_ban_info(discord_id: int) -> dict | None:
    """Détail complet du ban actif, None si absent ou expiré."""
    bans = await _get_cache()
    for b in bans:
        if b["discord_id"] == discord_id and _is_active(b):
            return dict(b)
    return None


async def list_active_bans() -> list[dict]:
    """Tous les bans actifs, triés par expiration croissante."""
    bans = await _get_cache()
    active = [b for b in bans if _is_active(b)]
    return sorted(active, key=lambda b: b["expiration"])


# ════════════════════════════════════════════════════════════
# ✍️ Écritures
# ════════════════════════════════════════════════════════════

async def ban_user(discord_id: int, raison: str, moderator_id: int, duree_jours: int) -> dict:
    """
    Crée ou remplace (upsert) le ban d'un utilisateur.
    duree_jours : nombre entier de jours avant expiration (utiliser 9999
    pour un ban de facto permanent — aucune notion de ban "infini" en DB).
    """
    date_ban = now_utc()
    expiration = date_ban + timedelta(days=duree_jours)

    async with _lock:
        async with get_session() as session:
            row = await session.scalar(
                select(BotBan).where(BotBan.discord_id == discord_id)
            )
            if row is None:
                row = BotBan(
                    discord_id=discord_id,
                    raison=raison,
                    moderator_id=moderator_id,
                    date_ban=date_ban,
                    expiration=expiration,
                )
                session.add(row)
            else:
                row.raison = raison
                row.moderator_id = moderator_id
                row.date_ban = date_ban
                row.expiration = expiration
            await session.flush()
            result = row.to_dict()
        _invalidate()

    log.info(
        "[BOT_BAN] %s banni par %s pour %d jour(s) — raison: %s",
        discord_id, moderator_id, duree_jours, raison,
    )
    return result


async def unban_user(discord_id: int) -> bool:
    """Retire le ban d'un utilisateur. Retourne False s'il n'était pas banni."""
    async with _lock:
        async with get_session() as session:
            result = await session.execute(
                delete(BotBan).where(BotBan.discord_id == discord_id)
            )
            deleted = result.rowcount > 0
        if deleted:
            _invalidate()

    if deleted:
        log.info("[BOT_BAN] %s débanni", discord_id)
    return deleted