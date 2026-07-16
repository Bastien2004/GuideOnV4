"""
cogs/birthday/birthday_add.py — Permet aux utilisateurs d'enregistrer leur date d'anniversaire.
"""

from __future__ import annotations

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error

from utils.birthday import BirthdayValidationError, register_birthday


# ============================================================
# 🎁 Commande : /birthday add
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 15)
@app_commands.command(name="add", description="🎂 Enregistre ta date d'anniversaire")
@app_commands.describe(date="Ta date d'anniversaire (JJ/MM ou JJ/MM/AAAA)")
async def birthday_add(interaction: discord.Interaction, date: str) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "birthday_add"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "birthday_add")

    # 🚫 Refus des bots (sécurité).
    if interaction.user.bot:
        return

    # 🚀 Traitement de la demande.
    try:
        result = await register_birthday(interaction.guild.id, interaction.user.id, date)
    except BirthdayValidationError as e:
        return await interaction.followup.send(view=error_container(e.message), ephemeral=True)

    await interaction.followup.send(
        view=success_container(f"Date d'anniversaire enregistrée : **{result.display}** 🎂"),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@birthday_add.error
async def birthday_add_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)