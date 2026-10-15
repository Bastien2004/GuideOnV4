"""
cogs/config/auto_fil.py — Configure le système "Auto-fil".
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

from views.auto_fil.auto_fil_config_view import AutoFilConfigView

log = logging.getLogger(__name__)


# ============================================================
# 🧵 Commande : /config auto_fil
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="auto_fil", description="🧵 Configure la création automatique de fils")
async def auto_fil(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Verrouillage Admin Discord.
    if not await check_admin(interaction, "configurer l'**Auto-fil**"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "config_auto_fil"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "config_auto_fil")

    # 💻 Envoi de l'interface.
    try:
        view = await AutoFilConfigView.create(guild=interaction.guild, moderator_id=interaction.user.id)
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception("[CONFIG AUTO_FIL] Ouverture de l'interface échouée guild=%s", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'ouvrir la configuration du système : **Auto-fil**."), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@auto_fil.error
async def auto_fil_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
