"""
cogs/birthday/birthday_config.py — Permet de configurer le système d'anniversaire du serveur.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.error_handler import handle_app_command_error
from utils.perm_admin import check_admin
from utils.container_universel import error_container

from views.birthday.config_view import BirthdayConfigView

log = logging.getLogger(__name__)


# ============================================================
# 🎁 Commande : /birthday config
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="config", description="🎂 Configure le système d'anniversaires",)
async def birthday_config(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification Administrateur.
    if not await check_admin(interaction, "configurer le système d'**anniversaires**"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "birthday_config"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "birthday_config")

    # 🧩 Création et envoi.
    try:
        view = await BirthdayConfigView.create(
            guild_id=interaction.guild.id,
            author_id=interaction.user.id,
            bot=interaction.client,
        )
        await interaction.followup.send(view=view, ephemeral=True)

    except Exception:
        log.exception("[BIRTHDAY] Ouverture de la configuration échouée (guild=%s)", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'ouvrir la **configuration**."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@birthday_config.error
async def birthday_config_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)