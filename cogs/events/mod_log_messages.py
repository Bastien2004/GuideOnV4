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

MAX_PREVIEW_LENGTH = 1000


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

        attachments = len(message.attachments)
        fields = [
            ("Auteur", f"{message.author.mention} (`{message.author.id}`)", True),
            ("Salon", message.channel.mention, True),
            ("ID du message", f"`{message.id}`", True),
        ]
        if attachments:
            fields.append(("Pièces jointes", str(attachments), True))

        await send_log(
            message.guild.id, "message_delete", fields,
            description=_preview(message.content),
            thumbnail_url=message.author.display_avatar.url,
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if before.guild is None or before.author is None or before.author.bot:
            return
        if before.content == after.content:
            return

        fields = [
            ("Auteur", f"{before.author.mention} (`{before.author.id}`)", True),
            ("Salon", before.channel.mention, True),
            ("Lien", f"[Aller au message]({after.jump_url})", True),
            ("Avant", _preview(before.content), False),
            ("Après", _preview(after.content), False),
        ]

        await send_log(
            before.guild.id, "message_edit", fields,
            thumbnail_url=before.author.display_avatar.url,
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

        pin_count = None
        try:
            pin_count = len(await channel.pins())
        except (discord.Forbidden, discord.HTTPException, AttributeError):
            pass

        fields = [("Salon", channel.mention, True), ("Par", actor, True)]
        if pin_count is not None:
            fields.append(("Messages épinglés", str(pin_count), True))

        await send_log(guild.id, "message_pin", fields)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModLogMessages(bot))