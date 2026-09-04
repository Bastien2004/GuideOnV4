"""
views/medialink/medialink_statistics_view.py — écran "Statistiques".
"""

from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay

from utils.managers import medialink_manager as medialink_mgr
from views._components.base_view import BaseLayoutView

EMOJI_BACK = "<:retour:1515658955190308995>"

_PLATFORM_EMOJI = {
    "youtube": "<:Youtube2:1545107295975772180>",
    "twitch": "<:Twitch2:1545053682129961081>",
    "tiktok": "<:TikTok:1545107255727235113>",
    "reddit": "<:Reddit:1545053589020483724>",
}

_STATUS_BADGE = {
    "operational": "🟢 Opérationnel",
    "degraded": "🟡 Dégradé",
    "error": "🔴 Erreur",
    "disabled": "⚪ Désactivé",
}

MAX_CONNECTIONS_SHOWN = 15


def _format_rate(rate: float | None) -> str:
    """Gestion du taux de succès."""

    if rate is None:
        return "—"
    return f"{rate * 100:.0f}%"


class MediaLinkStatisticsView(BaseLayoutView):
    """Comptage en direct sur media_events/media_rules."""

    def __init__(self, *, guild_id: int, owner_id: int, stats: dict):
        super().__init__(owner_id=owner_id, timeout=300)
        self.guild_id = guild_id
        self.stats = stats
        self._build()

    @classmethod
    async def build(cls, *, guild: discord.Guild, owner_id: int) -> "MediaLinkStatisticsView":
        stats = await medialink_mgr.get_detailed_stats(guild.id)
        return cls(guild_id=guild.id, owner_id=owner_id, stats=stats)

    def _build(self) -> None:
        container = Container()
        container.add_item(TextDisplay("# 📊 Statistiques"))
        container.add_item(TextDisplay(
            "-# Comptage en direct sur les événements enregistrés — pas d'historique dans le temps."
        ))
        container.add_item(Separator())

        totals = self.stats["totals"]
        container.add_item(TextDisplay(
            "**Global**\n"
            f"-# ✅ Envoyés : {totals['sent']}\n"
            f"-# ❌ Échoués : {totals['failed']}\n"
            f"-# ⏭️ Ignorés : {totals['skipped']}\n"
            f"-# ⏳ En attente : {totals['pending']}\n"
            f"-# Taux de succès : {_format_rate(totals['success_rate'])}"
        ))
        container.add_item(Separator())

        by_connection = self.stats["by_connection"]
        if not by_connection:
            container.add_item(TextDisplay("*Aucune connexion sur ce serveur.*"))
        else:
            for entry in by_connection[:MAX_CONNECTIONS_SHOWN]:
                emoji = _PLATFORM_EMOJI.get(entry["platform"], "🔗")
                status_badge = _STATUS_BADGE.get(entry["status"], entry["status"])
                container.add_item(TextDisplay(
                    f"**{emoji} {entry['label']}** — {status_badge}\n"
                    f"-# ✅ {entry['sent']} · ❌ {entry['failed']} · ⏭️ {entry['skipped']} · "
                    f"⏳ {entry['pending']} · Taux : {_format_rate(entry['success_rate'])}\n"
                    f"-# Règles actives : {entry['active_rules']}/{entry['total_rules']}"
                ))
            if len(by_connection) > MAX_CONNECTIONS_SHOWN:
                remaining = len(by_connection) - MAX_CONNECTIONS_SHOWN
                container.add_item(TextDisplay(f"-# … et {remaining} connexion(s) supplémentaire(s), non affichée(s)."))

        container.add_item(Separator())
        back_btn = Button(label="Retour au hub", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        back_btn.callback = self._cb_back
        container.add_item(ActionRow(back_btn))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        from views.medialink.medialink_dashboard_view import MediaLinkHubView

        view = await MediaLinkHubView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)