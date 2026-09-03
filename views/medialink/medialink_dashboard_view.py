"""
views/medialink/medialink_dashboard_view.py — écrans "hub" de
/medialink config (§6.2, §16).
 
Deux classes ici, formant une hiérarchie à 2 niveaux (retour Paul du
2026-09 : le dashboard plat d'origine ne montrait ni stats ni vue
d'ensemble par plateforme — cf. capture envoyée en référence) :
 
  - MediaLinkHubView : l'écran d'ACCUEIL envoyé par /medialink config.
    Vue d'ensemble (comptage de connexions par plateforme + activité
    globale de la guild) + navigation vers les 6 écrans du module.
  - MediaLinkDashboardView : l'écran "Plateformes" — la liste détaillée
    des connexions (une par une, avec bouton Gérer) + Ajouter une
    connexion. Ouvert depuis le hub, ou en "retour" depuis les écrans
    enfants (gestion d'une connexion, ajout).
 
Pas de tentative de reproduire des bordures ASCII/box-drawing : ça ne
s'aligne pas correctement dans le client Discord réel hors bloc de
code, et ce n'est pas le langage visuel du reste du bot (Components V2
natif, cf. cogs/mod/mod_config.py et consorts) — même structure
d'information que la référence, rendu natif.
"""
from __future__ import annotations
 
import discord
from discord import ButtonStyle
from discord.ui import Button, Container, Section, Separator, TextDisplay
 
from utils.managers import medialink_manager as medialink_mgr
from views._components.base_view import BaseLayoutView
 
_PLATFORM_EMOJI = {
    "youtube": "▶️",
    "twitch": "🟣",
    "tiktok": "🎵",
    "reddit": "🔴",
}
 
_PLATFORM_LABEL = {
    "youtube": "YouTube",
    "twitch": "Twitch",
    "tiktok": "TikTok",
    "reddit": "Reddit",
}
 
 
class MediaLinkHubView(BaseLayoutView):
    """Écran d'accueil MEDIALINK — envoyé par /medialink config
    (cogs/medialink/medialink_config.py). Vue d'ensemble + navigation."""
 
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
 
        container.add_item(TextDisplay("# 📡 MEDIALINK"))
        container.add_item(TextDisplay("-# Hub de diffusion automatique"))
        container.add_item(Separator())
 
        # ── Plateformes ──
        container.add_item(TextDisplay("**🌐 PLATEFORMES**"))
        platform_lines = []
        for platform in ("youtube", "twitch", "tiktok", "reddit"):
            count = self.stats["platforms"].get(platform, 0)
            emoji = _PLATFORM_EMOJI[platform]
            label = _PLATFORM_LABEL[platform]
            suffix = "configuration" if count <= 1 else "configurations"
            platform_lines.append(f"{emoji} {label} — **{count}** {suffix}")
        container.add_item(TextDisplay("\n".join(platform_lines)))
        container.add_item(Separator())
 
        # ── Activité ──
        # Instantané courant (comptages directs), pas l'écran
        # Statistiques détaillé (cf. _cb_open_statistics plus bas).
        container.add_item(TextDisplay("**⚡ ACTIVITÉ**"))
        container.add_item(
            TextDisplay(
                f"📢 **{self.stats['sent']}** annonce(s) envoyée(s)\n"
                f"🟢 **{self.stats['active_rules']}** règle(s) active(s)\n"
                f"{'🔴' if self.stats['errors'] else '🟢'} **{self.stats['errors']}** erreur(s)"
            )
        )
        container.add_item(Separator())
 
        # ── Navigation (6 écrans, 2 rangées de 3) ──
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
        settings_btn = Button(label="Configuration", style=ButtonStyle.secondary, emoji="⚙️")
        settings_btn.callback = self._cb_open_settings
 
        container.add_item(Section(TextDisplay("Gérer tes connexions et leurs règles :"), accessory=platforms_btn))
        container.add_item(Section(TextDisplay("-# Toutes les règles de la guild en un coup d'œil"), accessory=events_btn))
        container.add_item(Section(TextDisplay("-# Modèles de messages d'annonce"), accessory=templates_btn))
        container.add_item(Section(TextDisplay("-# Détails et historique des envois"), accessory=stats_btn))
        container.add_item(Section(TextDisplay("-# Journal technique du module"), accessory=logs_btn))
        container.add_item(Section(TextDisplay("-# Réglages transverses"), accessory=settings_btn))
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
                    "Ajoute une première connexion (YouTube, Twitch, TikTok ou "
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
        back_btn = Button(label="Retour au hub", style=ButtonStyle.secondary, emoji="↩️")
        back_btn.callback = self._cb_back
 
        container.add_item(Section(TextDisplay("Actions :"), accessory=add_btn))
        container.add_item(Section(TextDisplay("-# Retour à l'accueil MEDIALINK"), accessory=back_btn))
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