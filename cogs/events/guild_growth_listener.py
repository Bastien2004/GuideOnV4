"""
cogs/events/guild_growth_listener.py — Capture les ajouts/retraits du bot
sur des serveurs Discord (table bot_guild_events, via guild_growth_manager).
Pas de commande ici, juste les listeners — même principe que
guild_stats_listener.py.
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from utils.managers import guild_growth_manager

log = logging.getLogger(__name__)


class GuildGrowthListener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        try:
            await guild_growth_manager.record_join(guild.id, guild.name, guild.member_count)
        except Exception as e:
            log.warning("[growth] Échec enregistrement join guild=%s : %s", guild.id, e)
            return
        log.info("[growth] +1 serveur : %s (%s)", guild.name, guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        try:
            await guild_growth_manager.record_leave(guild.id, guild.name, guild.member_count)
        except Exception as e:
            log.warning("[growth] Échec enregistrement leave guild=%s : %s", guild.id, e)
            return
        log.info("[growth] -1 serveur : %s (%s)", guild.name, guild.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(GuildGrowthListener(bot))