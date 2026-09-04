"""
cogs/medialink/medialink_scheduler.py — Scheduler de polling des connexions MEDIALINK.
"""

from __future__ import annotations

import logging

from discord.ext import commands, tasks

from utils.medialink import scheduler

log = logging.getLogger(__name__)
POLL_INTERVAL_MINUTES = 5


class MediaLinkScheduler(commands.Cog):
    """Planificateur de polling des connexions MEDIALINK actives."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.poll_connections.start()

    async def cog_unload(self) -> None:
        self.poll_connections.cancel()

    @tasks.loop(minutes=POLL_INTERVAL_MINUTES)
    async def poll_connections(self) -> None:
        try:
            await scheduler.run_once(self.bot)
        except Exception:
            log.exception("[MEDIALINK] Passage de polling échoué")

    @poll_connections.before_loop
    async def _before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MediaLinkScheduler(bot))