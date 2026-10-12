"""
cogs/rappel/rappel_liste.py — Liste les rappels en attente.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.managers.reminder_manager import get_reminders_for_user
from utils.track_commande import tracker_commande

from views.rappel.liste_view import build_liste_view

log = logging.getLogger(__name__)


# ============================================================
# 📋 Commande : /rappel liste
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="list", description="📋 Liste tes rappels en attente")
async def rappel_list(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "rappel_list"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "rappel_list")

    try:
        reminders = await get_reminders_for_user(interaction.user.id)
        view = build_liste_view(interaction.user, reminders)
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("[RAPPEL LISTE] Échec d'affichage (user=%s)", interaction.user.id)
        await interaction.followup.send(
            view=error_container("Impossible d'afficher tes **rappels**."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@rappel_list.error
async def rappel_list_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)