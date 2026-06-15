"""
cogs/events/onu_alpha.py — Listener ONU Alpha.

Boucle toutes les 30 s. Pour chaque guild configuré et activé :
  - Si on est le bon jour + bonne heure → envoie la pré-annonce OU l'annonce
  - Les pré-annonces/annonces sont dé-dupliquées par (guild_id, "YYYY-MM-DD HH:MM")

Chargé automatiquement par _load_cogs_from_directory.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks
from discord.ui import (
    Container, LayoutView, MediaGallery, Section, Separator, TextDisplay,
)
from discord import MediaGalleryItem

from utils.managers.alpha_onu_manager import (
    list_all_onu_configs,
    get_onu_ping_members,
)
from utils.db.models.alpha_onu_config import JOURS_LABELS

log = logging.getLogger(__name__)


class ONUAlphaListener(commands.Cog):
    """Gère les annonces ONU automatiques pour le serveur Alpha."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_pre: dict[int, str] = {}
        self._last_ann: dict[int, str] = {}
        self.onu_task.start()

    def cog_unload(self) -> None:
        self.onu_task.cancel()

    # ════════════════════════════════════════════════════════
    # 🔁 Boucle principale
    # ════════════════════════════════════════════════════════

    @tasks.loop(seconds=30)
    async def onu_task(self) -> None:
        try:
            configs = await list_all_onu_configs()
        except Exception:
            log.exception("[ONU] Erreur lors du chargement des configs")
            return

        now_utc = datetime.now(timezone.utc)

        for cfg in configs:
            if not cfg.get("enabled") or not cfg.get("channel_id"):
                continue
            if cfg.get("jour_onu") is None:
                continue

            try:
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(cfg.get("timezone") or "Europe/Paris")
            except Exception:
                from zoneinfo import ZoneInfo
                tz = ZoneInfo("Europe/Paris")

            now = now_utc.astimezone(tz)
            if now.weekday() != cfg["jour_onu"]:
                continue

            guild_id = cfg["guild_id"]
            current_minute = now.strftime("%Y-%m-%d %H:%M")

            # Pré-annonce
            if (
                cfg.get("pre_heure") is not None
                and cfg.get("pre_minute") is not None
                and now.hour == cfg["pre_heure"]
                and now.minute == cfg["pre_minute"]
                and self._last_pre.get(guild_id) != current_minute
            ):
                self._last_pre[guild_id] = current_minute
                await self._send_pre_annonce(cfg)

            # Annonce
            if (
                cfg.get("ann_heure") is not None
                and cfg.get("ann_minute") is not None
                and now.hour == cfg["ann_heure"]
                and now.minute == cfg["ann_minute"]
                and self._last_ann.get(guild_id) != current_minute
            ):
                self._last_ann[guild_id] = current_minute
                await self._send_annonce(cfg)

    @onu_task.before_loop
    async def before_onu(self) -> None:
        await self.bot.wait_until_ready()

    @onu_task.error
    async def onu_task_error(self, error: Exception) -> None:
        log.exception("[ONU] Erreur non gérée dans la boucle : %s", error)

    # ════════════════════════════════════════════════════════
    # 🔧 Helpers
    # ════════════════════════════════════════════════════════

    async def _get_channel(self, cfg: dict) -> discord.TextChannel | None:
        guild = self.bot.get_guild(cfg["guild_id"])
        if guild is None:
            log.warning("[ONU] Guild %d introuvable", cfg["guild_id"])
            return None
        channel = guild.get_channel(cfg["channel_id"])
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(cfg["channel_id"])
            except (discord.NotFound, discord.HTTPException):
                log.warning("[ONU] Salon %d introuvable", cfg["channel_id"])
                return None
        return channel

    def _get_image_file(self, cfg: dict) -> discord.File | None:
        name = cfg.get("image_name")
        if not name:
            return None
        path = f"source/{name}"
        if not os.path.exists(path):
            log.warning("[ONU] Image introuvable : %s", path)
            return None
        return discord.File(path, filename=name)

    # ════════════════════════════════════════════════════════
    # 📢 Pré-annonce
    # ════════════════════════════════════════════════════════

    async def _send_pre_annonce(self, cfg: dict) -> None:
        channel = await self._get_channel(cfg)
        if channel is None:
            return

        ping = f"<@&{cfg['role_id']}> " if cfg.get("role_id") else ""

        view = LayoutView(timeout=None)
        c = Container()
        c.add_item(TextDisplay(f"# 🌐 ONU Alpha | {ping}"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "L'**ONU** démarre dans **30 minutes** ! ⏳\n"
            "👉 Rejoignez le [Discord NationsGlory](https://discord.gg/nationsglory) "
            "et prenez le **rôle** `'Serveur Alpha'`."
        ))
        c.add_item(Separator())

        img = self._get_image_file(cfg)
        if img:
            c.add_item(MediaGallery(MediaGalleryItem(f"attachment://{img.filename}")))
            c.add_item(Separator())

        c.add_item(TextDisplay("-# <:Alpha:1500414179650048070> Staff Alpha"))
        view.add_item(c)

        try:
            kwargs: dict = {"view": view}
            if img:
                kwargs["files"] = [img]
            await channel.send(**kwargs)
            log.info("[ONU] Pré-annonce envoyée | guild=%d", cfg["guild_id"])
        except discord.HTTPException:
            log.exception("[ONU] Erreur envoi pré-annonce | guild=%d", cfg["guild_id"])
            return

        # Ping MP
        if cfg.get("ping_mp"):
            await self._send_mp(cfg, channel.guild)

    # ════════════════════════════════════════════════════════
    # 📢 Annonce
    # ════════════════════════════════════════════════════════

    async def _send_annonce(self, cfg: dict) -> None:
        channel = await self._get_channel(cfg)
        if channel is None:
            return

        ping = f"<@&{cfg['role_id']}> " if cfg.get("role_id") else ""

        view = LayoutView(timeout=None)
        c = Container()
        c.add_item(TextDisplay(f"# 🌐 Début de l'ONU Alpha | {ping}"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "L'**ONU** commence **maintenant** !\n"
            "Nous vous attendons **nombreux** pour ce moment d'__échange__. 🎙️"
        ))
        c.add_item(Separator())

        img = self._get_image_file(cfg)
        if img:
            c.add_item(MediaGallery(MediaGalleryItem(f"attachment://{img.filename}")))
            c.add_item(Separator())

        # Bouton rejoindre (optionnel)
        if cfg.get("join_url"):
            join_btn = discord.ui.Button(
                label="Rejoindre la conférence",
                style=discord.ButtonStyle.link,
                url=cfg["join_url"],
                emoji="🎧",
            )
            c.add_item(Section(
                TextDisplay("🎙️ **Accéder à la conférence ONU**"),
                accessory=join_btn,
            ))
            c.add_item(Separator())

        c.add_item(TextDisplay("-# <:Alpha:1500414179650048070> Staff Alpha"))
        view.add_item(c)

        try:
            kwargs: dict = {"view": view}
            if img:
                kwargs["files"] = [img]
            await channel.send(**kwargs)
            log.info("[ONU] Annonce envoyée | guild=%d", cfg["guild_id"])
        except discord.HTTPException:
            log.exception("[ONU] Erreur envoi annonce | guild=%d", cfg["guild_id"])

    # ════════════════════════════════════════════════════════
    # 🔔 Ping MP
    # ════════════════════════════════════════════════════════

    async def _send_mp(self, cfg: dict, guild: discord.Guild) -> None:
        """Envoie un DM aux membres de la ping-list."""
        member_ids = await get_onu_ping_members(cfg["guild_id"])
        jour_label = JOURS_LABELS[cfg["jour_onu"]] if cfg.get("jour_onu") is not None else "ce soir"

        for uid in member_ids:
            member = guild.get_member(uid)
            if member is None:
                try:
                    member = await guild.fetch_member(uid)
                except (discord.NotFound, discord.HTTPException):
                    continue
            try:
                await member.send(
                    f"🔔 **Rappel ONU Alpha**\n"
                    f"Salut {member.display_name}, l'ONU commence dans **30 minutes** ({jour_label}) !"
                )
            except discord.Forbidden:
                log.warning("[ONU] DM impossible pour %d", uid)
            except discord.HTTPException:
                log.warning("[ONU] Erreur DM pour %d", uid)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ONUAlphaListener(bot))