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

        # Appel du stub DB
        incrementer_commande(
            nom_commande=nom_commande,
            user_id=user_id,
            guild_id=guild_id,
        )

    except Exception as e:
        # Le tracker NE DOIT JAMAIS bloquer une commande
        # On log simplement l'erreur pour debug
        print(f"[TRACKER] Erreur lors du tracking de '{nom_commande}' : {e}")

    return True