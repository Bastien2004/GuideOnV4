"""
cogs/events/bienvenue_listener.py — Envoi des messages de bienvenue/départ.

commands.Cog avec setup() → chargé automatiquement par _load_cogs_from_directory
(rglob récursif sur cogs/). C'est le chaînon manquant entre la configuration
(/config bienvenue, utils.managers.bienvenue_manager) et son effet réel :
sans ce listener, la config est enregistrée en DB mais jamais lue à
l'arrivée/au départ d'un membre — aucun message n'est jamais envoyé, et
aucune erreur n'est levée puisqu'aucun code ne s'exécute.

Logique métier :
- on_member_join :
    1. ignore les bots
    2. system_active=False pour la guild → skip
    3. arrive_active=False ou arrive_channel_id absent → skip
    4. salon introuvable / permissions insuffisantes → log + skip (silencieux
       côté Discord, mais tracé côté logs pour debug)
    5. rend le template (utils.bienvenue_render) et l'envoie au format choisi
       par l'admin (embed ou Components V2 — voir utils.bienvenue_render
       pour le détail de l'exception zéro-embed, limitée au mode embed).
       En mode embed, une image personnalisée (Gold+) peut remplacer la
       bannière par défaut — dégradation automatique si le Gold+ expire.
- on_member_remove : même logique, côté départ.

Le rendu utilise utils.bienvenue_render.render_template, le MÊME module que
l'aperçu affiché dans /config bienvenue — l'aperçu correspond donc
exactement à ce qui sera réellement envoyé.
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from utils.bienvenue_render import (
    build_bienvenue_embed,
    build_bienvenue_view,
    render_template,
    resolve_image_url,
)
from utils.managers.bienvenue_manager import load_bienvenue_config

log = logging.getLogger(__name__)


class BienvenueListener(commands.Cog):
    """Cog d'envoi des annonces d'arrivée/départ."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _send_announcement(
        self, member: discord.Member, *,
        channel_id: int | None, template: str, kind: str,
        format_: str, image_url: str | None,
    ) -> None:
        guild = member.guild

        if not channel_id:
            log.debug(
                "[Bienvenue] %s ignoré (pas de salon configuré) guild=%s", kind, guild.id
            )
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                channel = None

        if not isinstance(channel, discord.TextChannel):
            log.warning(
                "[Bienvenue] Salon %s introuvable/invalide pour %s (guild=%s)",
                channel_id, kind, guild.id,
            )
            return

        me = guild.me
        if me is not None:
            perms = channel.permissions_for(me)
            if not (perms.send_messages and perms.view_channel):
                log.warning(
                    "[Bienvenue] Permissions insuffisantes dans #%s pour %s (guild=%s)",
                    channel.name, kind, guild.id,
                )
                return

        rendered = render_template(template, member=member, guild=guild)
        embed_kind = "arrivee" if kind == "arrivée" else "depart"

        try:
            if format_ == "text":
                await channel.send(view=build_bienvenue_view(rendered, kind=embed_kind))
            else:
                resolved_image = resolve_image_url(guild.id, image_url)
                embed, file = build_bienvenue_embed(
                    rendered, kind=embed_kind, custom_image_url=resolved_image,
                )
                if file is not None:
                    await channel.send(embed=embed, file=file)
                else:
                    await channel.send(embed=embed)
        except discord.Forbidden:
            log.warning(
                "[Bienvenue] Forbidden en envoyant %s dans #%s (guild=%s)",
                kind, channel.name, guild.id,
            )
        except discord.HTTPException:
            log.exception(
                "[Bienvenue] Erreur HTTP en envoyant %s (guild=%s)", kind, guild.id
            )

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------

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


# ----------------------------------------------------
# 🔧 Setup du cog
# ----------------------------------------------------

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BienvenueListener(bot))