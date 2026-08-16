"""
utils/ng_check_discord.py — Vérification du lieu d'exécution des commandes NationsGlory.
"""

from __future__ import annotations

from discord import Interaction

from utils.container_universel import error_container, send_ephemeral
from utils.managers.ng_server_manager import get_server_by_guild


# ============================================================
# 📁 Fonctions
# ============================================================

async def require_alpha_guild(interaction: Interaction) -> bool:
    """Protège les commandes /alpha exécutée hors serveur Alpha."""

    guild_id = interaction.guild_id
    server = get_server_by_guild(guild_id) if guild_id is not None else None

    if server is None or server.name != "alpha":
        await send_ephemeral(interaction, error_container("Cette commande est **réservée** au Discord Alpha."))
        return False
    
    return True


async def require_delta_guild(interaction: Interaction) -> bool:
    """Protège les commandes /delta exécutée hors serveur Delta."""

    guild_id = interaction.guild_id
    server = get_server_by_guild(guild_id) if guild_id is not None else None

    if server is None or server.name != "delta":
        await send_ephemeral(interaction, error_container("Cette commande est **réservée** au Discord Delta."))
        return False
    
    return True