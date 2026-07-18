"""
cogs/commande/wiki.py — Affichage du wiki de GuideOn Bot.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.track_commande import tracker_commande
from views.wiki.wiki_view import WikiHomeView

log = logging.getLogger(__name__)


# ============================================================
# 👤 Commande principale : /wiki
# ============================================================

class Wiki(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5)
    @app_commands.command(name="wiki", description="📖 Consulte le wiki de GuideOn Bot")
    async def wiki(self, interaction: discord.Interaction) -> None:

        # 🛡️ Vérification ban.
        if not await verifier_ban_utilisateur(interaction):
            return

        # 🕒 Defer.
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return

        # ⚙️ Vérification maintenance.
        if not await verifier_commande(interaction, "wiki_cmd"):
            return

        # 📊 Tracking.
        await tracker_commande(interaction, "wiki_cmd")

        # 📖 Envoi du wiki.
        view = WikiHomeView(bot=self.bot, owner_id=interaction.user.id)
        await interaction.followup.send(view=view, ephemeral=True)


    # ============================================================
    # ❌ Gestion des erreurs
    # ============================================================

    @wiki.error
    async def wiki_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        await handle_app_command_error(interaction, error)


# ============================================================
# 🚀 Setup du Cog
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Wiki(bot))