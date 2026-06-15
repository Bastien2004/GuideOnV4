"""
Commande /ticket close — Permet de fermer un ticket existant.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.error_handler import handle_app_command_error
from views.ticket.lifecycle import handle_close

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande principale : /ticket close
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="close", description="🔒 Fermer ce ticket")
async def ticket_close(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return
    
    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ticket_close"):
        return
    
    # 📊 Tracking.
    await tracker_commande(interaction, "ticket_close")

    # 🔒 Gestion de la fermeture (Vérification est un ticket, si déjà fermé, cooldown, permissions, fermeture, compteur ...)
    await handle_close(interaction, interaction.channel.id, staff_only=True)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@ticket_close.error
async def ticket_close_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)