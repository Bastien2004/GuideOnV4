"""
Commande /ticket ban — Permet de bannir un membre d'un panel de ticket.
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
# 🧭 Commande principale : /ticket ban
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 15)
@app_commands.command(name="ban", description="🔨 Bannir un utilisateur des tickets")
@app_commands.describe(utilisateur="Utilisateur à bannir des tickets")
async def ticket_ban(interaction: discord.Interaction, utilisateur: discord.Member) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return
    
    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ticket_ban"):
        return

    # 📦 Récupération des données.
    guild_id = interaction.guild_id
    ticket = await tm.get_ticket(interaction.channel.id)

    # 🔎 Vérification que le salon soit bien un ticket.
    if not ticket:
        return await interaction.followup.send(
            view=error_container("Ce **salon** n'est __pas un ticket__."), ephemeral=True
        )

    # ⛔ Vérification des permissions.
    panel = await tm.get_panel(guild_id, ticket.get("panel_id", ""))
    if not panel:
        return await interaction.followup.send(
            view=error_container("**Configuration** du panel __introuvable__."), ephemeral=True
        )
    
    if not await is_staff(interaction, ticket, guild_id):
        return await interaction.followup.send(
            view=error_container("Vous n'avez pas la **permission** de __bannir des tickets__."),
            ephemeral=True,
        )

    # 📊 Tracking.
    await tracker_commande(interaction, "ticket_ban")

    # 🛡️ Protection contre le bannissement de staff.
    staff_ids = {int(r) for r in panel.get("staff_roles", [])}
    is_target_staff = any(r.id in staff_ids for r in utilisateur.roles)
    if is_target_staff or utilisateur.guild_permissions.administrator:
        return await interaction.followup.send(
            view=error_container("**Impossible** de bannir un __membre du staff__."), ephemeral=True
        )

    # 🔎 Vérification de l'existence d'un rôle de ban dans la configuration du panel.
    ban_role_id = panel.get("role_ban_ticket_id")
    if not ban_role_id:
        return await interaction.followup.send(
            view=error_container("Aucun __rôle de ban__ n'est **configuré** pour ce panel."),
            ephemeral=True,
        )
    
    # 🔎 Vérification que le rôle de ban existe sur le serveur.
    ban_role = interaction.guild.get_role(int(ban_role_id))
    if not ban_role:
        return await interaction.followup.send(
            view=error_container("Le __rôle de ban__ configuré est **introuvable** sur le serveur."),
            ephemeral=True,
        )
    
    # 🚫 Vérification que l'utilisateur n'est pas déjà banni.
    if ban_role in utilisateur.roles:
        return await interaction.followup.send(
            view=error_container("Cet __utilisateur__ est **déjà banni** des tickets."),
            ephemeral=True,
        )

    # 🔐 Ajout du rôle de ban à l'utilisateur.
    try:
        await utilisateur.add_roles(
            ban_role, reason=f"Ban ticket par {interaction.user} (ID: {interaction.user.id})"
        )
        await interaction.followup.send(
            view=success_container(f"{utilisateur.mention} a été **banni** des tickets."),
            ephemeral=True,
        )
    except discord.Forbidden:
        await interaction.followup.send(
            view=error_container("Je n'ai pas les **permissions** pour __ajouter ce rôle__."),
            ephemeral=True,
        )
    except discord.HTTPException as e:
        await interaction.followup.send(
            view=error_container(f"Une **erreur** est survenue : `{e}`"), ephemeral=True
        )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@ticket_ban.error
async def ticket_ban_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)