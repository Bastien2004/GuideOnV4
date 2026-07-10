"""
cogs/alpha/config_alpha.py — Gestion de configuration des systèmes Alpha.
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.createur import is_creator

from views.alpha.config_dashboard_view import ConfigDashboardView


# ============================================================
# 🧭 Commande : /alpha config_alpha
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(name="config_alpha", description="⚙️ [ALPHA] Dashboard configuration systèmes Alpha")
async def config_alpha(interaction: Interaction) -> None:

    # 🔐 Vérification des permissions.
    if not is_creator(interaction.user.id):
        return await interaction.response.send_message(view=error_container("Cette commande est __réservée__ aux **développeurs**."), ephemeral=True)

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "alpha_config_alpha"):
        return
    
    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_config_alpha")

    # 🚀 Envoi du dashboard.
    view = ConfigDashboardView(guild_id=interaction.guild_id, owner_id=interaction.user.id)
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@config_alpha.error
async def config_alpha_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)