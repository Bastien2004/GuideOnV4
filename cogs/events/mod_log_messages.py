"""
cogs/events/mod_log_messages.py — Logs /mod : messages (pack Stagiaire) + épinglage (pack Espion).

commands.Cog avec setup() -> chargé automatiquement par _load_cogs_from_directory.
"""
from __future__ import annotations

import datetime
import logging

import discord
from discord.ext import commands

from utils.managers.mod_log_manager import send_log

log = logging.getLogger(__name__)

MAX_PREVIEW_LENGTH = 500


def _preview(content: str | None) -> str:
    content = (content or "").strip()
    if not content:
        return "*(contenu vide ou média)*"
    if len(content) > MAX_PREVIEW_LENGTH:
        return content[:MAX_PREVIEW_LENGTH] + "…"
    return content


class ModLogMessages(commands.Cog):
    """Logs des messages supprimés/modifiés et des (dés)épinglages."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.guild is None or message.author is None or message.author.bot:
            return

        await send_log(
            message.guild.id, "message_delete",
            [
                f"**Auteur :** {message.author.mention}",
                f"**Salon :** {message.channel.mention}",
                f"**Contenu :** {_preview(message.content)}",
            ],
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if before.guild is None or before.author is None or before.author.bot:
            return
        if before.content == after.content:
            return

        await send_log(
            before.guild.id, "message_edit",
            [
                f"**Auteur :** {before.author.mention}",
                f"**Salon :** {before.channel.mention}",
                f"**Avant :** {_preview(before.content)}",
                f"**Après :** {_preview(after.content)}",
                f"-# [Aller au message]({after.jump_url})",
            ],
        )

    @commands.Cog.listener()
    async def on_guild_channel_pins_update(
        self, channel: discord.abc.GuildChannel, last_pin: datetime.datetime | None,
    ) -> None:
        guild = channel.guild
        if guild is None:
            return

        actor = "Un membre"
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.message_pin):
                actor = entry.user.mention if entry.user else actor
                break
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            log.debug("[MOD_LOG] Impossible de consulter l'audit-log pour l'épinglage (guild=%s)", guild.id)

        await send_log(
            guild.id, "message_pin",
            [f"**Salon :** {channel.mention}", f"**Par :** {actor}"],
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModLogMessages(bot))