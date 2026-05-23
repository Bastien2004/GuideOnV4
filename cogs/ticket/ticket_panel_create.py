"""
Commande /ticket panel_create — Permet de créer un panel de ticket.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.perm_admin import check_admin
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande
from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from views.ticket.panel_setup_view import build_setup_view

log = logging.getLogger(__name__)


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="panel_create", description="🎫 Créer un nouveau panel de tickets")
async def ticket_panel_create(interaction: discord.Interaction) -> None:
    
    # 🔒 Ban bot
    if not await verifier_ban_utilisateur(interaction):
        return
    # 🔐 Administrateur
    if not await check_admin(interaction, "créer un **panel de tickets**"):
        return
    # 🕒 Defer
    await interaction.response.defer(ephemeral=True)
    # ⚙️ Maintenance
    if not await verifier_commande(interaction, "ticket_panel_create"):
        return
    # 📊 Tracking
    await tracker_commande(interaction, "ticket_panel_create")

    # 🪟 Wizard (ctx vide, salon courant comme cible d'envoi)
    try:
        ctx = {"channel_id": interaction.channel_id}
        view = build_setup_view(interaction.guild, ctx)
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception("Ouverture wizard panel_create échouée (guild=%s)", interaction.guild_id)
        await interaction.followup.send(
            view=error_container("Impossible d'ouvrir l'interface de création."),
            ephemeral=True,
        )


@ticket_panel_create.error
async def ticket_panel_create_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)