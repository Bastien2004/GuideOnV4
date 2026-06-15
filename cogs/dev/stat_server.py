"""
cogs/dev/stat_server.py — Affiche les statistiques du bot GuideOn
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error
from utils.perm_dev import check_dev

from views.dev.stat_server_view import build_stat_server_view


# ============================================================
# 📁 Constantes
# ============================================================

log = logging.getLogger(__name__)

GUILDS_PER_PAGE = 10


# ============================================================
# 🧭 Commande principale : /dev stat_server
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="stat_server", description="📊 [DEV] Affiche les statistiques de GuideOn")
async def stat_server(interaction: Interaction) -> None:

    # 🔐 Vérification des permissions.
    if not await check_dev(interaction, "consulter les statistiques serveurs"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_stat_server"):
        return
    
    # 📊 Tracking.
    await tracker_commande(interaction, "dev_stat_server")

    # ✉️ Envoi de l'interface de statistique.
    await interaction.followup.send(view=build_stat_server_view(interaction.client, page=0), ephemeral=True)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@stat_server.error
async def stat_server_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)