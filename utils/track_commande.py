"""
utils/track_commande.py — Tracking d'utilisation des commandes.

🟡 STUB : délègue à utils.gestion_stats (lui-même stub).
À FAIRE par le collègue (DB) : remplir utils/gestion_stats.py.
"""
from __future__ import annotations

import discord

from utils.gestion_stats import incrementer_commande


async def tracker_commande(
    interaction: discord.Interaction,
    nom_commande: str,
) -> bool:
    """
    À insérer après la vérif de maintenance dans chaque commande.
    Toujours True (ne bloque jamais).
    """
    incrementer_commande(
        nom_commande=nom_commande,
        user_id=interaction.user.id,
        guild_id=interaction.guild.id if interaction.guild else None,
    )
    return True