"""
utils/botbancmd.py — Vérification du ban global du bot.

Port direct V3. Délègue à utils.gestion_ban (stub à remplir par le collègue).
"""
from __future__ import annotations

import os
from datetime import datetime

import discord

from utils.gestion_ban import est_banni, obtenir_info_ban

IMAGE_PATH = os.path.join("source", "GuideOn_ban.png")


async def verifier_ban_utilisateur(interaction: discord.Interaction) -> bool:
    """
    Retourne True si l'user peut continuer, False s'il est ban (et affiche le message).
    """
    user_id = interaction.user.id
    banni, raison = est_banni(user_id)

    if not banni:
        return True

    ban_info = obtenir_info_ban(user_id)

    if not ban_info:
        return True

    embed = discord.Embed(
        title="🚫 **Accès refusé**",
        description="Tu es actuellement banni de l'utilisation de ce bot.",
        color=discord.Color.red(),
    )
    embed.add_field(name="📋 Raison", value=raison, inline=False)

    date_ban = ban_info.get("date_ban")
    if date_ban:
        date_obj = datetime.fromisoformat(date_ban)
        embed.add_field(
            name="📅 Date du ban",
            value=f"<t:{int(date_obj.timestamp())}:F>",
            inline=True,
        )

    expiration = ban_info.get("expiration")
    if expiration:
        exp_date = datetime.fromisoformat(expiration)
        embed.add_field(
            name="⏰ Expiration",
            value=f"<t:{int(exp_date.timestamp())}:R>",
            inline=True,
        )
    else:
        embed.add_field(name="⏰ Durée", value="Permanent", inline=True)

    embed.set_footer(text="Pour contester ce ban, contacte l'équipe de développement.")

    if os.path.exists(IMAGE_PATH):
        file = discord.File(IMAGE_PATH, filename="erreur_GuideON.png")
        embed.set_image(url="attachment://erreur_GuideON.png")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

    return False