"""
cogs/events/auto_fil_listener.py — Création automatique d'un fil sous chaque message.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from utils.managers.auto_fil_manager import is_auto_fil_channel

log = logging.getLogger(__name__)

_THREADABLE_TYPES = (discord.MessageType.default, discord.MessageType.reply)


# ============================================================
#  🧩 Class principale
# ============================================================

class AutoFilListener(commands.Cog):
    """Cog de création automatique de fils."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        if message.type not in _THREADABLE_TYPES:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return

        try:
            if not await is_auto_fil_channel(message.channel.id):
                return
        except Exception:
            log.exception("[AUTO_FIL_LISTENER] Échec vérification config guild=%s channel=%s", message.guild.id, message.channel.id)
            return

        try:
            await message.create_thread(
                name=f"Fil de {message.author.display_name}"[:100],
                reason="Auto-fil",
            )

        except discord.Forbidden:
            log.warning(
                "[AUTO_FIL] Permissions insuffisantes pour créer un fil guild=%s channel=%s",
                message.guild.id, message.channel.id,
            )

        except discord.HTTPException:
            log.exception(
                "[AUTO_FIL] Erreur Discord lors de la création du fil guild=%s channel=%s",
                message.guild.id, message.channel.id,
            )


# ============================================================
# 🚀 Setup
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoFilListener(bot))