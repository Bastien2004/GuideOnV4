"""
utils/managers/onu_manager.py — Gestion ONU Config V4 (CORRIGÉ)
"""
from __future__ import annotations

import logging
from sqlalchemy import delete, select

from utils.db.engine import get_session
from utils.db.models.alpha_onu_config import AlphaONUConfig, AlphaONUPingMember

log = logging.getLogger(__name__)


async def get_config(guild_id: int) -> dict | None:
    """Récupère la config ONU complète (avec ping_list)"""
    async with get_session() as session:
        # Récupérer la config
        config = await session.get(AlphaONUConfig, guild_id)
        if config is None:
            return None

        # Récupérer les pings
        pings_result = await session.execute(
            select(AlphaONUPingMember).where(AlphaONUPingMember.guild_id == guild_id)
        )
        pings = pings_result.scalars().all()

        # Convertir en dict
        result = config.to_dict()
        result['ping_list'] = {str(p.discord_id): p.discord_id for p in pings}

    return result


async def update_full_config(data: dict) -> dict:
    """Met à jour la config complète"""
    guild_id = int(data["guild_id"])
    ping_list = data.pop("ping_list", {})

    async with get_session() as session:
        # Récupérer ou créer la config
        config = await session.get(AlphaONUConfig, guild_id)

        if config is None:
            # Créer une nouvelle config
            config = AlphaONUConfig(guild_id=guild_id)

        # Mettre à jour les champs
        for key, value in data.items():
            if key != "guild_id" and hasattr(config, key):
                # Les IDs Discord doivent rester en int
                setattr(config, key, value)

        session.add(config)

        # Supprimer les anciens pings et en ajouter de nouveaux
        await session.execute(
            delete(AlphaONUPingMember).where(AlphaONUPingMember.guild_id == guild_id)
        )

        for discord_id, name in ping_list.items():
            ping = AlphaONUPingMember(
                guild_id=guild_id,
                discord_id=int(discord_id)
            )
            session.add(ping)

        await session.commit()
        result = config.to_dict()

        # Ajouter les pings au dict
        result['ping_list'] = ping_list

    log.info("Config ONU mise à jour complète (guild=%s)", guild_id)
    return result


async def update_partial(guild_id: int, partial: dict) -> dict:
    """Mise à jour partielle (sans toucher ping_list)"""
    guild_id = int(guild_id)

    async with get_session() as session:
        config = await session.get(AlphaONUConfig, guild_id)

        if config is None:
            raise ValueError(f"ONU config not found for guild {guild_id}")

        for key, value in partial.items():
            if key not in ("guild_id", "ping_list") and hasattr(config, key):
                setattr(config, key, value)

        await session.commit()
        result = config.to_dict()

    log.info("Config ONU mise à jour partielle (guild=%s)", guild_id)
    return result


async def add_ping(guild_id: int, discord_id: int, name: str) -> dict:
    """Ajoute un utilisateur à la ping_list"""
    guild_id = int(guild_id)
    discord_id = int(discord_id)

    async with get_session() as session:
        config = await session.get(AlphaONUConfig, guild_id)

        if config is None:
            raise ValueError(f"ONU config not found for guild {guild_id}")

        # Vérifier si le ping existe déjà
        existing = await session.scalar(
            select(AlphaONUPingMember).where(
                AlphaONUPingMember.guild_id == guild_id,
                AlphaONUPingMember.discord_id == discord_id
            )
        )

        if existing is None:
            ping = AlphaONUPingMember(guild_id=guild_id, discord_id=discord_id)
            session.add(ping)
            await session.commit()

        result = config.to_dict()

    log.info("Ping ajouté: %s (%s)", name, discord_id)
    return result


async def remove_ping(guild_id: int, discord_id: int) -> dict:
    """Supprime un utilisateur de la ping_list"""
    guild_id = int(guild_id)
    discord_id = int(discord_id)

    async with get_session() as session:
        await session.execute(
            delete(AlphaONUPingMember).where(
                AlphaONUPingMember.guild_id == guild_id,
                AlphaONUPingMember.discord_id == discord_id
            )
        )
        await session.commit()

        config = await session.get(AlphaONUConfig, guild_id)

        if config is None:
            raise ValueError(f"ONU config not found for guild {guild_id}")

        result = config.to_dict()

    log.info("Ping supprimé: %s", discord_id)
    return result