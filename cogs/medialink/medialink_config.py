"""
cogs/medialink/medialink_config.py — Dashboard de configuration des annonces MEDIALINK.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.perm_admin import check_admin
from utils.track_commande import tracker_commande

from views.medialink.medialink_dashboard_view import MediaLinkDashboardView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /medialink config
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="config", description="📡 Configure les annonces MEDIALINK du serveur")
async def medialink_config(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Permission admin
    if not await check_admin(interaction, "configurer **MEDIALINK** du serveur"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "medialink_config"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "medialink_config")

    # 💻 Envoi du dashboard.
    try:
        view = await MediaLinkDashboardView.build(guild=interaction.guild, owner_id=interaction.user.id)
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("[MEDIALINK CONFIG] Ouverture dashboard échouée guild=%s", interaction.guild.id)
        await interaction.followup.send(view=error_container("Impossible d'ouvrir le **dashboard MEDIALINK**."), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@medialink_config.error
async def medialink_config_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)