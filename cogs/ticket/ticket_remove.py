"""
Commande /ticket remove — Permet de retirer un utilisateur d'un ticket existant.
"""

"""
cogs/ticket/ticket_remove.py — /ticket remove

Retire un utilisateur de ce ticket (staff uniquement).
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande
from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error
from utils.managers import ticket_manager as tm
from views.ticket._helpers import is_staff

log = logging.getLogger(__name__)


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="remove", description="👤 Retirer un utilisateur de ce ticket")
@app_commands.describe(utilisateur="Utilisateur à retirer du ticket")
async def ticket_remove(interaction: discord.Interaction, utilisateur: discord.Member) -> None:
    if not await verifier_ban_utilisateur(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    if not await verifier_commande(interaction, "ticket_remove"):
        return

    channel = interaction.channel
    ticket = await tm.get_ticket(channel.id)
    if not ticket:
        return await interaction.followup.send(
            view=error_container("Ce salon n'est pas un ticket."), ephemeral=True
        )
    if not await is_staff(interaction, ticket, interaction.guild_id):
        return await interaction.followup.send(
            view=error_container("Vous n'avez pas la permission de retirer un membre de ce ticket."),
            ephemeral=True,
        )
    if not channel.permissions_for(utilisateur).view_channel:
        return await interaction.followup.send(
            view=error_container(f"{utilisateur.display_name} n'est pas présent dans ce ticket."),
            ephemeral=True,
        )
    # Empêche de retirer le créateur du ticket
    if utilisateur.id == ticket.get("creator_id"):
        return await interaction.followup.send(
            view=error_container("Impossible de retirer le créateur du ticket."),
            ephemeral=True,
        )

    await tracker_commande(interaction, "ticket_remove")

    try:
        await channel.set_permissions(
            utilisateur, overwrite=None,
            reason=f"Retrait du ticket par {interaction.user} (ID: {interaction.user.id})",
        )
        await interaction.followup.send(
            view=success_container(f"{utilisateur.mention} a été retiré du ticket."),
            ephemeral=True,
        )
    except discord.Forbidden:
        await interaction.followup.send(
            view=error_container("Je n'ai pas les permissions pour modifier les accès de ce salon."),
            ephemeral=True,
        )
    except discord.HTTPException as e:
        await interaction.followup.send(
            view=error_container(f"Une erreur est survenue lors du retrait : `{e}`"),
            ephemeral=True,
        )


@ticket_remove.error
async def ticket_remove_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)