"""
views/medialink/medialink_dashboard_view.py — écran d'accueil de
/medialink config : liste des connexions de la guild, accès aux autres
écrans (§6.2, §16).
"""
from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import Button, Container, Section, Separator, TextDisplay

from utils.managers import medialink_manager as medialink_mgr
from utils.medialink.builders.container import empty_state_container
from views._components.base_view import BaseLayoutView

_PLATFORM_EMOJI = {
    "youtube": "▶️",
    "twitch": "🟣",
    "tiktok": "🎵",
    "reddit": "👽",
}


class MediaLinkDashboardView(BaseLayoutView):
    """Dashboard principal MEDIALINK — envoyé par /medialink config
    (cogs/medialink/medialink_config.py)."""

    def __init__(self, *, guild_id: int, owner_id: int, connections: list[dict]):
        super().__init__(owner_id=owner_id, timeout=600)
        self.guild_id = guild_id
        self.connections = connections
        self._build()

    @classmethod
    async def build(cls, *, guild: discord.Guild, owner_id: int) -> "MediaLinkDashboardView | discord.ui.LayoutView":
        connections = await medialink_mgr.list_connections(guild.id)
        if not connections:
            # §6.2 : état vide explicite plutôt qu'un dashboard silencieux.
            return empty_state_container()
        return cls(guild_id=guild.id, owner_id=owner_id, connections=connections)

    def _build(self) -> None:
        container = Container()

        container.add_item(TextDisplay("# 📡 MEDIALINK"))
        container.add_item(
            TextDisplay(f"-# {len(self.connections)} connexion(s) active(s) sur ce serveur.")
        )
        container.add_item(Separator())

        for conn in self.connections:
            emoji = _PLATFORM_EMOJI.get(conn["platform"], "🔗")
            label = conn.get("external_username") or conn["external_id"]
            status = conn.get("status", "operational")
            manage_btn = Button(label="Gérer", style=ButtonStyle.secondary)
            manage_btn.callback = self._cb_manage_connection(conn["id"])
            container.add_item(Section(
                TextDisplay(
                    f"{emoji} __**{label}**__ · `{conn['platform']}`\n"
                    f"➥ Statut : `{status}`"
                ),
                accessory=manage_btn,
            ))

        container.add_item(Separator())

        add_btn = Button(label="Ajouter une connexion", style=ButtonStyle.primary, emoji="➕")
        add_btn.callback = self._cb_add_connection
        stats_btn = Button(label="Statistiques", style=ButtonStyle.secondary, emoji="📊")
        stats_btn.callback = self._cb_open_statistics
        logs_btn = Button(label="Historique", style=ButtonStyle.secondary, emoji="🗒️")
        logs_btn.callback = self._cb_open_logs

        container.add_item(Section(TextDisplay("Actions :"), accessory=add_btn))
        container.add_item(Section(TextDisplay(" "), accessory=stats_btn))
        container.add_item(Section(TextDisplay(" "), accessory=logs_btn))
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    # ── Callbacks ────────────────────────────────────────────────
    # Stubs : chaque callback devra ouvrir la vue correspondante
    # (medialink_platforms_view.py, medialink_events_view.py,
    # medialink_statistics_view.py, medialink_logs_view.py) via
    # self.push_update(interaction, view=...).

    def _cb_manage_connection(self, connection_id: int):
        async def _callback(interaction: discord.Interaction) -> None:
            raise NotImplementedError(
                f"dashboard._cb_manage_connection({connection_id}) — "
                "ouvrir medialink_events_view.py (roadmap)"
            )
        return _callback

    async def _cb_add_connection(self, interaction: discord.Interaction) -> None:
        raise NotImplementedError("dashboard._cb_add_connection — ouvrir medialink_platforms_view.py")

    async def _cb_open_statistics(self, interaction: discord.Interaction) -> None:
        raise NotImplementedError("dashboard._cb_open_statistics — ouvrir medialink_statistics_view.py")

    async def _cb_open_logs(self, interaction: discord.Interaction) -> None:
        raise NotImplementedError("dashboard._cb_open_logs — ouvrir medialink_logs_view.py")
