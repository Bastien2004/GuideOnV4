"""
cogs/events/mod_log_guild.py — Logs /mod : salons, rôles, serveur, emojis/stickers.

commands.Cog avec setup() -> chargé automatiquement par _load_cogs_from_directory.
Lie également le bot au manager de logs (mod_log_manager.bind_bot), pour
que utils.managers.mod_sanction_manager/mod_rename_manager puissent
résoudre un guild_id en discord.Guild sans dépendre directement du client.
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from utils.managers.mod_log_manager import bind_bot, send_log

log = logging.getLogger(__name__)


class ModLogGuild(commands.Cog):
    """Logs des évènements liés aux salons, rôles, au serveur et aux emojis/stickers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bind_bot(bot)

    # ── Salons ──────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        await send_log(channel.guild.id, "channel_create", [f"**Salon :** {channel.mention} (`{channel.name}`)"])

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        await send_log(channel.guild.id, "channel_delete", [f"**Salon :** `#{channel.name}` (`{channel.id}`)"])

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> None:
        if before.name == after.name:
            return
        await send_log(
            after.guild.id, "channel_update",
            [f"**Salon :** {after.mention}", f"**Avant :** `#{before.name}`", f"**Après :** `#{after.name}`"],
        )

    # ── Rôles ───────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        await send_log(role.guild.id, "role_create", [f"**Rôle :** {role.mention} (`{role.name}`)"])

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        await send_log(role.guild.id, "role_delete", [f"**Rôle :** `{role.name}` (`{role.id}`)"])

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        if before.name == after.name:
            return
        await send_log(
            after.guild.id, "role_update",
            [f"**Rôle :** {after.mention}", f"**Avant :** `{before.name}`", f"**Après :** `{after.name}`"],
        )

    # ── Serveur ─────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        if before.name == after.name:
            return
        await send_log(
            after.id, "guild_update",
            ["**Nom du serveur**", f"**Avant :** `{before.name}`", f"**Après :** `{after.name}`"],
        )

    # ── Emojis / stickers (pack Espion) ─────────────────

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self, guild: discord.Guild, before: list[discord.Emoji], after: list[discord.Emoji],
    ) -> None:
        before_ids = {e.id: e for e in before}
        after_ids = {e.id: e for e in after}

        for emoji_id, emoji in after_ids.items():
            if emoji_id not in before_ids:
                await send_log(guild.id, "emoji_create", [f"**Emoji :** {emoji} `:{emoji.name}:`"])

        for emoji_id, emoji in before_ids.items():
            if emoji_id not in after_ids:
                await send_log(guild.id, "emoji_delete", [f"**Emoji :** `:{emoji.name}:`"])

        for emoji_id, emoji in after_ids.items():
            old = before_ids.get(emoji_id)
            if old is not None and old.name != emoji.name:
                await send_log(
                    guild.id, "emoji_update",
                    [f"**Avant :** `:{old.name}:`", f"**Après :** `:{emoji.name}:`"],
                )

    @commands.Cog.listener()
    async def on_guild_stickers_update(
        self, guild: discord.Guild, before: list[discord.GuildSticker], after: list[discord.GuildSticker],
    ) -> None:
        before_ids = {s.id: s for s in before}
        after_ids = {s.id: s for s in after}

        for sticker_id, sticker in after_ids.items():
            if sticker_id not in before_ids:
                await send_log(guild.id, "sticker_create", [f"**Sticker :** `{sticker.name}`"])

        for sticker_id, sticker in before_ids.items():
            if sticker_id not in after_ids:
                await send_log(guild.id, "sticker_delete", [f"**Sticker :** `{sticker.name}`"])

        for sticker_id, sticker in after_ids.items():
            old = before_ids.get(sticker_id)
            if old is not None and old.name != sticker.name:
                await send_log(
                    guild.id, "sticker_update",
                    [f"**Avant :** `{old.name}`", f"**Après :** `{sticker.name}`"],
                )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModLogGuild(bot))