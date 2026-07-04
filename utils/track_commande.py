"""
utils/track_commande.py — Tracking d'utilisation des commandes.

Délègue à utils.gestion_stats.incrementer_commande, qui incrémente le
compteur quotidien (table command_stats_daily, voir
utils.managers.command_stats_manager).
"""

from __future__ import annotations

import logging

import discord

from utils.gestion_stats import incrementer_commande

log = logging.getLogger(__name__)


async def tracker_commande(
    interaction: discord.Interaction,
    nom_commande: str,
) -> bool:
    """
    Tracking universel des commandes GuideON V4.

    À insérer après la vérification maintenance dans chaque commande.
    Ne bloque jamais l'exécution (retourne toujours True).

    ⚠️ IMPORTANT :
    - interaction.guild peut être None dans certains contextes.
    - interaction.guild_id, lui, est TOUJOURS disponible.
    """

    try:
        user_id = interaction.user.id
        guild_id = interaction.guild_id  # Toujours fiable, même si interaction.guild est None

        await incrementer_commande(
            nom_commande=nom_commande,
            user_id=user_id,
            guild_id=guild_id,
        )

    except Exception:
        # Le tracker NE DOIT JAMAIS bloquer une commande
        # On log simplement l'erreur pour debug
        log.warning("Échec du tracking de la commande '%s'", nom_commande, exc_info=True)

    return True