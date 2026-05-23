"""
Commande /ticket add — Permet d'ajouter un membre à un ticket existant.
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
@app_commands.command(name="add", description="👤 Ajouter un utilisateur à ce ticket")
@app_commands.describe(utilisateur="Utilisateur à ajouter au ticket")
async def ticket_add(interaction: discord.Interaction, utilisateur: discord.Member) -> None:
    if not await verifier_ban_utilisateur(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    if not await verifier_commande(interaction, "ticket_add"):
        return

    channel = interaction.channel
    ticket = await tm.get_ticket(channel.id)
    if not ticket:
        return await interaction.followup.send(
            view=error_container("Ce salon n'est pas un ticket."), ephemeral=True
        )
    if not await is_staff(interaction, ticket, interaction.guild_id):
        return await interaction.followup.send(
            view=error_container("Vous n'avez pas la permission d'ajouter un membre à ce ticket."),
            ephemeral=True,
        )
    if channel.permissions_for(utilisateur).view_channel:
        return await interaction.followup.send(
            view=error_container(f"{utilisateur.display_name} a déjà accès à ce ticket."),
            ephemeral=True,
        )

    await tracker_commande(interaction, "ticket_add")

    try:
        await channel.set_permissions(
            utilisateur,
            overwrite=discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                attach_files=True, embed_links=True,
            ),
            reason=f"Ajout au ticket par {interaction.user} (ID: {interaction.user.id})",
        )
        await interaction.followup.send(
            view=success_container(f"{utilisateur.mention} a été ajouté au ticket."),
            ephemeral=True,
        )
    except discord.Forbidden:
        await interaction.followup.send(
            view=error_container("Je n'ai pas les permissions pour modifier les accès de ce salon."),
            ephemeral=True,
        )
    except discord.HTTPException as e:
        await interaction.followup.send(
            view=error_container(f"Une erreur est survenue lors de l'ajout : `{e}`"),
            ephemeral=True,
        )


@ticket_add.error
async def ticket_add_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)