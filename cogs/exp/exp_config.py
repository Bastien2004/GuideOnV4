"""
cogs/exp/exp_config.py — Configure le système d'EXP.
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

from views.exp.config_view import ExpConfigView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /exp config
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 15)
@app_commands.command(name="config", description="🧮 Configure le système d'EXP")
async def exp_config(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification Administrateur.
    if not await check_admin(interaction, "configurer le système d'**EXP**"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "exp_config"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "exp_config")

    # 🧩 Création et envoi de l'interface.
    try:
        view = await ExpConfigView.create(
            guild_id=interaction.guild.id,
            author_id=interaction.user.id,
            bot=interaction.client,
        )
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("[EXP] Ouverture /exp config échouée (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'ouvrir l'interface de **configuration**."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@exp_config.error
async def exp_config_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)