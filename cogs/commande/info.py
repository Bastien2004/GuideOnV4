"""
cogs/commande/info.py — Envoi la présentation du bot GuideON.
"""

from __future__ import annotations

import logging

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.track_commande import tracker_commande

from views.info.info_view import build_info_view

log = logging.getLogger(__name__)


# ============================================================
# 👤 Commande principale : /info
# ============================================================

class Info(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 15)
    @app_commands.command(name="info", description="❔ Découvre GuideOn Bot")
    async def info(self, interaction: Interaction) -> None:

        # 🛡️ Vérification ban utilisateur.
        if not await verifier_ban_utilisateur(interaction):
            return

        # 🕒 Defer.
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return

        # ⚙️ Vérification maintenance.
        if not await verifier_commande(interaction, "info_cmd"):
            return

        # 📊 Tracking.
        await tracker_commande(interaction, "info_cmd")

        # 🚀 Envoi.
        await interaction.followup.send(view=build_info_view())

    # ============================================================
    # 📨 Message automatique à l'arrivée sur un nouveau serveur
    # ============================================================

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        view = build_info_view()

        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                try:
                    await channel.send(view=view)
                    log.info("[Info GuideOn] Message de présentation envoyé dans #%s (%s)", channel.name, guild.name)
                    return
                except discord.HTTPException as e:
                    log.warning("[Info GuideOn] Échec envoi présentation dans #%s : %s", channel.name, e)

        log.warning("[Info GuideOn] Aucun salon disponible pour envoyer la présentation sur %s", guild.name)

    # ============================================================
    # ❌ Gestion erreurs
    # ============================================================

    @info.error
    async def info_error(self, interaction: Interaction, error: app_commands.AppCommandError) -> None:
        await handle_app_command_error(interaction, error)


# ============================================================
# 🔌 Setup
# ============================================================
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Info(bot))