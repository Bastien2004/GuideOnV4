"""
Commande /ticket delete — Permet de supprimer un ticket fermer (transcript automatique).
"""

"""
cogs/ticket/ticket_delete.py — /ticket delete

Supprime définitivement le ticket courant (staff uniquement). Le ticket doit
d'abord être fermé. Confirmation via DeleteConfirmView (partagée avec le bouton
Supprimer de l'état fermé) → génère le transcript puis supprime le salon.
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


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="delete", description="🗑️ Supprimer définitivement ce ticket")
async def ticket_delete(interaction: discord.Interaction) -> None:
    if not await verifier_ban_utilisateur(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    if not await verifier_commande(interaction, "ticket_delete"):
        return

    channel = interaction.channel
    ticket = await tm.get_ticket(channel.id)
    if not ticket:
        return await interaction.followup.send(
            view=error_container("Ce salon n'est pas un ticket."), ephemeral=True
        )
    if not await is_staff(interaction, ticket, interaction.guild_id):
        return await interaction.followup.send(
            view=error_container("Vous n'avez pas la permission de supprimer ce ticket."),
            ephemeral=True,
        )
    if not ticket.get("closed"):
        return await interaction.followup.send(
            view=error_container(
                "Fermez d'abord le ticket avec `/ticket close` avant de le supprimer."
            ),
            ephemeral=True,
        )

    await tracker_commande(interaction, "ticket_delete")

    # Confirmation : DeleteConfirmView gère la génération du transcript + delete.
    await interaction.followup.send(view=DeleteConfirmView(channel.id), ephemeral=True)


@ticket_delete.error
async def ticket_delete_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)