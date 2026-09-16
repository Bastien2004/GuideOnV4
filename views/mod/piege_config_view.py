"""
views/mod/piege_config_view.py — Interface de configuration du système de piège (HoneyPot).
"""

from __future__ import annotations

import logging
import os

import discord
from discord import ButtonStyle, MediaGalleryItem
from discord.ui import ActionRow, Button, Container, MediaGallery, Section, Separator, TextDisplay

from utils.container_universel import error_container, info_container, send_ephemeral
from utils.managers.honeypot_manager import load_config, set_channel, set_enabled
from utils.settings import settings
from views._components.base_view import BaseLayoutView
from views.mod.piege_ignored_view import PiegeIgnoredListView

log = logging.getLogger(__name__)


# ============================================================
# 🥰 Emojis
# ============================================================

ICON_HEADER = "<:bouclier:1539013183577133106>"
ICON_PLUS = "<:plus:1495444111505752154>"
ICON_DELETE = "<:supprimer:1495444051623809075>"
ICON_VALIDER = "<:valider:1495444292867723284>"
ICON_ANNULER = "<:annuler:1495444256754761979>"
ICON_LISTE = "<:lister:1495445288364675192>"


# ============================================================
# 🔩 Paramètres
# ============================================================

CHANNEL_NAME = "🍯・piège"

PIEGE_BANNER_FILENAME = "piege_guideon.webp"
PIEGE_BANNER_PATH = os.path.join("source", PIEGE_BANNER_FILENAME)

_WARNING_MESSAGE = (
    "Ce salon sert de **piège** contre les __comptes suspects__.\n"
    "Il est volontairement laissé **accessible** à tous.\n\n"

    "`NE PAS ÉCRIRE DANS CE SALON !`\n\n"

    "__Toute personne déclanchant le piège s'expose__ :\n"
    "➤ 🔨 A une **Expulsion immédiate** de son compte.\n"
    "➤ 🗑️ A une **Suppression** de tous ses messages\n"
    "➤ 📝 A un **signalement** dans son registre des sanctions.\n"
)


# ============================================================
# ⚒️ Fonctions utilitaires
# ============================================================

def get_piege_banner_file() -> discord.File | None:
    """Récupère la bannière du système."""
    if not os.path.exists(PIEGE_BANNER_PATH):
        return None
    return discord.File(PIEGE_BANNER_PATH, filename=PIEGE_BANNER_FILENAME)


def build_warning_view(guild_name: str, *, attach_banner: bool = False) -> discord.ui.LayoutView:
    """Création de la view d'avertissement dans le salon-piège."""

    view = discord.ui.LayoutView(timeout=None)
    container = Container()

    if attach_banner:
        container.add_item(MediaGallery(MediaGalleryItem(f"attachment://{PIEGE_BANNER_FILENAME}")))

    container.add_item(Separator())
    container.add_item(TextDisplay("# <:erreur:1495443907281031359> ATTENTION — SALON PIÈGE <:erreur:1495443907281031359>"))
    container.add_item(TextDisplay(_WARNING_MESSAGE))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


