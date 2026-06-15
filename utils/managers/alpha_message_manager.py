"""
utils/managers/alpha_message_manager.py — CRUD messages persistants Alpha.

Gère la persistance des message_id des messages Alpha (index, nous_rejoindre…)
afin de pouvoir les éditer plutôt que d'en recréer un nouveau à chaque fois.

API publique :
    await get_alpha_message(guild_id, key) -> AlphaMessageConfig | None
    await upsert_alpha_message(guild_id, key, channel_id, message_id) -> AlphaMessageConfig
    await clear_alpha_message(guild_id, key) -> bool
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from utils.db.models.alpha import AlphaMessageConfig
from utils.db.session import get_session

log = logging.getLogger(__name__)


async def get_alpha_message(guild_id: int, key: str) -> AlphaMessageConfig | None:
    """Retourne la config du message persistant ou None si absente."""
    async with get_session() as session:
        return await session.get(AlphaMessageConfig, {"guild_id": guild_id, "key": key})


async def upsert_alpha_message(
    guild_id: int,
    key: str,
    channel_id: int,
    message_id: int | None,
) -> AlphaMessageConfig:
    """
    Crée ou met à jour le message persistant (guild_id, key).
    Retourne l'objet à jour.
    """
    async with get_session() as session:
        row = await session.get(AlphaMessageConfig, {"guild_id": guild_id, "key": key})
        if row is None:
            row = AlphaMessageConfig(
                guild_id=guild_id,
                key=key,
                channel_id=channel_id,
                message_id=message_id,
            )
            session.add(row)
        else:
            row.channel_id = channel_id
            row.message_id = message_id
    log.debug("upsert_alpha_message guild=%d key=%r msg=%s", guild_id, key, message_id)
    return row


async def clear_alpha_message(guild_id: int, key: str) -> bool:
    """
    Remet message_id à None (le message a été supprimé côté Discord).
    Retourne True si la ligne existait.
    """
    async with get_session() as session:
        row = await session.get(AlphaMessageConfig, {"guild_id": guild_id, "key": key})
        if row is None:
            return False
        row.message_id = None
    return True