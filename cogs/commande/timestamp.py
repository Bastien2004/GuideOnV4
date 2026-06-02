"""
Commande /timestamp — Convertit une date en timestamp Discord.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.track_commande import tracker_commande

from views.timestamp.timestamp_view import build_main_view

log = logging.getLogger(__name__)


# ============================================================
# ⏱️ Commande principale : /timestamp
# ============================================================

class Timestamp(commands.Cog):
    """Cog du convertisseur de date en timestamp Discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 10)
    @app_commands.command(
        name="timestamp",
        description="⏱️ Convertit une date en timestamp Discord",
    )
    async def timestamp_command(self, interaction: discord.Interaction) -> None:

        # 🛡️ Vérification ban utilisateur.
        if not await verifier_ban_utilisateur(interaction):
            return

        # 🕒 Defer.
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return

        # ⚙️ Vérification maintenance.
        if not await verifier_commande(interaction, "timestamp_command"):
            return

        # 📊 Tracking.
        await tracker_commande(interaction, "timestamp_command")

        # 🧩 Construction et envoi de la vue.
        try:
            view = build_main_view()
            await interaction.followup.send(view=view, ephemeral=True)
        except Exception:
            log.exception("Ouverture /timestamp échouée (user=%s)", interaction.user.id)
            await interaction.followup.send(
                view=error_container("Impossible d'ouvrir le **convertisseur**."),
                ephemeral=True,
            )

    # ============================================================
    # ❌ Gestion des erreurs
    # ============================================================

    @timestamp_command.error
    async def timestamp_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError,
    ) -> None:
        await handle_app_command_error(interaction, error)


# ============================================================
# 🚀 Setup du Cog
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Timestamp(bot))