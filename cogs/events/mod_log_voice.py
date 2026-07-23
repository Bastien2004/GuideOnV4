"""
cogs/events/mod_log_voice.py — Logs /mod : connexions/déconnexions vocales (pack Chercheur).

commands.Cog avec setup() -> chargé automatiquement par _load_cogs_from_directory.
"""
from __future__ import annotations

import discord
from discord.ext import commands

from utils.managers.mod_log_manager import send_log


class ModLogVoice(commands.Cog):
    """Logs des connexions/déconnexions aux salons vocaux."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState,
    ) -> None:
        if before.channel is None and after.channel is not None:
            await send_log(
                member.guild.id, "voice_join",
                [
                    ("Membre", f"{member.mention} (`{member.id}`)", True),
                    ("Salon", after.channel.mention, True),
                    ("Membres présents", str(len(after.channel.members)), True),
                ],
                thumbnail_url=member.display_avatar.url,
            )
            return

        if before.channel is not None and after.channel is None:
            await send_log(
                member.guild.id, "voice_leave",
                [
                    ("Membre", f"{member.mention} (`{member.id}`)", True),
                    ("Salon", before.channel.mention, True),
                ],
                thumbnail_url=member.display_avatar.url,
            )
            return

        if before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
            await send_log(
                member.guild.id, "voice_leave",
                [
                    ("Membre", f"{member.mention} (`{member.id}`)", True),
                    ("Salon", before.channel.mention, True),
                ],
                thumbnail_url=member.display_avatar.url,
            )
            await send_log(
                member.guild.id, "voice_join",
                [
                    ("Membre", f"{member.mention} (`{member.id}`)", True),
                    ("Salon", after.channel.mention, True),
                    ("Membres présents", str(len(after.channel.members)), True),
                ],
                thumbnail_url=member.display_avatar.url,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModLogVoice(bot))