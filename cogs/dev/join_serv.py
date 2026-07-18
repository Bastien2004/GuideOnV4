"""
cogs/dev/join_serv.py — Crée une invitation Discord sur un serveur où le bot est présent.
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.perm_dev import check_dev

from utils.join_serv import JoinServError, create_server_invite
from views.dev.join_serv_view import build_invite_view

# ============================================================
# 🧭 Commande : /dev join_serv
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="join_serv", description="🔗 [DEV] Crée une invitation sur un serveur")
@app_commands.describe(id_serveur="ID du serveur cible")
async def join_serv(interaction: Interaction, id_serveur: str) -> None:

    # 🔐 Vérification des permissions.
    if not await check_dev(interaction, "**créer une invitation** sur un serveur"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_join_serv"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_join_serv")

    # 🔎 Vérification de l'ID.
    try:
        guild_id = int(id_serveur)
    except ValueError:
        return await interaction.followup.send(
            view=error_container("`id_serveur` doit être un **identifiant numérique**."), ephemeral=True)

    guild = interaction.client.get_guild(guild_id)
    if guild is None:
        return await interaction.followup.send(
            view=error_container("GuideOn n'est présent sur **aucun serveur** avec cet ID."), ephemeral=True)

    # 🚀 Création de l'invitation.
    try:
        invite, channel = await create_server_invite(guild, interaction.user)
    except JoinServError as e:
        return await interaction.followup.send(view=error_container(e.message), ephemeral=True)

    # ✉️ Envoi de l'invitation.
    await interaction.followup.send(view=build_invite_view(guild, invite, channel), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@join_serv.error
async def join_serv_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)