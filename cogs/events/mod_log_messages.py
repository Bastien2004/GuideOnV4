"""
cogs/events/mod_log_messages.py — Gestion des logs messages (delete/edit/pin/unpin).
"""

from __future__ import annotations

import asyncio
import datetime
import logging

import discord
from discord.ext import commands

from utils.managers.mod_log_manager import send_log

log = logging.getLogger(__name__)


# ============================================================
# 🔩 Paramètres
# ============================================================

MAX_PREVIEW_LENGTH = 1000
_AUDIT_LOOKUP_ATTEMPTS = 3
_AUDIT_LOOKUP_DELAY = 0.6


# ============================================================
# ⚒️ Fonctions utilitaires
# ============================================================

async def _resolve_pin_action(guild: discord.Guild, channel: discord.abc.GuildChannel) -> tuple[str, str]:
    """Détermine s'il s'agit d'un épinglage ou d'un désépinglage."""

    if guild.me is None or not guild.me.guild_permissions.view_audit_log:
        return "message_pin", "Un membre"

    for attempt in range(_AUDIT_LOOKUP_ATTEMPTS):
        best_entry = None
        best_is_pin = True
        try:
            for action, is_pin in (
                (discord.AuditLogAction.message_pin, True),
                (discord.AuditLogAction.message_unpin, False),
            ):
                async for entry in guild.audit_logs(limit=5, action=action):
                    entry_channel = getattr(entry.extra, "channel", None)
                    if entry_channel is None or entry_channel.id != channel.id:
                        continue
                    if best_entry is None or entry.created_at > best_entry.created_at:
                        best_entry, best_is_pin = entry, is_pin
                    break

        except discord.Forbidden:
            return "message_pin", "Un membre"
        
        except discord.HTTPException:
            log.debug("[MODLOG] Log indisponible pour l'épinglage (guild=%s)", guild.id)
            return "message_pin", "Un membre"

        if best_entry is not None:
            event_key = "message_pin" if best_is_pin else "message_unpin"
            actor = best_entry.user.mention if best_entry.user else "Un membre"
            return event_key, actor

        if attempt < _AUDIT_LOOKUP_ATTEMPTS - 1:
            await asyncio.sleep(_AUDIT_LOOKUP_DELAY)

    return "message_pin", "Un membre"


def _preview(content: str | None) -> str:
    content = (content or "").strip()
    if not content:
        return "*(contenu vide ou média)*"
    if len(content) > MAX_PREVIEW_LENGTH:
        return content[:MAX_PREVIEW_LENGTH] + "…"
    return content


# ============================================================
# 🖥️ Logs des messages (delete/edit/pin/unpin ...)
# ============================================================

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

        event_key, actor = await _resolve_pin_action(guild, channel)

        pin_count = None
        try:
            pin_count = len(await channel.pins())
        except (discord.Forbidden, discord.HTTPException, AttributeError):
            pass

        fields = [("Salon", channel.mention, True), ("Par", actor, True)]
        if pin_count is not None:
            fields.append(("Messages épinglés", str(pin_count), True))

        await send_log(guild.id, event_key, fields)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModLogMessages(bot))