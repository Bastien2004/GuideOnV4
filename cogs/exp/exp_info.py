"""
cogs/exp/exp_info.py — Explique le système d'EXP et les paliers.
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
from utils.managers.exp_manager import load_exp_config

from views.exp.info_view import build_exp_info_view

log = logging.getLogger(__name__)


# ============================================================
# ℹ️ Commande : /exp info
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="info", description="ℹ️ Explique le système d'EXP et les paliers")
async def exp_info(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer()
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "exp_info"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "exp_info")

    # 🧩 Construction et envoi de l'interface.
    try:
        cfg = await load_exp_config(interaction.guild.id)
        view = build_exp_info_view(interaction.guild, cfg)
        await interaction.followup.send(view=view)

    except Exception:
        log.exception("[EXP INFO] Affichage de l'interface échoué (guild=%s)", interaction.guild.id)
        await interaction.followup.send(view=error_container("Impossible d'afficher les **informations** du système d'EXP."))


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@exp_info.error
async def exp_info_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
