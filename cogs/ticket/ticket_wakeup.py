"""
Commande /ticket wakeup — Permet de relancer un ticket inactif.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.error_handler import handle_app_command_error
from views.ticket.lifecycle import handle_wakeup

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande principale : /ticket wakeup
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="wakeup", description="🔔 Relancer le créateur du ticket")
async def ticket_wakeup(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return
    
    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ticket_wakeup"):
        return
    
    # 📊 Tracking.
    await tracker_commande(interaction, "ticket_wakeup")

    # 🧩 Gestion du wake-Up
    await handle_wakeup(interaction, interaction.channel.id)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@ticket_wakeup.error
async def ticket_wakeup_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)