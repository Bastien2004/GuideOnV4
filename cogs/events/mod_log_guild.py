"""
cogs/events/mod_log_guild.py — Gestion des logs de guild (salon/rôle/param_serv/emojis ...).
"""

from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from utils.managers.mod_log_manager import bind_bot, send_log

log = logging.getLogger(__name__)


# ============================================================
# 🔩 Paramètres
# ============================================================

_AUDIT_LOOKUP_ATTEMPTS = 3
_AUDIT_LOOKUP_DELAY = 0.6


# ============================================================
# ⚒️ Fonctions utilitaires
# ============================================================

async def _resolve_actor(guild: discord.Guild, action: discord.AuditLogAction, *, target_id: int | None = None) -> str:
    """Récupère l'auteur d'une action."""

    if guild.me is None or not guild.me.guild_permissions.view_audit_log:
        return "Inconnu"

    for attempt in range(_AUDIT_LOOKUP_ATTEMPTS):
        try:
            async for entry in guild.audit_logs(limit=5, action=action):
                if target_id is not None and getattr(entry.target, "id", None) != target_id:
                    continue
                if entry.user is not None:
                    return entry.user.mention
                break

        except discord.Forbidden:
            return "Inconnu"
        
        except discord.HTTPException:
            log.debug("[MODLOG] Audit-log indisponible (guild=%s, action=%s)", guild.id, action)
            return "Inconnu"
        
        if attempt < _AUDIT_LOOKUP_ATTEMPTS - 1:
            await asyncio.sleep(_AUDIT_LOOKUP_DELAY)

    return "Inconnu"


# ============================================================
# 🖥️ Logs de guild (salon/rôle/emoji ...)
# ============================================================

