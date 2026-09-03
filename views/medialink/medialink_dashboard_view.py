"""
views/medialink/medialink_dashboard_view.py — Interface Hub MediaLink.
"""

from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.managers import medialink_manager as medialink_mgr
from utils.settings import settings
from views._components.base_view import BaseLayoutView

_PLATFORM_EMOJI = {
    "youtube": "<:Youtube2:1545107295975772180>",
    "twitch": "<:Twitch2:1545053682129961081>",
    "tiktok": "<:TikTok:1545107255727235113>",
    "reddit": "<:Reddit:1545053589020483724>",
}

_PLATFORM_LABEL = {
    "youtube": "YouTube",
    "twitch": "Twitch",
    "tiktok": "TikTok",
    "reddit": "Reddit",
}

_STATUS_BADGE = {
    "operational": "🟢 Opérationnel",
    "degraded": "🟡 Dégradé",
    "error": "🔴 Erreur",
    "disabled": "⚪ Désactivé",
}

EMOJI_ADD = "<:plus:1495444111505752154>"
EMOJI_EDIT = "<:modifier:1495444144712192003>"
EMOJI_DELETE = "<:supprimer:1495444051623809075>"
EMOJI_BACK = "<:retour:1515658955190308995>"
EMOJI_SETTINGS = "<:parametre:1495444004328706059>"

class MediaLinkHubView(BaseLayoutView):
    """Page principale dashboard MediaLink"""

    def __init__(self, *, guild_id: int, owner_id: int, stats: dict):
        super().__init__(owner_id=owner_id, timeout=600)
        self.guild_id = guild_id
        self.stats = stats
        self._build()

    @classmethod
    async def build(cls, *, guild: discord.Guild, owner_id: int) -> "MediaLinkHubView":
        stats = await medialink_mgr.get_hub_stats(guild.id)
        return cls(guild_id=guild.id, owner_id=owner_id, stats=stats)

    def _build(self) -> None:
        container = Container()

        container.add_item(TextDisplay("# <:analyser:1495446292963528798> Système MédiaLink"))
        container.add_item(TextDisplay("➤ Système de diffusion automatique"))
        container.add_item(Separator())

        # ── Plateformes ──
        container.add_item(TextDisplay("### <:lister:1495445288364675192> __Plateformes__ :"))
        platform_lines = []
        for platform in ("youtube", "twitch", "tiktok", "reddit"):
            count = self.stats["platforms"].get(platform, 0)
            emoji = _PLATFORM_EMOJI[platform]
            label = _PLATFORM_LABEL[platform]
            suffix = "configuration" if count <= 1 else "configurations"
            platform_lines.append(f"**{emoji} {label}** — {count} {suffix}")
        container.add_item(TextDisplay("\n".join(platform_lines)))
        container.add_item(Separator())

        # ── Activité ──
        container.add_item(TextDisplay("### ⚡ __Activité__"))
        error_badge = "🔴" if self.stats["errors"] else "🟢"
        container.add_item(
            TextDisplay(
                f"📢 **{self.stats['sent']}** annonce(s) envoyée(s)\n"
                f"🟢 **{self.stats['active_rules']}** règle(s) active(s)\n"
                f"{error_badge} **{self.stats['errors']}** erreur(s)"
            )
        )
        container.add_item(Separator())

        # ── Navigation (6 écrans, 2 rangées de 3 — ActionRow, pas 6
        # boutons empilés) ──
        platforms_btn = Button(label="Plateformes", style=ButtonStyle.primary, emoji="🌐")
        platforms_btn.callback = self._cb_open_platforms
        events_btn = Button(label="Événements", style=ButtonStyle.secondary, emoji="⚡")
        events_btn.callback = self._cb_open_events
        templates_btn = Button(label="Annonces", style=ButtonStyle.secondary, emoji="📢")
        templates_btn.callback = self._cb_open_templates

        stats_btn = Button(label="Statistiques", style=ButtonStyle.secondary, emoji="📊")
        stats_btn.callback = self._cb_open_statistics
        logs_btn = Button(label="Logs", style=ButtonStyle.secondary, emoji="🗒️")
        logs_btn.callback = self._cb_open_logs
        settings_btn = Button(label="Configuration", style=ButtonStyle.secondary, emoji=EMOJI_SETTINGS)
        settings_btn.callback = self._cb_open_settings

        container.add_item(ActionRow(platforms_btn, events_btn, templates_btn))
        container.add_item(ActionRow(stats_btn, logs_btn, settings_btn))
        container.add_item(Separator())

        doc_btn = Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚")
        container.add_item(ActionRow(doc_btn))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    # ── Callbacks ────────────────────────────────────────────────

    async def _cb_open_platforms(self, interaction: discord.Interaction) -> None:
        view = await MediaLinkDashboardView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)

    async def _cb_open_events(self, interaction: discord.Interaction) -> None:
        from views.medialink.medialink_events_view import GuildEventsOverviewView

        view = await GuildEventsOverviewView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)

    async def _cb_open_templates(self, interaction: discord.Interaction) -> None:
        from views.medialink.medialink_announcement_view import TemplateListView

        view = await TemplateListView.build(guild_id=self.guild_id, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)

    async def _cb_open_statistics(self, interaction: discord.Interaction) -> None:
        # L'instantané ci-dessus (Activité) couvre déjà les chiffres du
        # moment. Cet écran serait pour l'historique/les tendances dans
        # le temps — ça reste bloqué sur l'arbitrage du schéma
        # media_statistics (comptage à la volée vs. table d'agrégats),
        # cf. medialink_statistics_view.py.
        from utils.container_universel import info_container, send_ephemeral

        await send_ephemeral(
            interaction,
            info_container(
                "Les chiffres du moment sont déjà affichés dans la section "
                "Activité du hub. Un écran d'historique détaillé (tendances "
                "dans le temps) reste à faire — le schéma de stockage "
                "(comptage à la volée vs. table d'agrégats) n'est pas "
                "encore tranché."
            ),
        )

    async def _cb_open_logs(self, interaction: discord.Interaction) -> None:
        from views.medialink.medialink_logs_view import MediaLinkLogsView

        view = await MediaLinkLogsView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)

    async def _cb_open_settings(self, interaction: discord.Interaction) -> None:
        from views.medialink.medialink_configuration_view import MediaLinkSettingsView

        view = MediaLinkSettingsView(guild_id=self.guild_id, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)


