"""
cogs/commande/report.py — Permet de signaler un problème sur le bot.
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error

from utils.managers.bug_report_manager import clear_draft
from views.report.config_view import home_view

log = logging.getLogger(__name__)


# ============================================================
# 👤 Commande principale : /report
# ============================================================

class Report(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 10)
    @app_commands.command(name="report", description="⚠️ Signaler un bug ou un problème")
    async def report_cmd(self, interaction: discord.Interaction) -> None:
        
        # 🛡️ Vérification ban utilisateur.
        if not await verifier_ban_utilisateur(interaction):
            return

        # ⚙️ Vérification maintenance.
        if not await verifier_commande(interaction, "report"):
            return

        # 📊 Tracking.
        await tracker_commande(interaction, "report")

        # 🪟 Ouverture de l'interface.
        clear_draft(interaction.user.id)
        try:
            await interaction.response.send_message(view=home_view(), ephemeral=True)
        except discord.HTTPException:
            log.exception("Ouverture /report échouée (user=%s)", interaction.user.id)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    view=error_container("**Impossible** d'ouvrir le formulaire de report."),
                    ephemeral=True,
                )

    # ============================================================
    # ❌ Gestion des erreurs
    # ============================================================

    @report_cmd.error
    async def report_cmd_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        await handle_app_command_error(interaction, error)


# ============================================================
# 🚀 Setup du Cog
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Report(bot))