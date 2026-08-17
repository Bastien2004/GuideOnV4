"""
Commande /ticket unban — Permet debannir un utilisateur d'un panel de ticket.
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


# ============================================================
# 🧭 Commande principale : /ticket unban
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 15)
@app_commands.command(name="unban", description="♻️ Révoquer le ban tickets d'un utilisateur")
@app_commands.describe(utilisateur="Utilisateur à débannir des tickets")
async def ticket_unban(interaction: discord.Interaction, utilisateur: discord.Member) -> None:
    
    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return
    
    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ticket_unban"):
        return

    # 📦 Récupération des données.
    guild_id = interaction.guild_id
    ticket = await tm.get_ticket(interaction.channel.id)

    # 🔎 Vérification que le salon soit bien un ticket.
    if not ticket:
        return await interaction.followup.send(
            view=error_container("Vous n'êtes pas dans un **ticket**."), ephemeral=True
        )

    # ⛔ Vérification des permissions.
    panel = await tm.get_panel(guild_id, ticket.get("panel_id", ""))
    if not panel:
        return await interaction.followup.send(
            view=error_container("**Configuration** du panel __introuvable__."), ephemeral=True
        )
    
    if not await is_staff(interaction, ticket, guild_id):
        return await interaction.followup.send(
            view=error_container("Vous n'avez pas la **permission** de __débannir des tickets__."),
            ephemeral=True,
        )

    # 📊 Tracking.
    await tracker_commande(interaction, "ticket_unban")

    # 🔎 Vérification de l'existence d'un rôle de ban dans la configuration du panel.
    ban_role_id = panel.get("role_ban_ticket_id")
    if not ban_role_id:
        return await interaction.followup.send(
            view=error_container("Aucun **rôle de ban** n'est __configuré__ pour ce panel."),
            ephemeral=True,
        )
    
    # 🔎 Vérification que le rôle de ban existe sur le serveur.
    ban_role = interaction.guild.get_role(int(ban_role_id))
    if not ban_role:
        return await interaction.followup.send(
            view=error_container("Le **rôle de ban** configuré est __introuvable__ sur le serveur."),
            ephemeral=True,
        )
    
    # 🚫 Vérification que l'utilisateur est bien banni.
    if ban_role not in utilisateur.roles:
        return await interaction.followup.send(
            view=error_container("Cet **utilisateur** n'__est pas banni__ des tickets."),
            ephemeral=True,
        )

    # 🔐 Retrait du rôle de ban à l'utilisateur.
    try:
        await utilisateur.remove_roles(
            ban_role, reason=f"**Unban ticket** par {interaction.user} (ID: {interaction.user.id})"
        )
        await interaction.followup.send(
            view=success_container(f"Le __ban tickets__ de {utilisateur.mention} a été **levé**."),
            ephemeral=True,
        )
    except discord.Forbidden:
        await interaction.followup.send(
            view=error_container("Je n'ai pas les **permissions** pour __retirer ce rôle__."),
            ephemeral=True,
        )
    except discord.HTTPException as e:
        await interaction.followup.send(
            view=error_container(f"Une **erreur** est survenue : `{e}`"), ephemeral=True
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@ticket_unban.error
async def ticket_unban_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)