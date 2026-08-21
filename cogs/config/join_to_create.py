"""
cogs/config/join_to_create.py — Configure le système "Join to Create".
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
from utils.perm_admin import check_admin

from views.join_to_create.join_to_create_config_view import JoinToCreateConfigView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /config join_to_create
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="join_to_create", description="🔊 Configure le système join to create")
async def join_to_create(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Verrouillage Admin Discord.
    if not await check_admin(interaction, "configurer le **Join to Create**"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "config_join_to_create"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "config_join_to_create")

    # 💻 Envoi de l'interface.
    try:
        view = await JoinToCreateConfigView.create(guild=interaction.guild, moderator_id=interaction.user.id)
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception("[CONFIG JOIN_TO_CREATE] Ouverture de l'interface échouée guild=%s", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'ouvrir la configuration du système : **Join to Create**."), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@join_to_create.error
async def join_to_create_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)