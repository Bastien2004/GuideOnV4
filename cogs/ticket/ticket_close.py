"""
Commande /ticket close — Permet de fermer un ticket existant.
"""

"""
cogs/ticket/ticket_close.py — /ticket close

Ferme le ticket courant (staff uniquement). Délègue à lifecycle.handle_close,
partagé avec le bouton « Fermer » du message d'accueil.
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


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="close", description="🔒 Fermer ce ticket")
async def ticket_close(interaction: discord.Interaction) -> None:
    if not await verifier_ban_utilisateur(interaction):
        return
    # 🕒 Defer avant verifier_commande (canon V4) ; handle_close ne re-defer pas.
    await interaction.response.defer(ephemeral=True)
    if not await verifier_commande(interaction, "ticket_close"):
        return
    await tracker_commande(interaction, "ticket_close")

    # handle_close gère toutes les vérifs (ticket, déjà fermé, cooldown,
    # permission staff) puis exécute la fermeture.
    await handle_close(interaction, interaction.channel.id, staff_only=True)


@ticket_close.error
async def ticket_close_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)