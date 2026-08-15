"""
views/mod/unlock_builder_view.py — Panneau interactif pour /mod unlock.

Déverrouillage uniquement. Le verrouillage est traité par /mod lock
(views/mod/lock_builder_view.py). Même pattern que LockBuilderView pour
rester cohérent (Section, ChannelSelect, raison optionnelle).
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container, warning_container
from utils.managers.mod_channel_lock_manager import LockError, is_locked, unlock_channel
from utils.managers.mod_log_manager import log_channel_action
from utils.settings import settings
from views._components.base_view import BaseLayoutView
from views._components.channel_select import ChannelSelect
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

MAX_REASON_LENGTH = 500

ICON_MODIFIER = "<:modifier:1495444144712192003>"
ICON_VALIDER = "<:valider:1495444292867723284>"

CHANNEL_TYPES = [discord.ChannelType.text, discord.ChannelType.news]


class UnlockBuilderView(BaseLayoutView):
    """Panneau /mod unlock : salon + raison + bouton de déverrouillage."""

    def __init__(self, *, guild: discord.Guild, moderator: discord.Member):
        super().__init__(owner_id=moderator.id, timeout=300)
        self.guild = guild
        self.moderator = moderator

        self.channel: discord.TextChannel | None = None
        self.reason: str | None = None

        self._build()

    def _build(self) -> None:
        self.clear_items()

        container = Container()
        container.add_item(TextDisplay("# 🔓 Déverrouillage de salon"))
        container.add_item(Separator())

        # ── Salon ─────────────────────────────────────────
        channel_display = self.channel.mention if self.channel is not None else "`Non sélectionné`"
        select = ChannelSelect(
            placeholder="Choisir un salon", on_select=self._on_select_channel,
            channel_types=CHANNEL_TYPES,
        )
        container.add_item(TextDisplay(f"**📌 Salon**\n-# {channel_display}"))
        container.add_item(ActionRow(select))
        container.add_item(Separator())

        # ── Raison ───────────────────────────────────────
        reason_display = f"« {self.reason} »" if self.reason else "`Non précisée`"
        btn_reason = Button(label="Modifier", style=ButtonStyle.secondary, emoji=ICON_MODIFIER)
        btn_reason.callback = self._on_click_reason
        container.add_item(Section(
            TextDisplay(f"**📝 Raison (optionnelle)**\n-# {reason_display}"),
            accessory=btn_reason,
        ))
        container.add_item(Separator())

        # ── Actions ──────────────────────────────────────
        # Le bouton reflète l'état : disabled si pas de salon ou déjà déverrouillé.
        if self.channel is None:
            btn_unlock = Button(
                label="Déverrouiller", style=ButtonStyle.success,
                emoji=ICON_VALIDER, disabled=True,
            )
        elif not is_locked(self.channel):
            btn_unlock = Button(
                label="Non verrouillé", style=ButtonStyle.secondary,
                emoji="🔓", disabled=True,
            )
        else:
            btn_unlock = Button(
                label="Déverrouiller", style=ButtonStyle.success, emoji=ICON_VALIDER,
            )
        btn_unlock.callback = self._on_unlock

        btn_doc = Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚")
        container.add_item(ActionRow(btn_unlock, btn_doc))

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
                view=error_container("Ce salon n'est pas un salon textuel valide."),
                ephemeral=True,
            )
            return
        self.channel = channel
        await self._refresh(interaction)

    async def _on_click_reason(self, interaction: discord.Interaction) -> None:
        async def on_submit(inter: discord.Interaction, value: str) -> None:
            value = value.strip()
            if len(value) > MAX_REASON_LENGTH:
                await inter.response.send_message(
                    view=warning_container(
                        f"La raison doit contenir au maximum **{MAX_REASON_LENGTH} caractères**."
                    ),
                    ephemeral=True,
                )
                return
            self.reason = value or None
            await self._refresh(inter)

        modal = TextModal(
            title="Raison du déverrouillage",
            label="Raison (optionnelle)",
            placeholder="Explique la raison de cette action...",
            default=self.reason or "",
            required=False,
            max_length=MAX_REASON_LENGTH,
            style=discord.TextStyle.paragraph,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _on_unlock(self, interaction: discord.Interaction) -> None:
        if self.channel is None:
            await interaction.response.send_message(
                view=warning_container("Veuillez sélectionner un salon avant de continuer."),
                ephemeral=True,
            )
            return

        try:
            await unlock_channel(self.channel, self.moderator, reason=self.reason)
        except LockError as e:
            view = warning_container(e.message) if e.warning else error_container(e.message)
            await interaction.response.send_message(view=view, ephemeral=True)
            return
        except Exception:
            log.exception(
                "[UNLOCK_BUILDER] Échec inattendu guild=%s channel=%s",
                self.guild.id, self.channel.id,
            )
            await interaction.response.send_message(
                view=error_container("Une erreur inattendue est survenue lors du **déverrouillage**."),
                ephemeral=True,
            )
            return

        await log_channel_action(
            self.guild.id, "Déverrouillage", self.moderator.id, self.channel, reason=self.reason,
        )
        await self._refresh(interaction)