"""
utils/managers/onu_manager.py — Manager API pour NGONUConfig / NGONUPingMember.

Utilisé par les routes /onu/* de cogs/api/api_app.py. Séparé du manager
Discord (ng_onu_manager.py) qui a son propre cache TTL indépendant sur le
même modèle.

Refonte multi-serveurs phase 8 : le contrat externe de l'API (URLs et
payloads JSON) reste inchangé — le site continue d'envoyer/recevoir des
`guild_id`, il n'a aucune notion de `server` (nom NGServer). Ce module fait
donc la résolution guild_id -> server via ng_server_manager avant d'opérer
sur NGONUConfig/NGONUPingMember (clés par `server`). Si le guild_id ne
correspond à aucun serveur NG connu du cache, on lève/renvoie la même
absence de résultat que si aucune config n'existait — le site voit un 404
ou une ValueError comme avant, sans avoir à changer son intégration.
"""
from __future__ import annotations

import logging
from sqlalchemy import delete, select

from utils.db.session import get_session
from utils.db.models.ng_onu_config import NGONUConfig, NGONUPingMember
from utils.managers.ng_server_manager import get_server_by_guild

log = logging.getLogger(__name__)


def _resolve_server(guild_id: int) -> str | None:
    """Résout un guild_id Discord vers un nom de serveur NG, ou None si inconnu."""
    ng_server = get_server_by_guild(guild_id)
    return ng_server.name if ng_server is not None else None


async def get_config(guild_id: int) -> dict | None:
    """Récupère la config ONU complète (avec ping_list)"""
    server = _resolve_server(guild_id)
    if server is None:
        return None

    async with get_session() as session:
        # Récupérer la config
        config = await session.get(NGONUConfig, server)
        if config is None:
            return None

        # Récupérer les pings
        pings_result = await session.execute(
            select(NGONUPingMember).where(NGONUPingMember.server == server)
        )
        pings = pings_result.scalars().all()

        # Convertir en dict
        result = config.to_dict()
        result['guild_id'] = guild_id
        result['ping_list'] = {str(p.discord_id): p.discord_id for p in pings}

    return result


async def update_full_config(data: dict) -> dict:
    """Met à jour la config complète"""
    guild_id = int(data["guild_id"])
    server = _resolve_server(guild_id)
    if server is None:
        raise ValueError(f"Aucun serveur NG connu pour guild_id={guild_id}")

    ping_list = data.pop("ping_list", {})

    async with get_session() as session:
        # Récupérer ou créer la config
        config = await session.get(NGONUConfig, server)

        if config is None:
            # Créer une nouvelle config
            config = NGONUConfig(server=server)

        # Mettre à jour les champs
        for key, value in data.items():
            if key not in ("guild_id", "server") and hasattr(config, key):
                # Les IDs Discord doivent rester en int
                setattr(config, key, value)

        session.add(config)

        # Supprimer les anciens pings et en ajouter de nouveaux
        await session.execute(
            delete(NGONUPingMember).where(NGONUPingMember.server == server)
        )

        for discord_id, name in ping_list.items():
            ping = NGONUPingMember(
                server=server,
                discord_id=int(discord_id)
            )
            session.add(ping)

        result = config.to_dict()
        result['guild_id'] = guild_id

        # Ajouter les pings au dict
        result['ping_list'] = ping_list

    log.info("Config ONU mise à jour complète (guild=%s, server=%s)", guild_id, server)
    return result


async def update_partial(guild_id: int, partial: dict) -> dict:
    """Mise à jour partielle (sans toucher ping_list)"""
    guild_id = int(guild_id)
    server = _resolve_server(guild_id)
    if server is None:
        raise ValueError(f"Aucun serveur NG connu pour guild_id={guild_id}")

    async with get_session() as session:
        config = await session.get(NGONUConfig, server)

        if config is None:
            raise ValueError(f"ONU config not found for guild {guild_id}")

        for key, value in partial.items():
            if key not in ("guild_id", "server", "ping_list") and hasattr(config, key):
                setattr(config, key, value)

        result = config.to_dict()
        result['guild_id'] = guild_id

    log.info("Config ONU mise à jour partielle (guild=%s, server=%s)", guild_id, server)
    return result


async def add_ping(guild_id: int, discord_id: int, name: str) -> dict:
    """Ajoute un utilisateur à la ping_list"""
    guild_id = int(guild_id)
    discord_id = int(discord_id)
    server = _resolve_server(guild_id)
    if server is None:
        raise ValueError(f"Aucun serveur NG connu pour guild_id={guild_id}")

    async with get_session() as session:
        config = await session.get(NGONUConfig, server)

        if config is None:
            raise ValueError(f"ONU config not found for guild {guild_id}")

        # Vérifier si le ping existe déjà
        existing = await session.scalar(
            select(NGONUPingMember).where(
                NGONUPingMember.server == server,
                NGONUPingMember.discord_id == discord_id
            )
        )

        if existing is None:
            ping = NGONUPingMember(server=server, discord_id=discord_id)
            session.add(ping)

        result = config.to_dict()
        result['guild_id'] = guild_id

    log.info("Ping ajouté: %s (%s)", name, discord_id)
    return result


async def remove_ping(guild_id: int, discord_id: int) -> dict:
    """Supprime un utilisateur de la ping_list"""
    guild_id = int(guild_id)
    discord_id = int(discord_id)
    server = _resolve_server(guild_id)
    if server is None:
        raise ValueError(f"Aucun serveur NG connu pour guild_id={guild_id}")

    async with get_session() as session:
        await session.execute(
            delete(NGONUPingMember).where(
                NGONUPingMember.server == server,
                NGONUPingMember.discord_id == discord_id
            )
        )

        config = await session.get(NGONUConfig, server)

        if config is None:
            raise ValueError(f"ONU config not found for guild {guild_id}")

        result = config.to_dict()
        result['guild_id'] = guild_id

    log.info("Ping supprimé: %s", discord_id)
    return result
