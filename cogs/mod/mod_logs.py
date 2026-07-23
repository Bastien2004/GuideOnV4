"""
cogs/mod/mod_logs.py — Configure le système de logs du serveur.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.perm_mod import check_mod_permission

from views.mod.logs_config_view import LogsConfigView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /mod logs
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="logs", description="📋 Configure le système de logs du serveur")
async def mod_logs(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification permission /mod.
    if not await check_mod_permission(interaction, "config_logs"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "config_logs"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "config_logs")

    # 💻 Envoi de l'interface.
    try:
        view = await LogsConfigView.create(guild=interaction.guild, moderator_id=interaction.user.id)
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception("[MOD_LOGS] Ouverture du panneau échouée (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'ouvrir la configuration des logs."), ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@mod_logs.error
async def mod_logs_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)