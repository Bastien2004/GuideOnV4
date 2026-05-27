"""
views/report/dev_report.py — Récapitulatif d'un report envoyé au salon des devs.

Le salon cible vient de settings.report_channel_id (override possible via .env),
avec fallback sur l'ID historique si le champ n'existe pas.
"""
from __future__ import annotations

import logging

import discord
from discord.ui import Container, LayoutView, MediaGallery, Separator, TextDisplay
from discord import MediaGalleryItem

log = logging.getLogger(__name__)

# Fallback si settings.report_channel_id n'est pas défini.
_FALLBACK_REPORT_CHANNEL_ID = 1488233511277297976


def _report_channel_id() -> int:
    try:
        from utils.settings import settings
        return int(getattr(settings, "report_channel_id", _FALLBACK_REPORT_CHANNEL_ID))
    except Exception:
        return _FALLBACK_REPORT_CHANNEL_ID


_IMPORTANCE_EMOJI = {"gênant": "🟡", "important": "🟠", "critique": "🔴"}


async def send_to_devs(bot, report: dict, user: discord.abc.User) -> None:
    """Poste le récap d'un report dans le salon des devs."""
    channel = bot.get_channel(_report_channel_id())
    if channel is None:
        log.warning("Salon report introuvable (id=%s)", _report_channel_id())
        return

    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"# 🐞 Rapport de Bug : {report['reference']}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(f"### 📝 {report['title']}"))
    c.add_item(TextDisplay(report["description"]))
    c.add_item(Separator())

    emoji = _IMPORTANCE_EMOJI.get(report["importance"], "🚩")
    c.add_item(TextDisplay(f"{emoji} **Importance** : {report['importance'].capitalize()}"))
    c.add_item(TextDisplay(f"👤 **Auteur** : {user.mention} (`{user.id}`)"))
    if report.get("guild_id"):
        c.add_item(TextDisplay(f"🏠 **Serveur** : `{report['guild_id']}`"))

    if report.get("attachment_url"):
        c.add_item(Separator())
        try:
            c.add_item(MediaGallery(MediaGalleryItem(report["attachment_url"])))
        except Exception:
            # URL invalide malgré la validation amont : on l'affiche en lien.
            c.add_item(TextDisplay(f"🖼️ Capture : {report['attachment_url']}"))

    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideON Studio"))
    view.add_item(c)

    await channel.send(view=view)