class MediaLinkDashboardView(BaseLayoutView):
    """Écran "Plateformes" — liste détaillée des connexions de la guild,
    une par une, avec gestion. Ouvert depuis MediaLinkHubView, et cible
    de "retour" pour les écrans enfants (gérer/ajouter une connexion)."""

    def __init__(self, *, guild_id: int, owner_id: int, connections: list[dict]):
        super().__init__(owner_id=owner_id, timeout=600)
        self.guild_id = guild_id
        self.connections = connections
        self._build()

    @classmethod
    async def build(cls, *, guild: discord.Guild, owner_id: int) -> "MediaLinkDashboardView":
        connections = await medialink_mgr.list_connections(guild.id)
        return cls(guild_id=guild.id, owner_id=owner_id, connections=connections)

    def _build(self) -> None:
        container = Container()

        container.add_item(TextDisplay("# 🌐 Plateformes"))

        if not self.connections:
            container.add_item(
                TextDisplay(
                    "Aucun compte connecté pour le moment.\n"
                    "-# Ajoute une première connexion (YouTube, Twitch, TikTok ou "
                    "Reddit) pour commencer à recevoir des annonces automatiques."
                )
            )
        else:
            container.add_item(
                TextDisplay(f"-# {len(self.connections)} connexion(s) active(s) sur ce serveur.")
            )

        container.add_item(Separator())

        for conn in self.connections:
            emoji = _PLATFORM_EMOJI.get(conn["platform"], "🔗")
            label = conn.get("external_username") or conn["external_id"]
            status_badge = _STATUS_BADGE.get(conn.get("status", "operational"), conn.get("status"))
            manage_btn = Button(label="Gérer", style=ButtonStyle.secondary, emoji=EMOJI_EDIT)
            manage_btn.callback = self._cb_manage_connection(conn["id"])
            container.add_item(Section(
                TextDisplay(
                    f"**{emoji} {label}** — {status_badge}\n"
                    f"-# `{conn['platform']}`"
                ),
                accessory=manage_btn,
            ))

        container.add_item(Separator())

        add_btn = Button(label="Ajouter une connexion", style=ButtonStyle.success, emoji=EMOJI_ADD)
        add_btn.callback = self._cb_add_connection
        back_btn = Button(label="Retour au hub", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        back_btn.callback = self._cb_back

        container.add_item(ActionRow(add_btn, back_btn))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    # ── Callbacks ────────────────────────────────────────────────

    def _cb_manage_connection(self, connection_id: int):
        async def _callback(interaction: discord.Interaction) -> None:
            from views.medialink.medialink_events_view import ConnectionRulesView

            connection = next((c for c in self.connections if c["id"] == connection_id), None)
            if connection is None:
                return
            view = await ConnectionRulesView.build(connection=connection, owner_id=self.owner_id)
            await self.push_update(interaction, view=view)
        return _callback

    async def _cb_add_connection(self, interaction: discord.Interaction) -> None:
        from views.medialink.medialink_platforms_view import AddConnectionView

        view = AddConnectionView(guild_id=self.guild_id, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        view = await MediaLinkHubView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)