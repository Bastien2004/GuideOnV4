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


def _duration_label(delta) -> str:
    days = delta.days
    if days >= 1:
        return f"{days} jour(s)"
    hours = delta.seconds // 3600
    if hours >= 1:
        return f"{hours} heure(s)"
    return f"{max(delta.seconds // 60, 1)} minute(s)"


class ModLogMembers(commands.Cog):
    """Logs des évènements liés aux membres et aux utilisateurs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        fields = [
            ("Membre", f"{member.mention} (`{member.id}`)", True),
            ("Compte créé", f"<t:{int(member.created_at.timestamp())}:R>", True),
            ("Effectif du serveur", str(member.guild.member_count), True),
        ]
        await send_log(
            member.guild.id, "member_join", fields,
            thumbnail_url=member.display_avatar.url,
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        fields = [
            ("Membre", f"{member} (`{member.id}`)", True),
            ("Effectif du serveur", str(member.guild.member_count), True),
        ]
        if member.joined_at is not None:
            stayed = discord.utils.utcnow() - member.joined_at
            fields.append(("Arrivé le", f"<t:{int(member.joined_at.timestamp())}:R>", True))
            fields.append(("Resté", _duration_label(stayed), True))

        await send_log(
            member.guild.id, "member_leave", fields,
            thumbnail_url=member.display_avatar.url,
        )

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        guild_id = after.guild.id

        if before.nick != after.nick:
            await send_log(
                guild_id, "member_rename",
                [
                    ("Membre", f"{after.mention} (`{after.id}`)", True),
                    ("Avant", before.nick or before.name, True),
                    ("Après", after.nick or after.name, True),
                ],
                thumbnail_url=after.display_avatar.url,
            )

        before_roles = set(before.roles)
        after_roles = set(after.roles)

        for role in after_roles - before_roles:
            if role.is_default():
                continue
            await send_log(
                guild_id, "role_add",
                [
                    ("Membre", f"{after.mention} (`{after.id}`)", True),
                    ("Rôle", f"{role.mention} (`{role.id}`)", True),
                ],
                thumbnail_url=after.display_avatar.url,
            )

        for role in before_roles - after_roles:
            if role.is_default():
                continue
            await send_log(
                guild_id, "role_remove",
                [
                    ("Membre", f"{after.mention} (`{after.id}`)", True),
                    ("Rôle", f"{role.mention} (`{role.id}`)", True),
                ],
                thumbnail_url=after.display_avatar.url,
            )

        if before.premium_since != after.premium_since:
            guild = after.guild
            fields = [
                ("Membre", f"{after.mention} (`{after.id}`)", True),
                ("Niveau du serveur", f"Niveau {guild.premium_tier}", True),
                ("Boosts actifs", str(guild.premium_subscription_count), True),
            ]
            description = (
                f"{after.mention} a commencé à **booster** le serveur."
                if after.premium_since is not None
                else f"{after.mention} ne boost plus le serveur."
            )
            await send_log(
                guild_id, "boost", fields,
                description=description,
                thumbnail_url=after.display_avatar.url,
            )

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User) -> None:
        guilds = getattr(after, "mutual_guilds", None) or []

        if before.name != after.name or before.global_name != after.global_name:
            for guild in guilds:
                await send_log(
                    guild.id, "user_rename",
                    [
                        ("Utilisateur", f"{after.mention} (`{after.id}`)", True),
                        ("Avant", str(before), True),
                        ("Après", str(after), True),
                    ],
                    thumbnail_url=after.display_avatar.url,
                )

        if before.avatar != after.avatar:
            for guild in guilds:
                await send_log(
                    guild.id, "avatar_update",
                    [("Utilisateur", f"{after.mention} (`{after.id}`)", True)],
                    thumbnail_url=before.display_avatar.url,
                    image_url=after.display_avatar.url,
                )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModLogMembers(bot))