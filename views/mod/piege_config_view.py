"""
views/mod/piege_config_view.py — Interface de configuration du système
HoneyPot / "Piège" (/mod piege).

Contrairement à RaidProtect (dont s'inspire ce système visuellement, cf.
Paul 2026-09) : PAS de sélecteur de sanction ni de durée — la réaction est
FIXE (kick + purge + entrée /mod historique, cf.
cogs/events/honeypot_listener.py) et le panneau ne propose donc que :
  - créer/supprimer le salon-piège
  - activer/désactiver la détection sans supprimer le salon
  - gérer les rôles/membres ignorés (jamais sanctionnés par le piège)

Style aligné sur views/join_to_create/join_to_create_config_view.py et
views/mod/sanction_builder_view.py (Section+accessory par champ, icônes
maison). En-tête <:bouclier:...> réutilisé de views/mod/automod_dashboard_view.py
(même famille "protection/sécurité", même identité visuelle).
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container, send_ephemeral, warning_container
from utils.managers.honeypot_manager import load_config, set_channel, set_enabled
from utils.settings import settings
from views._components.base_view import BaseLayoutView
from views.mod.piege_ignored_view import PiegeIgnoredListView

log = logging.getLogger(__name__)

ICON_HEADER = "<:bouclier:1539013183577133106>"
ICON_PLUS = "<:plus:1495444111505752154>"
ICON_DELETE = "<:supprimer:1495444051623809075>"
ICON_VALIDER = "<:valider:1495444292867723284>"
ICON_ANNULER = "<:annuler:1495444256754761979>"
ICON_LISTE = "<:lister:1495445288364675192>"

CHANNEL_NAME = "🍯・piège"

_WARNING_MESSAGE = (
    "Ce salon sert de **piège anti-raid**. Il est intentionnellement laissé "
    "visible et accessible en écriture à **tous les membres**.\n\n"
    "**N'envoie aucun message ici** : toute personne qui le fait est "
    "automatiquement **expulsée** du serveur, ses messages sont "
    "**supprimés**, et l'action est enregistrée dans l'historique de modération."
)


def build_warning_view(guild_name: str) -> discord.ui.LayoutView:
    """Le message posté dans le salon-piège à sa création — réutilise
    warning_container pour une identité visuelle GuideOn cohérente avec le
    reste du bot, sans construire un container ad-hoc."""
    return warning_container(_WARNING_MESSAGE)


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

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.clear_items()

        container = Container()
        container.add_item(TextDisplay(f"# {ICON_HEADER} Configuration du Piège"))
        container.add_item(TextDisplay(
            "➥ Crée un __salon-piège__ (HoneyPot) : tout membre qui y écrit est "
            "**expulsé automatiquement**, ses messages **supprimés**, et l'action "
            "**enregistrée** dans `/mod historique`.\n"
            "-# Pas de sanction ni de durée à choisir : la réaction est fixe."
        ))
        container.add_item(Separator())

        # ── Salon-piège ────────────────────────────────
        channel_id = self.cfg.get("channel_id")
        channel = self.guild.get_channel(channel_id) if channel_id else None

        if channel is not None:
            channel_display = channel.mention
            channel_btn = Button(label="Supprimer le salon", style=ButtonStyle.danger, emoji=ICON_DELETE)
            channel_btn.callback = self._on_delete_channel
        elif channel_id:
            channel_display = "`Salon introuvable (supprimé manuellement ?)`"
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

        # ── Statut ─────────────────────────────────────
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
                "-# Suspend/réactive le piège sans supprimer le salon."
            ),
            accessory=status_btn,
        ))
        container.add_item(Separator())

        # ── Rôles & membres ignorés ──────────────────────
        # Gérés (ajout + suppression + liste paginée) sur un écran dédié,
        # cf. views/mod/piege_ignored_view.py — afficher chaque entrée ici
        # directement (Section+accessory par ligne) a fini par dépasser la
        # limite Discord de 40 composants/message dès qu'il y avait assez
        # de rôles/membres ignorés (cf. traceback Paul du 2026-09-16).
        ignored_roles = self.cfg.get("ignored_role_ids") or []
        ignored_members = self.cfg.get("ignored_member_ids") or []
        manage_btn = Button(label="Gérer la liste", style=ButtonStyle.secondary, emoji=ICON_LISTE)
        manage_btn.callback = self._on_manage_ignored
        container.add_item(Section(
            TextDisplay(
                "**🚫 Rôles & membres ignorés**\n"
                f"-# `{len(ignored_roles)}` rôle(s), `{len(ignored_members)}` membre(s) — "
                "jamais sanctionnés par le piège."
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
        await self.push_update(interaction)

    # ------------------------------------------------------------------
    # Callbacks — salon-piège
    # ------------------------------------------------------------------

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
            await send_ephemeral(interaction, error_container("Permissions insuffisantes pour créer ce salon."))
            return
        except discord.HTTPException:
            await send_ephemeral(interaction, error_container("Erreur Discord lors de la création du salon."))
            return

        try:
            await channel.send(view=build_warning_view(self.guild.name))
        except (discord.Forbidden, discord.HTTPException):
            log.warning("[PIEGE] Message d'avertissement non envoyé guild=%s channel=%s", self.guild.id, channel.id)

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
                log.warning("[PIEGE] Suppression salon échouée guild=%s channel=%s erreur=%s", self.guild.id, channel_id, exc)

        await set_channel(self.guild.id, None)
        await set_enabled(self.guild.id, False)
        await self._refresh(interaction)

    async def _on_toggle_enabled(self, interaction: discord.Interaction) -> None:
        current = bool(self.cfg.get("enabled"))
        await set_enabled(self.guild.id, not current)
        await self._refresh(interaction)

    # ------------------------------------------------------------------
    # Callbacks — rôles & membres ignorés
    # ------------------------------------------------------------------

    async def _on_manage_ignored(self, interaction: discord.Interaction) -> None:
        view = await PiegeIgnoredListView.create(guild=self.guild, moderator_id=self.moderator_id)
        await self.push_update(interaction, view=view)