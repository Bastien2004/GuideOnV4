"""
utils/ng_server_check.py — Protection Discord NG pour les commandes /ngstaff.
"""

from __future__ import annotations

import discord

from utils.container_universel import error_container, send_ephemeral
from utils.db.models.ng_server import NGServer
from utils.managers.ng_server_manager import get_server_by_guild

__all__ = ["require_ng_server"]


async def require_ng_server(interaction: discord.Interaction) -> NGServer | None:
    """Résout le serveur NG associé à l'interaction."""

    guild_id = interaction.guild_id
    server = get_server_by_guild(guild_id) if guild_id is not None else None
    if server is None:
        await send_ephemeral(
            interaction,
            error_container(
                "Cette commande n'est disponible que sur les **Discord NationsGlory**."
            ),
        )
        return None
    return server