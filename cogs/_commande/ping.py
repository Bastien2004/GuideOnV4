"""
Commande /ping

Affiche la latence du bot. Sert aussi de health-check rapide.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.theme import Colors


class Ping(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ping",
        description="⏳ Affiche la latence du bot",
    )
    async def ping(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.bot.latency * 1000)

        # Code couleur selon la latence
        if latency_ms < 100:
            color = Colors.SUCCESS
            status = "Excellente"
        elif latency_ms < 250:
            color = Colors.WARNING
            status = "Correcte"
        else:
            color = Colors.DANGER
            status = "Dégradée"

        embed = discord.Embed(
            title="🏓 Pong !",
            description=f"**Latence :** `{latency_ms} ms`\n**Statut :** {status}",
            color=color,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ping(bot))