class ModLogGuild(commands.Cog):
    """Logs des évènements de serveur."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bind_bot(bot)


    ### LOGS DE SALON ###

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        actor = await _resolve_actor(channel.guild, discord.AuditLogAction.channel_create, target_id=channel.id)
        fields = [
            ("Salon", f"{channel.mention} (`{channel.name}`)", True),
            ("Type", str(channel.type).replace("_", " ").title(), True),
            ("Par", actor, True),
        ]
        if channel.category is not None:
            fields.append(("Catégorie", channel.category.name, True))
        await send_log(channel.guild.id, "channel_create", fields)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        actor = await _resolve_actor(channel.guild, discord.AuditLogAction.channel_delete, target_id=channel.id)
        fields = [
            ("Salon", f"`#{channel.name}` (`{channel.id}`)", True),
            ("Type", str(channel.type).replace("_", " ").title(), True),
            ("Par", actor, True),
        ]
        await send_log(channel.guild.id, "channel_delete", fields)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> None:
        changes: list[tuple[str, str, bool]] = []
        if before.name != after.name:
            changes.append(("Nom", f"`#{before.name}` → `#{after.name}`", False))
        if getattr(before, "category", None) != getattr(after, "category", None):
            before_cat = before.category.name if before.category else "*(aucune)*"
            after_cat = after.category.name if after.category else "*(aucune)*"
            changes.append(("Catégorie", f"`{before_cat}` → `{after_cat}`", False))
        if not changes:
            return

        actor = await _resolve_actor(after.guild, discord.AuditLogAction.channel_update, target_id=after.id)
        fields = [("Salon", after.mention, True), ("Par", actor, True), *changes]
        await send_log(after.guild.id, "channel_update", fields)


    ### LOGS DE RÔLE ###

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        actor = await _resolve_actor(role.guild, discord.AuditLogAction.role_create, target_id=role.id)
        fields = [
            ("Rôle", f"{role.mention} (`{role.name}`)", True),
            ("Couleur", str(role.color), True),
            ("Par", actor, True),
        ]
        await send_log(role.guild.id, "role_create", fields)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        actor = await _resolve_actor(role.guild, discord.AuditLogAction.role_delete, target_id=role.id)
        fields = [
            ("Rôle", f"`{role.name}` (`{role.id}`)", True),
            ("Par", actor, True),
        ]
        await send_log(role.guild.id, "role_delete", fields)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        changes: list[tuple[str, str, bool]] = []
        if before.name != after.name:
            changes.append(("Nom", f"`{before.name}` → `{after.name}`", False))
        if before.color != after.color:
            changes.append(("Couleur", f"`{before.color}` → `{after.color}`", False))
        if not changes:
            return

        actor = await _resolve_actor(after.guild, discord.AuditLogAction.role_update, target_id=after.id)
        fields = [("Rôle", after.mention, True), ("Par", actor, True), *changes]
        await send_log(after.guild.id, "role_update", fields)


    ### LOGS DE SERVEUR ###

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        if before.name == after.name and before.icon == after.icon:
            return

        actor = await _resolve_actor(after, discord.AuditLogAction.guild_update, target_id=after.id)
        fields = [("Par", actor, True)]
        if before.name != after.name:
            fields.append(("Nom", f"`{before.name}` → `{after.name}`", False))

        image_url = None
        if before.icon != after.icon:
            fields.append(("Icône", "Modifiée", True))
            image_url = after.icon.url if after.icon is not None else None

        await send_log(after.id, "guild_update", fields, image_url=image_url)


    ### LOGS D'EMOJI/STICKERS ###

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before: list[discord.Emoji], after: list[discord.Emoji]) -> None:
        before_ids = {e.id: e for e in before}
        after_ids = {e.id: e for e in after}

        for emoji_id, emoji in after_ids.items():
            if emoji_id not in before_ids:
                actor = await _resolve_actor(guild, discord.AuditLogAction.emoji_create, target_id=emoji_id)
                await send_log(
                    guild.id, "emoji_create",
                    [("Emoji", f"{emoji} `:{emoji.name}:`", True), ("Par", actor, True)],
                    thumbnail_url=emoji.url,
                )

        for emoji_id, emoji in before_ids.items():
            if emoji_id not in after_ids:
                actor = await _resolve_actor(guild, discord.AuditLogAction.emoji_delete, target_id=emoji_id)
                await send_log(
                    guild.id, "emoji_delete",
                    [("Emoji", f"`:{emoji.name}:`", True), ("Par", actor, True)],
                )

        for emoji_id, emoji in after_ids.items():
            old = before_ids.get(emoji_id)
            if old is not None and old.name != emoji.name:
                actor = await _resolve_actor(guild, discord.AuditLogAction.emoji_update, target_id=emoji_id)
                await send_log(
                    guild.id, "emoji_update",
                    [("Nom", f"`:{old.name}:` → `:{emoji.name}:`", False), ("Par", actor, True)],
                    thumbnail_url=emoji.url,
                )

    @commands.Cog.listener()
    async def on_guild_stickers_update(self, guild: discord.Guild, before: list[discord.GuildSticker], after: list[discord.GuildSticker]) -> None:
        before_ids = {s.id: s for s in before}
        after_ids = {s.id: s for s in after}

        for sticker_id, sticker in after_ids.items():
            if sticker_id not in before_ids:
                actor = await _resolve_actor(guild, discord.AuditLogAction.sticker_create, target_id=sticker_id)
                await send_log(
                    guild.id, "sticker_create",
                    [("Sticker", f"`{sticker.name}`", True), ("Par", actor, True)],
                    thumbnail_url=sticker.url,
                )

        for sticker_id, sticker in before_ids.items():
            if sticker_id not in after_ids:
                actor = await _resolve_actor(guild, discord.AuditLogAction.sticker_delete, target_id=sticker_id)
                await send_log(
                    guild.id, "sticker_delete",
                    [("Sticker", f"`{sticker.name}`", True), ("Par", actor, True)],
                )

        for sticker_id, sticker in after_ids.items():
            old = before_ids.get(sticker_id)
            if old is not None and old.name != sticker.name:
                actor = await _resolve_actor(guild, discord.AuditLogAction.sticker_update, target_id=sticker_id)
                await send_log(
                    guild.id, "sticker_update",
                    [("Nom", f"`{old.name}` → `{sticker.name}`", False), ("Par", actor, True)],
                    thumbnail_url=sticker.url,
                )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModLogGuild(bot))