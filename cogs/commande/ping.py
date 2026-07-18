"""
cogs/commande/ping.py — Affiche la latence du bot.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.error_handler import handle_app_command_error

from utils.ping import get_latency_ms
from views.ping.ping_view import build_ping_view


# ============================================================
# 🏓 Commande principale : /ping
# ============================================================

class Ping(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 10)
    @app_commands.command(name="ping", description="🏓 Affiche la latence du bot")
    async def ping_command(self, interaction: discord.Interaction):

        # 🛡️ Vérification ban utilisateur.
        if not await verifier_ban_utilisateur(interaction):
            return

        # 🕒 Defer.
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return

        # ⚙️ Vérification maintenance.
        if not await verifier_commande(interaction, "ping_cmd"):
            return

        # 📊 Tracking.
        await tracker_commande(interaction, "ping_cmd")

        # 📡 Calcul latence.
        latency_ms = get_latency_ms(self.bot)

        # 🧩 Construction view.
        view = build_ping_view(latency_ms)

        # 🚀 Envoi.
        await interaction.followup.send(view=view, ephemeral=True)

    # ============================================================
    # ❌ Gestion des erreurs
    # ============================================================

    @ping_command.error
    async def ping_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await handle_app_command_error(interaction, error)


# ============================================================
# 🚀 Setup du Cog
# ============================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(Ping(bot))