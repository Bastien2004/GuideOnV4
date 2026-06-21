"""
utils/managers/onu_manager.py — Gestion ONU Config V4
"""
from __future__ import annotations

import logging
from sqlalchemy import select

from utils.db.engine import get_session
from utils.db.models.onu import ONUConfig, ONUPing

log = logging.getLogger(__name__)


async def get_config(guild_id: int) -> dict | None:
    """Récupère la config ONU complète (avec ping_list)"""
    async with get_session() as session:
        row = await session.get(ONUConfig, guild_id)
    return row.to_dict() if row is not None else None


async def update_full_config(data: dict) -> dict:
    """
    Mise à jour complète de la config ONU.

    Attendu:
    {
        "guild_id": int,
        "jour_onu": int,
        "pre_annonce": {"heure": int, "minute": int},
        "annonce": {"heure": int, "minute": int},
        "timezone": str,
        "ping_mp": bool,
        "ping_list": {"discord_id": "name", ...},
        "role_id": int,
        "channel_id": int,
        "image_name": str
    }
    """
    guild_id = data["guild_id"]
    ping_list = data.pop("ping_list", {})

    async with get_session() as session:
        row = await session.get(ONUConfig, guild_id)
        if row is None:
            row = ONUConfig(id_guild=guild_id, **data)
            session.add(row)
        else:
            for key, value in data.items():
                if key != "guild_id":
                    setattr(row, key, value)

        # Remplace les pings
        row.pings = []
        for discord_id, name in ping_list.items():
            ping = ONUPing(guild_id=guild_id, discord_id=discord_id, name=name)
            row.pings.append(ping)

        await session.flush()
        result = row.to_dict()

    log.info("Config ONU mise à jour complète (guild=%s)", guild_id)
    return result


async def update_partial(guild_id: int, partial: dict) -> dict:
    """Mise à jour partielle (sans toucher ping_list)"""
    async with get_session() as session:
        row = await session.get(ONUConfig, guild_id)
        if row is None:
            raise ValueError(f"ONU config not found for guild {guild_id}")

        for key, value in partial.items():
            if key != "guild_id":
                setattr(row, key, value)

        await session.flush()
        result = row.to_dict()

    log.info("Config ONU mise à jour partielle (guild=%s)", guild_id)
    return result


async def add_ping(guild_id: int, discord_id: str, name: str) -> dict:
    """Ajoute un utilisateur à la ping_list"""
    async with get_session() as session:
        row = await session.get(ONUConfig, guild_id)
        if row is None:
            raise ValueError(f"ONU config not found for guild {guild_id}")

        # Évite les doublons
        existing = await session.scalar(
            select(ONUPing).where(
                ONUPing.guild_id == guild_id,
                ONUPing.discord_id == discord_id
            )
        )
        if existing is None:
            ping = ONUPing(guild_id=guild_id, discord_id=discord_id, name=name)
            session.add(ping)
            await session.flush()

        result = row.to_dict()

    log.info("Ping ajouté: %s (%s)", name, discord_id)
    return result


async def remove_ping(guild_id: int, discord_id: str) -> dict:
    """Supprime un utilisateur de la ping_list"""
    async with get_session() as session:
        row = await session.get(ONUConfig, guild_id)
        if row is None:
            raise ValueError(f"ONU config not found for guild {guild_id}")

        await session.execute(
            "DELETE FROM onu_ping WHERE guild_id = :guild_id AND discord_id = :discord_id",
            {"guild_id": guild_id, "discord_id": discord_id}
        )
        await session.flush()
        result = row.to_dict()

    log.info("Ping supprimé: %s", discord_id)
    return result