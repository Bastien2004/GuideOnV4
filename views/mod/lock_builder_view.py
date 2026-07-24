"""
views/mod/lock_builder_view.py — Panneau interactif pour /mod lock.

Zéro paramètre de commande : salon choisi dans l'interface, verrouillage/
déverrouillage appliqué instantanément via un bouton d'état (même pattern
que views/bienvenue/config_view.py::_state_btn), icônes maison.
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container, warning_container
from utils.managers.mod_channel_lock_manager import LockError, is_locked
from utils.managers.mod_channel_lock_manager import set_channel_lock as apply_lock
from utils.managers.mod_log_manager import log_channel_action
from utils.settings import settings
from views._components.base_view import BaseLayoutView
from views._components.channel_select import ChannelSelect
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

MAX_REASON_LENGTH = 500

ICON_MODIFIER = "<:modifier:1495444144712192003>"
ICON_VALIDER = "<:valider:1495444292867723284>"
ICON_ANNULER = "<:annuler:1495444256754761979>"

CHANNEL_TYPES = [discord.ChannelType.text, discord.ChannelType.news]


def _state_btn(locked: bool) -> Button:
    """Bouton d'état verrouillé/déverrouillé (même pattern que bienvenue/autorole)."""
    return Button(
        label="Déverrouiller" if locked else "Verrouiller",
        style=ButtonStyle.success if locked else ButtonStyle.danger,
        emoji=ICON_VALIDER if locked else ICON_ANNULER,
    )


class LockBuilderView(BaseLayoutView):
    """Panneau /mod lock : salon + raison + bouton d'état verrouillé/déverrouillé."""

    def __init__(self, *, guild: discord.Guild, moderator_id: int):
        super().__init__(owner_id=moderator_id, timeout=300)
        self.guild = guild
        self.moderator_id = moderator_id

        self.channel: discord.TextChannel | None = None
        self.reason: str | None = None

        self._build()

    def _build(self) -> None:
        self.clear_items()

        container = Container()
        container.add_item(TextDisplay("# 🔒 Verrouillage de salon"))
        container.add_item(Separator())

        channel_display = self.channel.mention if self.channel is not None else "`Non sélectionné`"
        select = ChannelSelect(placeholder="Choisir un salon", on_select=self._on_select_channel, channel_types=CHANNEL_TYPES)
        container.add_item(TextDisplay(f"**📌 Salon**\n-# {channel_display}"))
        container.add_item(ActionRow(select))
        container.add_item(Separator())

        reason_display = f"« {self.reason} »" if self.reason else "`Non précisée`"
        btn_reason = Button(label="Modifier", style=ButtonStyle.secondary, emoji=ICON_MODIFIER)
        btn_reason.callback = self._on_click_reason
        container.add_item(Section(
            TextDisplay(f"**📝 Raison (optionnelle)**\n-# {reason_display}"),
            accessory=btn_reason,
        ))
        container.add_item(Separator())

        if self.channel is None:
            state_display = "`Sélectionnez un salon`"
            btn_toggle = _state_btn(False)
            btn_toggle.disabled = True
        else:
            locked = is_locked(self.channel)
            state_display = "🔴 Verrouillé" if locked else "🟢 Déverrouillé"
            btn_toggle = _state_btn(locked)
        btn_toggle.callback = self._on_toggle
        container.add_item(Section(
            TextDisplay(f"**🔘 Statut actuel**\n-# {state_display}"),
            accessory=btn_toggle,
        ))

        container.add_item(Separator())
        btn_doc = Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚")
        container.add_item(ActionRow(btn_doc))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self._build()
        await self.push_update(interaction)

    async def _on_select_channel(self, interaction: discord.Interaction, channel_id: int) -> None:
        channel = self.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                view=error_container("Ce salon n'est pas un salon textuel valide."), ephemeral=True,
            )
            return
        self.channel = channel
        await self._refresh(interaction)

    async def _on_click_reason(self, interaction: discord.Interaction) -> None:
        async def on_submit(inter: discord.Interaction, value: str) -> None:
            value = value.strip()
            if len(value) > MAX_REASON_LENGTH:
                await inter.response.send_message(
                    view=warning_container(f"La raison doit contenir au maximum **{MAX_REASON_LENGTH} caractères**."),
                    ephemeral=True,
                )
                return
            self.reason = value or None
            await self._refresh(inter)

        modal = TextModal(
            title="Raison du verrouillage",
            label="Raison (optionnelle)",
            placeholder="Explique la raison de cette action...",
            default=self.reason or "",
            required=False,
            max_length=MAX_REASON_LENGTH,
            style=discord.TextStyle.paragraph,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _on_toggle(self, interaction: discord.Interaction) -> None:
        if self.channel is None:
            await interaction.response.send_message(
                view=warning_container("Veuillez sélectionner un salon avant de continuer."), ephemeral=True,
            )
            return

        currently_locked = is_locked(self.channel)
        target_locked = not currently_locked

        try:
            await apply_lock(self.channel, target_locked, reason=self.reason)
        except LockError as e:
            view = warning_container(e.message) if e.warning else error_container(e.message)
            await interaction.response.send_message(view=view, ephemeral=True)
            return
        except Exception:
            log.exception("[LOCK_BUILDER] Échec inattendu guild=%s channel=%s", self.guild.id, self.channel.id)
            await interaction.response.send_message(
                view=error_container("Une erreur inattendue est survenue lors du **verrouillage**."), ephemeral=True,
            )
            return

        action_label = "Verrouillage" if target_locked else "Déverrouillage"
        await log_channel_action(self.guild.id, action_label, self.moderator_id, self.channel, reason=self.reason)

        await self._refresh(interaction)