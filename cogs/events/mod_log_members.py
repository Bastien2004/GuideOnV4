"""
cogs/events/mod_log_members.py — Logs /mod : membres.

Arrivées/départs, rôles donnés/retirés (pack Stagiaire), renommage et
boost serveur (pack Chercheur/Espion — cf. mod_log_manager.PACK_EVENTS
pour la répartition exacte), nom d'utilisateur et avatar globaux (pack
Espion, via on_user_update — évènement non lié à un serveur précis,
donc relayé dans chaque serveur commun via user.mutual_guilds).

commands.Cog avec setup() -> chargé automatiquement par _load_cogs_from_directory.
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from utils.managers.mod_log_manager import send_log

log = logging.getLogger(__name__)


class ModLogMembers(commands.Cog):
    """Logs des évènements liés aux membres et aux utilisateurs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await send_log(
            member.guild.id, "member_join",
            [f"**Membre :** {member.mention} (`{member.id}`)", f"-# Compte créé <t:{int(member.created_at.timestamp())}:R>"],
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await send_log(
            member.guild.id, "member_leave",
            [f"**Membre :** {member} (`{member.id}`)"],
        )

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        guild_id = after.guild.id

        if before.nick != after.nick:
            await send_log(
                guild_id, "member_rename",
                [
                    f"**Membre :** {after.mention}",
                    f"**Avant :** {before.nick or before.name}",
                    f"**Après :** {after.nick or after.name}",
                ],
            )

        before_roles = set(before.roles)
        after_roles = set(after.roles)

        for role in after_roles - before_roles:
            if role.is_default():
                continue
            await send_log(
                guild_id, "role_add",
                [f"**Membre :** {after.mention}", f"**Rôle :** {role.mention}"],
            )

        for role in before_roles - after_roles:
            if role.is_default():
                continue
            await send_log(
                guild_id, "role_remove",
                [f"**Membre :** {after.mention}", f"**Rôle :** {role.mention}"],
            )

        if before.premium_since != after.premium_since:
            if after.premium_since is not None:
                await send_log(guild_id, "boost", [f"**Membre :** {after.mention} a commencé à **booster** le serveur."])
            else:
                await send_log(guild_id, "boost", [f"**Membre :** {after.mention} ne boost plus le serveur."])

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User) -> None:
        guilds = getattr(after, "mutual_guilds", None) or []

        if before.name != after.name or before.global_name != after.global_name:
            for guild in guilds:
                await send_log(
                    guild.id, "user_rename",
                    [f"**Utilisateur :** {after.mention} (`{after.id}`)", f"**Avant :** {before}", f"**Après :** {after}"],
                )

        if before.avatar != after.avatar:
            for guild in guilds:
                await send_log(
                    guild.id, "avatar_update",
                    [f"**Utilisateur :** {after.mention} (`{after.id}`)"],
                )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModLogMembers(bot))