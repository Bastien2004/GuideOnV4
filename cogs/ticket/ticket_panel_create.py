"""
Commande /ticket panel_create — Permet de créer un panel de ticket.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.perm_admin import check_admin
from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error

from views.ticket.panel_setup_view import build_setup_view

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande principale : /ticket panel_create
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 15)
@app_commands.command(name="panel_create", description="🎫 Créer un nouveau panel de tickets")
async def ticket_panel_create(interaction: discord.Interaction) -> None:
    
    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🔐 Vérification administrateur.
    if not await check_admin(interaction, "**créer** un __panel de tickets__"):
        return
    
    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return
    
    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ticket_panel_create"):
        return
    
    # 📊 Tracking.
    await tracker_commande(interaction, "ticket_panel_create")


    # 🪟 Ouverture view de création
    try:
        ctx = {"channel_id": interaction.channel_id}
        view = build_setup_view(interaction.guild, ctx)
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("Ouverture de l'interface de création échouée (guild=%s)", interaction.guild_id)
        await interaction.followup.send(
            view=error_container("**Impossible** d'ouvrir l'__interface de création__."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@ticket_panel_create.error
async def ticket_panel_create_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)