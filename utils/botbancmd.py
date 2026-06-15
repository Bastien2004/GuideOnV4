"""
utils/botbancmd.py — Vérification du ban global du bot.
"""
from __future__ import annotations

import os
import discord
from datetime import datetime

from utils.gestion_ban import est_banni, obtenir_info_ban

IMAGE_PATH = os.path.join("source", "GuideOn_ban.png")


async def verifier_ban_utilisateur(interaction: discord.Interaction) -> bool:
    """Retourne False si l'utilisateur est banni du bot."""

    user_id = interaction.user.id
    banni, raison = est_banni(user_id)

    if not banni:
        return True

    ban_info = obtenir_info_ban(user_id)

    if not ban_info:
        return True

    embed = discord.Embed(
        title="<:sanctionner:1495444382587949086> **Accès refusé**",
        description="Tu es actuellement banni de l'utilisation de **GuideOn**.",
        color=discord.Color.red(),
    )
    embed.add_field(name="<:dialoguer:1495444451244511403> Raison", value=raison, inline=False)

    date_ban = ban_info.get("date_ban")
    if date_ban:
        date_obj = datetime.fromisoformat(date_ban)
        embed.add_field(
            name="<:info:1495443961144152094> Date du ban",
            value=f"<t:{int(date_obj.timestamp())}:F>",
            inline=True,
        )

    expiration = ban_info.get("expiration")
    if expiration:
        exp_date = datetime.fromisoformat(expiration)
        embed.add_field(
            name="<:notifier:1495444487206604833> Expiration",
            value=f"<t:{int(exp_date.timestamp())}:R>",
            inline=True,
        )
    else:
        embed.add_field(name="<:notifier:1495444487206604833> Durée", value="Permanent", inline=True)

    embed.set_footer(text="*Pour contester ce ban, contacte l'équipe de développement.*")

    if os.path.exists(IMAGE_PATH):
        file = discord.File(IMAGE_PATH, filename="erreur_GuideON.png")
        embed.set_image(url="attachment://erreur_GuideON.png")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

    return False