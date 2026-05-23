"""
Commande /ticket wakeup — Permet de relancer un ticket inactif.
"""

"""
cogs/ticket/ticket_wakeup.py — /ticket wakeup

Relance le créateur du ticket (staff uniquement, cooldown 1h par staff).
Délègue à lifecycle.handle_wakeup, partagé avec le bouton « Relancer ».
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


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="wakeup", description="🔔 Relancer le créateur du ticket")
async def ticket_wakeup(interaction: discord.Interaction) -> None:
    if not await verifier_ban_utilisateur(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    if not await verifier_commande(interaction, "ticket_wakeup"):
        return
    await tracker_commande(interaction, "ticket_wakeup")

    # handle_wakeup gère toutes les vérifs (ticket, staff, cooldown 1h) + relance.
    await handle_wakeup(interaction, interaction.channel.id)


@ticket_wakeup.error
async def ticket_wakeup_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)