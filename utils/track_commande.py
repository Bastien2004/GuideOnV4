"""
utils/track_commande.py — Tracking d'utilisation des commandes pour les statistiques.
"""

from __future__ import annotations

import logging
import discord

from utils.gestion_stats import incrementer_commande

log = logging.getLogger(__name__)


async def tracker_commande(interaction: discord.Interaction, nom_commande: str) -> bool:
    """Tracking des commandes utilisées."""

    try:
        user_id = interaction.user.id
        guild_id = interaction.guild_id

        await incrementer_commande(nom_commande=nom_commande, user_id=user_id, guild_id=guild_id)

    except Exception:
        log.warning("Échec du tracking de la commande '%s'", nom_commande, exc_info=True)

    return True