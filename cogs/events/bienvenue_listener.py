"""
cogs/events/bienvenue_listener.py — Envoie les messages de bienvenue/départ.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from utils.bienvenue_render import build_bienvenue_embed, build_bienvenue_view, render_template, resolve_image_url
from utils.managers.bienvenue_manager import load_bienvenue_config

log = logging.getLogger(__name__)


# ============================================================
#  🧩 Class principale
# ============================================================

class BienvenueListener(commands.Cog):
    """Cog d'envoi des annonces d'arrivée/départ."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _send_announcement(self, member: discord.Member, *, channel_id: int | None, template: str, kind: str, format_: str, image_url: str | None) -> None:
        """Envoie le message d'arrivée ou de départ dans le salon configuré."""

        guild = member.guild

        # 🔩 Vérifie qu'un salon est configuré.
        if not channel_id:
            log.debug("[LISTENER BIENVENUE] %s ignoré (pas de salon configuré) guild=%s", kind, guild.id)
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                channel = None

        # ⚠️ Vérifie que le salon est valide.
        if not isinstance(channel, discord.TextChannel):
            log.warning("[LISTENER BIENVENUE] Salon %s introuvable/invalide pour %s (guild=%s)", channel_id, kind, guild.id)
            return

        # ✅ Vérifie que le bot a les permissions nécessaires.
        me = guild.me
        if me is not None:
            perms = channel.permissions_for(me)
            if not (perms.send_messages and perms.view_channel):
                log.warning("[LISTENER BIENVENUE] Permissions insuffisantes dans #%s pour %s (guild=%s)", channel.name, kind, guild.id)
                return

        rendered = render_template(template, member=member, guild=guild)
        embed_kind = "arrivee" if kind == "arrivée" else "depart"

        # ✉️ Envoie le message dans le salon.
        try:
            if format_ == "text":
                await channel.send(view=build_bienvenue_view(rendered, kind=embed_kind))
            else:
                resolved_image = resolve_image_url(guild.id, image_url)
                embed, file = build_bienvenue_embed(rendered, kind=embed_kind, custom_image_url=resolved_image)

                if file is not None:
                    await channel.send(embed=embed, file=file)
                else:
                    await channel.send(embed=embed)

        except discord.Forbidden:
            log.warning("[LISTENER BIENVENUE] Forbidden en envoyant %s dans #%s (guild=%s)", kind, channel.name, guild.id)

        except discord.HTTPException:
            log.exception("[LISTENER BIENVENUE] Erreur HTTP en envoyant %s (guild=%s)", kind, guild.id)


# ============================================================
#  💻 Listener
# ============================================================

    # 👋 Cas d'arrivée 
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return

        cfg = await load_bienvenue_config(member.guild.id)
        if not cfg.get("system_active") or not cfg.get("arrive_active"):
            return

        await self._send_announcement(
            member,
            channel_id=cfg.get("arrive_channel_id"),
            template=cfg.get("arrive_message", ""),
            kind="arrivée",
            format_=cfg.get("arrive_format", "embed"),
            image_url=cfg.get("arrive_image_url"),
        )

    # 🚪 Cas de départ
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if member.bot:
            return

        cfg = await load_bienvenue_config(member.guild.id)
        if not cfg.get("system_active") or not cfg.get("depart_active"):
            return

        await self._send_announcement(
            member,
            channel_id=cfg.get("depart_channel_id"),
            template=cfg.get("depart_message", ""),
            kind="départ",
            format_=cfg.get("depart_format", "embed"),
            image_url=cfg.get("depart_image_url"),
        )


# ============================================================
#  💻 Setup BOT
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BienvenueListener(bot))