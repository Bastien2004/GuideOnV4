"""
cogs/eco/eco_config.py — Configure le système d'économie.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande
from utils.perm_admin import check_admin

from utils.error_handler import handle_app_command_error
from utils.container_universel import error_container
from views.eco.config_view import EcoConfigView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /eco config
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="config", description="💰 Configure le système d'économie")
async def eco_config(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification Administrateur.
    if not await check_admin(interaction, "configurer le système d'**économie**"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "eco_config"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "eco_config")

    # 🧩 Création et envoi de l'interface.
    try:
        view = await EcoConfigView.create(
            guild_id=interaction.guild.id,
            author_id=interaction.user.id,
            bot=interaction.client,
        )
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("[ECO_CONFIG] Ouverture de l'interface de configuration échouée (guild=%s)", interaction.guild.id)
        await interaction.followup.send(view=error_container("Impossible d'ouvrir l'interface de **configuration**."), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@eco_config.error
async def eco_config_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)