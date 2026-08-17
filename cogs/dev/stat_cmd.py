"""
cogs/dev/stat_cmd.py — Statistiques d'usage des commandes GuideOn.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error
from utils.perm_check import has_grade_check

from views.dev.stat_cmd_view import build_stat_cmd_view

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /dev stat_cmd
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="stat_cmd", description="📊 [DEV] Statistiques d'usage des commandes")
async def stat_cmd(interaction: Interaction) -> None:

    # 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "equipe_guideon.dev", "consulter les **statistiques** des commandes"):
        return
    
    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_stat_cmd"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_stat_cmd")

    # ✉️ Envoi du dashboard.
    view, graph_file = await build_stat_cmd_view(interaction.user.id, window_days=7, page=0)
    await interaction.followup.send(view=view, files=[graph_file], ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@stat_cmd.error
async def stat_cmd_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)