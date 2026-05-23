"""
Commande /ticket unban — Permet debannir un utilisateur d'un panel de ticket.
"""

"""
cogs/ticket/ticket_unban.py — /ticket unban

Lève le ban tickets d'un utilisateur en retirant le rôle de ban du panel
(staff uniquement). Symétrique de /ticket ban.
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
@app_commands.command(name="unban", description="♻️ Lever le ban tickets d'un utilisateur")
@app_commands.describe(utilisateur="Utilisateur à débannir des tickets")
async def ticket_unban(interaction: discord.Interaction, utilisateur: discord.Member) -> None:
    if not await verifier_ban_utilisateur(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    if not await verifier_commande(interaction, "ticket_unban"):
        return

    guild_id = interaction.guild_id
    ticket = await tm.get_ticket(interaction.channel.id)
    if not ticket:
        return await interaction.followup.send(
            view=error_container("Ce salon n'est pas un ticket."), ephemeral=True
        )

    panel = await tm.get_panel(guild_id, ticket.get("panel_id", ""))
    if not panel:
        return await interaction.followup.send(
            view=error_container("Configuration du panel introuvable."), ephemeral=True
        )
    if not await is_staff(interaction, ticket, guild_id):
        return await interaction.followup.send(
            view=error_container("Vous n'avez pas la permission de débannir des tickets."),
            ephemeral=True,
        )

    await tracker_commande(interaction, "ticket_unban")

    ban_role_id = panel.get("role_ban_ticket_id")
    if not ban_role_id:
        return await interaction.followup.send(
            view=error_container("Aucun rôle de ban n'est configuré pour ce panel."),
            ephemeral=True,
        )
    ban_role = interaction.guild.get_role(int(ban_role_id))
    if not ban_role:
        return await interaction.followup.send(
            view=error_container("Le rôle de ban configuré est introuvable sur le serveur."),
            ephemeral=True,
        )
    if ban_role not in utilisateur.roles:
        return await interaction.followup.send(
            view=error_container("Cet utilisateur n'est pas banni des tickets."),
            ephemeral=True,
        )

    try:
        await utilisateur.remove_roles(
            ban_role, reason=f"Unban ticket par {interaction.user} (ID: {interaction.user.id})"
        )
        await interaction.followup.send(
            view=success_container(f"Le ban tickets de {utilisateur.mention} a été levé."),
            ephemeral=True,
        )
    except discord.Forbidden:
        await interaction.followup.send(
            view=error_container("Je n'ai pas les permissions pour retirer ce rôle."),
            ephemeral=True,
        )
    except discord.HTTPException as e:
        await interaction.followup.send(
            view=error_container(f"Une erreur est survenue : `{e}`"), ephemeral=True
        )


@ticket_unban.error
async def ticket_unban_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)