"""
views/mod/clear_builder_view.py — Panneau interactif pour /mod clear.

Zéro paramètre de commande : salon, nombre de messages et filtre optionnel
choisis entièrement dans l'interface, même style que SanctionBuilderView/
RenameBuilderView (Section+accessory, icônes maison).
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container, success_container, warning_container
from utils.managers.mod_clear_manager import (
    MAX_CLEAR_AMOUNT,
    MIN_CLEAR_AMOUNT,
    ClearError,
)
from utils.managers.mod_clear_manager import clear_messages as apply_clear
from utils.managers.mod_log_manager import log_channel_action
from utils.settings import settings
from views._components.base_view import BaseLayoutView
from views._components.channel_select import ChannelSelect
from views._components.text_modal import TextModal
from views._components.user_select import UserSelect

log = logging.getLogger(__name__)

MAX_REASON_LENGTH = 500

ICON_MODIFIER = "<:modifier:1495444144712192003>"
ICON_VALIDER = "<:valider:1495444292867723284>"

CHANNEL_TYPES = [discord.ChannelType.text, discord.ChannelType.news]


class ClearBuilderView(BaseLayoutView):
    """Panneau /mod clear : salon + nombre de messages + filtre + raison."""

    def __init__(self, *, guild: discord.Guild, moderator_id: int):
        super().__init__(owner_id=moderator_id, timeout=300)
        self.guild = guild
        self.moderator_id = moderator_id

        self.channel: discord.TextChannel | None = None
        self.amount: int | None = None
        self.author_filter_id: int | None = None
        self.reason: str | None = None

        self._build()

    def _is_complete(self) -> bool:
        return self.channel is not None and self.amount is not None

    def _build(self) -> None:
        self.clear_items()

        container = Container()
        container.add_item(TextDisplay("# 🧹 Clear"))
        container.add_item(Separator())

        channel_display = self.channel.mention if self.channel is not None else "`Non sélectionné`"
        select = ChannelSelect(placeholder="Choisir un salon", on_select=self._on_select_channel, channel_types=CHANNEL_TYPES)
        container.add_item(TextDisplay(f"**📌 Salon**\n-# {channel_display}"))
        container.add_item(ActionRow(select))
        container.add_item(Separator())

        amount_display = f"{self.amount} message(s)" if self.amount is not None else "`Non défini`"
        btn_amount = Button(label="Modifier", style=ButtonStyle.secondary, emoji=ICON_MODIFIER)
        btn_amount.callback = self._on_click_amount
        container.add_item(Section(
            TextDisplay(f"**🔢 Nombre de messages**\n-# {amount_display}"),
            accessory=btn_amount,
        ))
        container.add_item(Separator())

        filter_display = f"<@{self.author_filter_id}>" if self.author_filter_id is not None else "`Aucun filtre`"
        filter_select = UserSelect(
            placeholder="Filtrer sur un membre (optionnel)",
            on_select=self._on_select_filter,
            min_values=0,
        )
        container.add_item(TextDisplay(f"**🎯 Filtrer par membre (optionnel)**\n-# {filter_display}"))
        container.add_item(ActionRow(filter_select))
        container.add_item(Separator())

        reason_display = f"« {self.reason} »" if self.reason else "`Non précisée`"
        btn_reason = Button(label="Modifier", style=ButtonStyle.secondary, emoji=ICON_MODIFIER)
        btn_reason.callback = self._on_click_reason
        container.add_item(Section(
            TextDisplay(f"**📝 Raison (optionnelle)**\n-# {reason_display}"),
            accessory=btn_reason,
        ))
        container.add_item(Separator())

        btn_confirm = Button(label="Confirmer", emoji=ICON_VALIDER, style=ButtonStyle.danger, disabled=not self._is_complete())
        btn_confirm.callback = self._on_confirm
        btn_doc = Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚")
        container.add_item(ActionRow(btn_confirm, btn_doc))

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

    async def _on_select_filter(self, interaction: discord.Interaction, ids: list[int]) -> None:
        self.author_filter_id = ids[0] if ids else None
        await self._refresh(interaction)

    async def _on_click_amount(self, interaction: discord.Interaction) -> None:
        async def on_submit(inter: discord.Interaction, value: str) -> None:
            value = value.strip()
            if not value.isdigit():
                await inter.response.send_message(
                    view=warning_container("Le nombre de messages doit être un nombre entier."), ephemeral=True,
                )
                return
            amount = int(value)
            if not (MIN_CLEAR_AMOUNT <= amount <= MAX_CLEAR_AMOUNT):
                await inter.response.send_message(
                    view=warning_container(
                        f"Le nombre de messages doit être compris entre **{MIN_CLEAR_AMOUNT}** et **{MAX_CLEAR_AMOUNT}**."
                    ),
                    ephemeral=True,
                )
                return
            self.amount = amount
            await self._refresh(inter)

        modal = TextModal(
            title="Nombre de messages",
            label="Nombre de messages à supprimer",
            placeholder=f"Entre {MIN_CLEAR_AMOUNT} et {MAX_CLEAR_AMOUNT}",
            default=str(self.amount) if self.amount is not None else "",
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

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
            title="Raison du clear",
            label="Raison (optionnelle)",
            placeholder="Explique la raison de cette suppression...",
            default=self.reason or "",
            required=False,
            max_length=MAX_REASON_LENGTH,
            style=discord.TextStyle.paragraph,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        if not self._is_complete():
            await interaction.response.send_message(
                view=warning_container("Veuillez sélectionner un salon et un nombre de messages avant de confirmer."),
                ephemeral=True,
            )
            return

        author_filter = self.guild.get_member(self.author_filter_id) if self.author_filter_id is not None else None

        try:
            deleted = await apply_clear(self.channel, self.amount, author_filter=author_filter)
        except ClearError as e:
            view = warning_container(e.message) if e.warning else error_container(e.message)
            await interaction.response.send_message(view=view, ephemeral=True)
            return
        except Exception:
            log.exception("[CLEAR_BUILDER] Échec inattendu guild=%s channel=%s", self.guild.id, self.channel.id)
            await interaction.response.send_message(
                view=error_container("Une erreur inattendue est survenue lors du **clear**."), ephemeral=True,
            )
            return

        extra = f"Filtré sur <@{self.author_filter_id}>" if self.author_filter_id is not None else None
        await log_channel_action(
            self.guild.id, "Clear", self.moderator_id, self.channel,
            reason=self.reason, extra=extra,
        )

        done_view = success_container(f"**{deleted}** message(s) supprimé(s) dans {self.channel.mention}.")
        await self.push_update(interaction, view=done_view)
        self.stop()