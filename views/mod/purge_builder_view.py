"""
views/mod/purge_builder_view.py — Interface de purge de salon.
"""

from __future__ import annotations

import logging

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container, success_container, warning_container
from utils.managers.mod_log_manager import log_channel_action
from utils.managers.mod_purge_manager import PurgeError
from utils.managers.mod_purge_manager import purge_channel as apply_purge
from utils.settings import settings
from views._components.base_view import BaseLayoutView
from views._components.channel_select import ChannelSelect
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

MAX_REASON_LENGTH = 500

ICON_MODIFIER = "<:modifier:1495444144712192003>"
ICON_VALIDER = "<:valider:1495444292867723284>"

CHANNEL_TYPES = [discord.ChannelType.text, discord.ChannelType.news]


class PurgeBuilderView(BaseLayoutView):
    """Panneau /mod purge : salon + raison + bouton de confirmation."""

    def __init__(self, *, guild: discord.Guild, moderator: discord.Member):
        super().__init__(owner_id=moderator.id, timeout=300)
        self.guild = guild
        self.moderator = moderator

        self.channel: discord.TextChannel | None = None
        self.reason: str | None = None

        self._build()

    def _is_complete(self) -> bool:
        return self.channel is not None

    def _build(self) -> None:
        self.clear_items()

        container = Container()
        container.add_item(TextDisplay("# <:supprimer:1495444051623809075> Purge de salon")) 
        container.add_item(Separator())

        channel_display = self.channel.mention if self.channel is not None else "`Non sélectionné`"
        select = ChannelSelect(
            placeholder="Choisir un salon", on_select=self._on_select_channel,
            channel_types=CHANNEL_TYPES,
        )
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

        btn_confirm = Button(
            label="Purger", emoji=ICON_VALIDER, style=ButtonStyle.danger,
            disabled=not self._is_complete(),
        )
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
            title="Raison de la purge",
            label="Raison (optionnelle)",
            placeholder="Explique la raison de cette purge...",
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
                view=warning_container("Veuillez sélectionner un salon avant de confirmer."),
                ephemeral=True,
            )
            return

        # 🕒 Defer AVANT la purge : clone() + edit(position=...) + delete()
        # sont 3 appels HTTP Discord distincts qui peuvent, cumulés, dépasser
        # les 3 secondes de la fenêtre de réponse initiale — exactement le
        # même risque que celui corrigé sur /mod clear (cf.
        # views/mod/clear_builder_view.py). Une fois déferré, push_update()
        # bascule automatiquement sur edit_original_response() (valide
        # ~15 min), donc les erreurs ci-dessous doivent passer par followup.
        try:
            await interaction.response.defer()
        except (discord.NotFound, discord.HTTPException):
            return

        old_channel = self.channel

        try:
            new_channel = await apply_purge(old_channel, self.moderator, reason=self.reason)
        except PurgeError as e:
            view = warning_container(e.message) if e.warning else error_container(e.message)
            await interaction.followup.send(view=view, ephemeral=True)
            return
        except Exception:
            log.exception(
                "[PURGE_BUILDER] Échec inattendu guild=%s channel=%s",
                self.guild.id, old_channel.id,
            )
            await interaction.followup.send(
                view=error_container("Une erreur inattendue est survenue lors de la **purge**."), ephemeral=True,
            )
            return

        # ⚠️ old_channel n'existe plus à partir d'ici : toute référence au
        # salon (log, message de confirmation) doit utiliser new_channel.
        await log_channel_action(
            self.guild.id, "Purge", self.moderator.id, new_channel, reason=self.reason,
        )

        confirmation = f"✅ Salon purgé avec succès par {self.moderator.mention} — historique vidé."

        # Si /mod purge a été lancé DANS le salon qu'on vient de purger (cas
        # le plus courant), le message éphémère du panneau vivait dans ce
        # salon : pour Discord, ce salon n'existe plus, donc ni
        # edit_original_response ni followup.send ne peuvent plus l'atteindre
        # (→ 404 "Unknown Message"). On confirme alors directement par un
        # petit message en texte brut dans le NOUVEAU salon, plutôt que de
        # laisser le modérateur sans retour.
        if interaction.channel_id == old_channel.id:
            try:
                await new_channel.send(confirmation)
            except discord.HTTPException:
                log.exception(
                    "[PURGE_BUILDER] Confirmation impossible dans le nouveau salon guild=%s channel=%s",
                    self.guild.id, new_channel.id,
                )
            self.stop()
            return

        # Sinon (purge d'un AUTRE salon que celui où la commande a été
        # lancée), le panneau éphémère est toujours valide : on le met à
        # jour normalement, avec le même filet de sécurité au cas où il
        # aurait disparu pour une autre raison.
        done_view = success_container(f"Salon purgé avec succès : {new_channel.mention}")
        try:
            await self.push_update(interaction, view=done_view)
        except (discord.NotFound, discord.HTTPException):
            try:
                await new_channel.send(confirmation)
            except discord.HTTPException:
                log.exception(
                    "[PURGE_BUILDER] Confirmation impossible dans le nouveau salon guild=%s channel=%s",
                    self.guild.id, new_channel.id,
                )
        self.stop()
