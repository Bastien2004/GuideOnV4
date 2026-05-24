"""
Commande /ticket delete — Permet de supprimer un ticket fermer (transcript automatique).
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande
from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.managers import ticket_manager as tm
from views.ticket._helpers import is_staff
from views.ticket.lifecycle import DeleteConfirmView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande principale : /ticket delete
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="delete", description="🗑️ Supprimer définitivement ce ticket")
async def ticket_delete(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return
    
    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ticket_delete"):
        return
    
    # 📦 Récupération des données.
    channel = interaction.channel
    ticket = await tm.get_ticket(channel.id)

    # 🔎 Vérification que le salon soit bien un ticket.
    if not ticket:
        return await interaction.followup.send(
            view=error_container("Vous n'êtes pas dans un **ticket**."), ephemeral=True
        )
    
    # ⛔ Vérification des permissions.
    if not await is_staff(interaction, ticket, interaction.guild_id):
        return await interaction.followup.send(
            view=error_container("Vous n'avez pas la **permission** de __supprimer ce ticket__."),
            ephemeral=True,
        )
    
    # 🔒 Vérification que le ticket soit fermé.
    if not ticket.get("closed"):
        return await interaction.followup.send(
            view=error_container("**Fermez d'abord** le ticket avec `/ticket close` avant de le **supprimer**."),
            ephemeral=True,
        )

    # 📊 Tracking.
    await tracker_commande(interaction, "ticket_delete")

    # 🗑️ Confirmation de suppression (gestion de la suppression, du transcript et du compteur.
    await interaction.followup.send(view=DeleteConfirmView(channel.id), ephemeral=True)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@ticket_delete.error
async def ticket_delete_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)