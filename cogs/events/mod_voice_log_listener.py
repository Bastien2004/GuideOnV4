"""
cogs/events/mod_voice_log_listener.py — Gestion des logs en vocal (mise en muet, mise en sourdine, expulsion et move
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

_AUDIT_LOOKUP_ATTEMPTS = 3
_AUDIT_LOOKUP_DELAY = 0.6
_SINCE_SAFETY_MARGIN = datetime.timedelta(seconds=2)


# ============================================================
# 🧩 Listener
# ============================================================

class ModVoiceLogListener(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        guild = member.guild
        if guild is None or member.bot:
            return

        event_time = discord.utils.utcnow()

        try:
            if before.channel is not None and before.mute != after.mute:
                await self._log_mute(guild, member, muted=after.mute, since=event_time)

            if before.channel is not None and before.deaf != after.deaf:
                await self._log_deaf(guild, member, deafened=after.deaf, since=event_time)

            if (
                before.channel is not None
                and after.channel is not None
                and before.channel.id != after.channel.id
            ):
                await self._log_move(guild, member, before.channel, after.channel, since=event_time)

            if before.channel is not None and after.channel is None:
                await self._log_disconnect(guild, member, before.channel, since=event_time)

        except Exception:
            log.exception("[MODLOG VOICE] Erreur traitement voice_state_update guild=%s membre=%s", guild.id, member.id)


    async def _find_moderator(self, guild: discord.Guild, action: discord.AuditLogAction, *, match, since: datetime.datetime) -> discord.abc.User | None:
        """Récupère l'auteur de l'action de modération."""

        if guild.me is None or not guild.me.guild_permissions.view_audit_log:
            return None

        threshold = since - _SINCE_SAFETY_MARGIN

        for attempt in range(_AUDIT_LOOKUP_ATTEMPTS):
            try:
                async for entry in guild.audit_logs(action=action, limit=5):
                    if entry.created_at < threshold:
                        break

                    if match(entry):
                        return entry.user
                    
            except (discord.Forbidden, discord.HTTPException) as exc:
                log.warning("[MODLOG VOICE] Lecture audit log impossible guild=%s erreur=%s",
                    guild.id, exc,
                )
                return None
            
            if attempt < _AUDIT_LOOKUP_ATTEMPTS - 1:
                await asyncio.sleep(_AUDIT_LOOKUP_DELAY)
        return None

    def _is_own_bot(self, user: discord.abc.User) -> bool:
        """Bypass du bot."""
        return self.bot.user is not None and user.id == self.bot.user.id

    # ============================================================
    # 🗣️ MUTE VOCAL
    # ============================================================

    async def _log_mute(self, guild: discord.Guild, member: discord.Member, *, muted: bool, since: datetime.datetime) -> None:

        moderator = await self._find_moderator(
            guild, discord.AuditLogAction.member_update,
            match=lambda e: (
                e.target is not None
                and e.target.id == member.id
                and getattr(e.after, "mute", None) == muted
            ),
            since=since,
        )
        if moderator is not None and self._is_own_bot(moderator):
            return

        moderator_display = moderator.mention if moderator else "`Modérateur inconnu`"
        action_label = "Rendu muet" if muted else "Muet retiré"

        fields = [
            ("Modérateur", moderator_display, True),
            ("Membre", member.mention, True),
            ("Action", action_label, True),
        ]
        if member.voice is not None and member.voice.channel is not None:
            fields.append(("Salon vocal", member.voice.channel.mention, False))

        await send_log(
            guild.id, "voice_mute", fields,
            thumbnail_url=member.display_avatar.url,
        )

    # ============================================================
    # 🎧 SOURDINE VOCAL
    # ============================================================

    async def _log_deaf(self, guild: discord.Guild, member: discord.Member, *, deafened: bool, since: datetime.datetime) -> None:

        moderator = await self._find_moderator(
            guild, discord.AuditLogAction.member_update,
            match=lambda e: (
                e.target is not None
                and e.target.id == member.id
                and getattr(e.after, "deaf", None) == deafened
            ),
            since=since,
        )
        if moderator is not None and self._is_own_bot(moderator):
            return

        moderator_display = moderator.mention if moderator else "`Modérateur inconnu`"
        action_label = "Mise en sourdine" if deafened else "Sourdine retirée"

        fields = [
            ("Modérateur", moderator_display, True),
            ("Membre", member.mention, True),
            ("Action", action_label, True),
        ]
        if member.voice is not None and member.voice.channel is not None:
            fields.append(("Salon vocal", member.voice.channel.mention, False))

        await send_log(
            guild.id, "voice_deaf", fields,
            thumbnail_url=member.display_avatar.url,
        )

    # ============================================================
    # 🛫 MOVE VOCAL
    # ============================================================

    async def _log_move(self, guild: discord.Guild, member: discord.Member, before_channel: discord.abc.GuildChannel,
        after_channel: discord.abc.GuildChannel, *, since: datetime.datetime) -> None:

        moderator = await self._find_moderator(
            guild, discord.AuditLogAction.member_move,
            match=lambda e: (
                getattr(e.extra, "channel", None) is not None
                and e.extra.channel.id == after_channel.id
            ),
            since=since,
        )
        if moderator is None:
            return
        if self._is_own_bot(moderator):
            return

        fields = [
            ("Modérateur", moderator.mention, True),
            ("Membre", member.mention, True),
            ("Depuis", before_channel.mention, True),
            ("Vers", after_channel.mention, True),
        ]

        await send_log(
            guild.id, "voice_move", fields,
            thumbnail_url=member.display_avatar.url,
        )

    # ============================================================
    # 🛫 KICK VOCAL
    # ============================================================

    async def _log_disconnect(self, guild: discord.Guild, member: discord.Member,
        before_channel: discord.abc.GuildChannel, *, since: datetime.datetime) -> None:

        moderator = await self._find_moderator(
            guild, discord.AuditLogAction.member_disconnect,
            match=lambda e: True,
            since=since,
        )

        if moderator is None:
            return
        
        if self._is_own_bot(moderator):
            return

        fields = [
            ("Modérateur", moderator.mention, True),
            ("Membre", member.mention, True),
            ("Salon vocal", before_channel.mention, True),
        ]

        await send_log(
            guild.id, "voice_disconnect", fields,
            thumbnail_url=member.display_avatar.url,
        )


# ============================================================
# 🚀 Setup
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModVoiceLogListener(bot))