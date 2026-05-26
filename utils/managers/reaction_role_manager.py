"""
utils/managers/reaction_role_manager.py — CRUD du système de rôle-réaction.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import discord
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from utils.boutique.gold_manager import is_gold
from utils.db.models.reaction_role import ReactionRoleCouple, ReactionRoleMessage
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

LIMITE_MESSAGES_DEFAUT = 2
LIMITE_MESSAGES_GOLD = 5
LIMITE_COUPLES_DEFAUT = 2
LIMITE_COUPLES_GOLD = 3

_cache: dict[int, tuple[dict[str, dict], float]] = {}
_lock = asyncio.Lock()


def _invalidate(guild_id: int) -> None:
    _cache.pop(guild_id, None)


async def _load_guild_messages(guild_id: int) -> dict[str, dict]:
    """Charge tous les messages RR d'une guilde → {message_id(str): dict}."""

    async with get_session() as session:
        rows = (
            await session.execute(
                select(ReactionRoleMessage)
                .where(ReactionRoleMessage.guild_id == guild_id)
                .options(selectinload(ReactionRoleMessage.couples))
            )
        ).scalars().all()
    return {str(m.message_id): m.to_dict() for m in rows}


async def _get_guild_messages_cached(guild_id: int) -> dict[str, dict]:
    """Retourne les messages RR d'une guilde avec cache."""

    now = time.monotonic()
    cached = _cache.get(guild_id)
    if cached is not None and (now - cached[1]) < CACHE_TTL_SECONDS:
        return cached[0]
    msgs = await _load_guild_messages(guild_id)
    _cache[guild_id] = (msgs, now)
    return msgs


# ======================================================
# ================== LIMITES & QUOTAS ==================
# ======================================================

def obtenir_limite_messages(guild_id: int) -> int:
    """Nombre maximum de messages autorisés."""
    return LIMITE_MESSAGES_GOLD if is_gold(guild_id) else LIMITE_MESSAGES_DEFAUT


def obtenir_limite_couples(guild_id: int) -> int:
    """Nombre maximum de couples emoji/rôle par message."""
    return LIMITE_COUPLES_GOLD if is_gold(guild_id) else LIMITE_COUPLES_DEFAUT


async def peut_creer_message(guild_id: int) -> tuple[bool, str]:
    """Vérifie si on peut créer un nouveau message de rôle-réaction."""
    messages = await _get_guild_messages_cached(guild_id)
    limite = obtenir_limite_messages(guild_id)
    if len(messages) >= limite:
        return False, f"Limite atteinte ({len(messages)}/{limite} messages)"
    return True, "OK"


# ======================================================
# ================== CRUD MESSAGES =====================
# ======================================================

async def creer_message_reaction(
    guild_id: int,
    channel_id: int,
    message_id: int,
    description: str,
    reactions: list[dict[str, Any]],
) -> None:
    """Enregistre un nouveau message rôle-réaction + ses couples."""
    async with _lock:
        async with get_session() as session:
            msg = ReactionRoleMessage(
                message_id=message_id,
                guild_id=guild_id,
                channel_id=channel_id,
                description=description,
            )
            seen = set()
            for r in reactions:
                emoji = r.get("emoji")
                role_id = r.get("role_id")
                if not emoji or not role_id or emoji in seen:
                    continue
                seen.add(emoji)
                msg.couples.append(ReactionRoleCouple(emoji=emoji, role_id=int(role_id)))
            session.add(msg)
            await session.flush()
        _invalidate(guild_id)
    log.info("[Rôle-Réaction] Message rôle-réaction créé : guild=%s message=%s", guild_id, message_id)


async def supprimer_message_reaction(guild_id: int, message_id: int) -> None:
    """Supprime un message rôle-réaction."""
    
    async with _lock:
        async with get_session() as session:
            await session.execute(
                delete(ReactionRoleMessage).where(
                    ReactionRoleMessage.message_id == message_id,
                    ReactionRoleMessage.guild_id == guild_id,
                )
            )
        _invalidate(guild_id)


async def obtenir_message_reaction(guild_id: int, message_id: int) -> Optional[dict]:
    """Infos d'un message rôle-réaction, ou None."""
    messages = await _get_guild_messages_cached(guild_id)
    return messages.get(str(message_id))


async def obtenir_tous_messages(guild_id: int) -> dict[str, dict]:
    """Tous les messages rôle-réaction d'un serveur."""
    return await _get_guild_messages_cached(guild_id)


# ======================================================
# ============== LOOKUP EMOJI → RÔLE ===================
# ======================================================

async def obtenir_role_par_message_emoji(guild_id: int, message_id: int, emoji: str) -> Optional[int]:
    """Retourne le role_id associé à un emoji sur un message."""

    messages = await _get_guild_messages_cached(guild_id)
    data = messages.get(str(message_id))
    if not data:
        return None
    for r in data.get("reactions", []):
        if r["emoji"] == emoji:
            return r["role_id"]
    return None


# ======================================================
# ================== NETTOYAGE =========================
# ======================================================

async def nettoyer_messages_supprimes(guild_id: int, bot) -> int:
    """Supprime de la DB les messages qui n'existent plus sur Discord."""

    messages = await _get_guild_messages_cached(guild_id)
    supprimes = 0

    for message_id, data in list(messages.items()):
        channel = bot.get_channel(data.get("channel_id"))
        if not channel:
            await supprimer_message_reaction(guild_id, int(message_id))
            supprimes += 1
            continue
        try:
            await channel.fetch_message(int(message_id))
        except discord.NotFound:
            await supprimer_message_reaction(guild_id, int(message_id))
            supprimes += 1
        except discord.HTTPException:
            pass

    if supprimes:
        _invalidate(guild_id)
    return supprimes