class PiegeConfigView(BaseLayoutView):
    """Panneau /mod piege : salon-piège + statut + rôles/membres ignorés."""

    def __init__(self, *, guild: discord.Guild, moderator_id: int, cfg: dict | None = None):
        super().__init__(owner_id=moderator_id, timeout=300)
        self.guild = guild
        self.moderator_id = moderator_id
        self.cfg = cfg or {
            "channel_id": None, "enabled": False, "ignored_role_ids": [], "ignored_member_ids": [],
        }
        self._build()

    @classmethod
    async def create(cls, *, guild: discord.Guild, moderator_id: int) -> "PiegeConfigView":
        cfg = await load_config(guild.id)
        return cls(guild=guild, moderator_id=moderator_id, cfg=cfg)

    # ============================================================
    # 🚧 Construction de l'interface
    # ============================================================

    def _build(self) -> None:
        self.clear_items()

        container = Container()
        container.add_item(TextDisplay(f"# {ICON_HEADER} Configuration du piège"))
        container.add_item(Separator())

        container.add_item(TextDisplay(
            "➥ Crée un __salon-piège__ contre les **comptes suspects**.\n"
            "Tout membre qui y écrit sera **expulsé automatiquement**."
        ))
        container.add_item(Separator())

        channel_id = self.cfg.get("channel_id")
        channel = self.guild.get_channel(channel_id) if channel_id else None

        if channel is not None:
            channel_display = channel.mention
            channel_btn = Button(label="Supprimer le salon", style=ButtonStyle.danger, emoji=ICON_DELETE)
            channel_btn.callback = self._on_delete_channel
        elif channel_id:
            channel_display = "`Salon introuvable`"
            channel_btn = Button(label="Recréer le salon", style=ButtonStyle.primary, emoji=ICON_PLUS)
            channel_btn.callback = self._on_create_channel
        else:
            channel_display = "`Non créé`"
            channel_btn = Button(label="Créer le salon", style=ButtonStyle.primary, emoji=ICON_PLUS)
            channel_btn.callback = self._on_create_channel

        container.add_item(Section(
            TextDisplay(f"**<:salons:1508535670333902999> Salon-piège**\n-# {channel_display}"),
            accessory=channel_btn,
        ))
        container.add_item(Separator())

        enabled = bool(self.cfg.get("enabled")) and channel is not None
        status_btn = Button(
            label="Activé" if enabled else "Désactivé",
            emoji=ICON_VALIDER if enabled else ICON_ANNULER,
            style=ButtonStyle.success if enabled else ButtonStyle.danger,
            disabled=channel is None,
        )
        status_btn.callback = self._on_toggle_enabled
        container.add_item(Section(
            TextDisplay(
                "**🔘 Statut de la détection**\n"
                "-# Suspend/réactive le système de piège."
            ),
            accessory=status_btn,
        ))
        container.add_item(Separator())

        ignored_roles = self.cfg.get("ignored_role_ids") or []
        ignored_members = self.cfg.get("ignored_member_ids") or []
        manage_btn = Button(label="Gérer la liste", style=ButtonStyle.secondary, emoji=ICON_LISTE)
        manage_btn.callback = self._on_manage_ignored
        container.add_item(Section(
            TextDisplay(
                "**🚫 Rôles & membres ignorés**\n"
                f"-# `{len(ignored_roles)}` rôle(s), `{len(ignored_members)}` membre(s)"
            ),
            accessory=manage_btn,
        ))
        container.add_item(Separator())

        btn_doc = Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚")
        container.add_item(ActionRow(btn_doc))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self.cfg = await load_config(self.guild.id)
        self._build()

        try:
            await self.push_update(interaction)

        except discord.NotFound:
            log.debug("[MOD PIEGE] Rafraîchissement du panneau ignoré : message introuvable guild=%s", self.guild.id)

            try:
                await send_ephemeral(
                    interaction,
                    error_container("Une **erreur** est survenue. Relance `/mod piege` pour afficher l'interface."))
            
            except discord.HTTPException:
                log.warning("[MOD PIEGE] Réponse de secours après NotFound en échec guild=%s", self.guild.id)

    # ============================================================
    # 💻 Callbacks
    # ============================================================

    async def _on_create_channel(self, interaction: discord.Interaction) -> None:
        me = self.guild.me
        if me is None or not self.guild.default_role:
            await send_ephemeral(interaction, error_container("Impossible de vérifier les permissions du bot."))
            return

        overwrites = {
            self.guild.default_role: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
            ),
            me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                manage_channels=True, manage_messages=True,
            ),
        }

        try:
            channel = await self.guild.create_text_channel(
                name=CHANNEL_NAME, position=0, overwrites=overwrites,
                reason=f"Configuration HoneyPot par {interaction.user}",
            )

        except discord.Forbidden:
            await send_ephemeral(interaction, error_container("**Permissions insuffisantes** pour créer ce salon."))
            return
        
        except discord.HTTPException:
            await send_ephemeral(interaction, error_container("**Erreur Discord** lors de la création du salon."))
            return

        banner_file = get_piege_banner_file()
        warning_view = build_warning_view(self.guild.name, attach_banner=banner_file is not None)

        try:
            if banner_file is not None:
                await channel.send(view=warning_view, file=banner_file)
            else:
                await channel.send(view=warning_view)

        except (discord.Forbidden, discord.HTTPException):
            log.warning("[MOD PIEGE] Message d'avertissement non envoyé guild=%s channel=%s", self.guild.id, channel.id)

        await set_channel(self.guild.id, channel.id)
        await set_enabled(self.guild.id, True)
        await self._refresh(interaction)

    async def _on_delete_channel(self, interaction: discord.Interaction) -> None:
        channel_id = self.cfg.get("channel_id")
        channel = self.guild.get_channel(channel_id) if channel_id else None

        if isinstance(channel, discord.TextChannel):
            try:
                await channel.delete(reason=f"Suppression HoneyPot par {interaction.user}")

            except (discord.Forbidden, discord.HTTPException) as exc:
                log.warning("[MOD PIEGE] Suppression salon échouée guild=%s channel=%s erreur=%s", self.guild.id, channel_id, exc)

        await set_channel(self.guild.id, None)
        await set_enabled(self.guild.id, False)
        await self._refresh(interaction)

    async def _on_toggle_enabled(self, interaction: discord.Interaction) -> None:
        current = bool(self.cfg.get("enabled"))
        await set_enabled(self.guild.id, not current)
        await self._refresh(interaction)

    async def _on_manage_ignored(self, interaction: discord.Interaction) -> None:
        view = await PiegeIgnoredListView.create(guild=self.guild, moderator_id=self.moderator_id)
        await self.push_update(interaction, view=view)