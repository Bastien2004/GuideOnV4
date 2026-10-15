"""
views/mod/voice_manage_builder_view.py — Panneau interactif pour /mod vocal.

Zéro paramètre de commande : salon source (+ destination pour le
déplacement) choisis dans l'interface. Trois actions indépendantes,
appliquées instantanément (même pattern que views/bienvenue/config_view.py
::_state_btn pour le mute, boutons d'action directs pour déplacer/expulser),
icônes maison.

Après chaque action, un message éphémère confirme le résultat (nombre de
membres réellement affectés, ou avertissement si 0 — cf. send_ephemeral en
fin de _on_toggle_mute/_on_move/_on_disconnect) : même convention que
views/mod/clear_builder_view.py et views/mod/purge_builder_view.py, qui
affichent toujours un succès explicite après leur action finale (audit
2026-10-15 — avant ce correctif, le panneau se contentait de se rafraîchir
silencieusement, sans jamais dire au modérateur combien de membres avaient
réellement été affectés, ni s'il y en avait eu zéro à cause d'un salon vide
ou d'une permission manquante).
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container, send_ephemeral, success_container, warning_container
from utils.managers.mod_log_manager import log_channel_action
from utils.managers.mod_voice_manager import (
    VoiceManageError,
    is_channel_muted,
)
from utils.managers.mod_voice_manager import disconnect_all as apply_disconnect_all
from utils.managers.mod_voice_manager import move_all as apply_move_all
from utils.managers.mod_voice_manager import mute_all as apply_mute_all
from utils.settings import settings
from views._components.base_view import BaseLayoutView
from views._components.channel_select import ChannelSelect
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

MAX_REASON_LENGTH = 500

ICON_MODIFIER = "<:modifier:1495444144712192003>"
ICON_VALIDER = "<:valider:1495444292867723284>"
ICON_ANNULER = "<:annuler:1495444256754761979>"
ICON_SUPPRIMER = "<:supprimer:1495444051623809075>"

CHANNEL_TYPES = [discord.ChannelType.voice, discord.ChannelType.stage_voice]


def _mute_btn(muted: bool) -> Button:
    """Bouton d'état mute/démute (même pattern que bienvenue/autorole)."""
    return Button(
        label="Démute tous" if muted else "Mute tous",
        style=ButtonStyle.success if muted else ButtonStyle.danger,
        emoji=ICON_VALIDER if muted else ICON_ANNULER,
    )


class VoiceManageBuilderView(BaseLayoutView):
    """Panneau /mod vocal : salon source/destination + mute/déplacer/expulser."""

    def __init__(self, *, guild: discord.Guild, moderator_id: int):
        super().__init__(owner_id=moderator_id, timeout=300)
        self.guild = guild
        self.moderator_id = moderator_id

        self.source: discord.VoiceChannel | None = None
        self.destination: discord.VoiceChannel | None = None
        self.reason: str | None = None

        self._build()

    def _build(self) -> None:
        self.clear_items()

        container = Container()
        container.add_item(TextDisplay("# 🔊 Gestion vocale de masse"))
        container.add_item(Separator())

        source_display = (
            f"{self.source.mention} ({len(self.source.members)} membre(s))" if self.source is not None else "`Non sélectionné`"
        )
        select_source = ChannelSelect(
            placeholder="Choisir le salon source", on_select=self._on_select_source, channel_types=CHANNEL_TYPES,
        )
        container.add_item(TextDisplay(f"**📌 Salon source**\n-# {source_display}"))
        container.add_item(ActionRow(select_source))
        container.add_item(Separator())

        dest_display = self.destination.mention if self.destination is not None else "`Non sélectionné`"
        select_dest = ChannelSelect(
            placeholder="Choisir le salon destination (pour déplacer)",
            on_select=self._on_select_destination,
            channel_types=CHANNEL_TYPES,
        )
        container.add_item(TextDisplay(f"**➡️ Salon destination**\n-# {dest_display}"))
        container.add_item(ActionRow(select_dest))
        container.add_item(Separator())

        reason_display = f"« {self.reason} »" if self.reason else "`Non précisée`"
        btn_reason = Button(label="Modifier", style=ButtonStyle.secondary, emoji=ICON_MODIFIER)
        btn_reason.callback = self._on_click_reason
        container.add_item(Section(
            TextDisplay(f"**📝 Raison (optionnelle)**\n-# {reason_display}"),
            accessory=btn_reason,
        ))
        container.add_item(Separator())

        # Un salon source vide n'a personne à muter/déplacer/expulser : on désactive
        # directement les 3 boutons d'action plutôt que de laisser cliquer pour
        # découvrir "0 membre affecté" (même logique que can_move ci-dessous, qui
        # désactive déjà "Déplacer" quand source == destination).
        has_source_members = self.source is not None and len(self.source.members) > 0

        if self.source is None:
            btn_mute = _mute_btn(False)
            btn_mute.disabled = True
        else:
            btn_mute = _mute_btn(is_channel_muted(self.source))
            btn_mute.disabled = not has_source_members
        btn_mute.callback = self._on_toggle_mute
        container.add_item(Section(
            TextDisplay("**🔇 Mute serveur**\n-# Mute/démute tous les membres présents dans le salon source."),
            accessory=btn_mute,
        ))
        container.add_item(Separator())

        can_move = (
            has_source_members
            and self.destination is not None
            and self.source.id != self.destination.id
        )
        btn_move = Button(label="Déplacer tous", style=ButtonStyle.primary, disabled=not can_move)
        btn_move.callback = self._on_move
        container.add_item(Section(
            TextDisplay("**🚚 Déplacer tous les membres**\n-# Vers le salon destination sélectionné."),
            accessory=btn_move,
        ))
        container.add_item(Separator())

        btn_disconnect = Button(
            label="Expulser tous", style=ButtonStyle.danger, emoji=ICON_SUPPRIMER, disabled=not has_source_members,
        )
        btn_disconnect.callback = self._on_disconnect
        container.add_item(Section(
            TextDisplay("**🚪 Expulser tous les membres**\n-# Déconnecte tous les membres du salon source."),
            accessory=btn_disconnect,
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

    async def _on_select_source(self, interaction: discord.Interaction, channel_id: int) -> None:
        channel = self.guild.get_channel(channel_id)
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            await interaction.response.send_message(
                view=error_container("Ce salon n'est pas un salon vocal valide."), ephemeral=True,
            )
            return
        self.source = channel
        await self._refresh(interaction)

    async def _on_select_destination(self, interaction: discord.Interaction, channel_id: int) -> None:
        channel = self.guild.get_channel(channel_id)
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            await interaction.response.send_message(
                view=error_container("Ce salon n'est pas un salon vocal valide."), ephemeral=True,
            )
            return
        self.destination = channel
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
            title="Raison de l'action",
            label="Raison (optionnelle)",
            placeholder="Explique la raison de cette action...",
            default=self.reason or "",
            required=False,
            max_length=MAX_REASON_LENGTH,
            style=discord.TextStyle.paragraph,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _on_toggle_mute(self, interaction: discord.Interaction) -> None:
        if self.source is None:
            await interaction.response.send_message(
                view=warning_container("Veuillez sélectionner un salon source avant de continuer."), ephemeral=True,
            )
            return
        if not self.source.members:
            # Filet de sécurité : le bouton est normalement déjà désactivé dans ce
            # cas (cf. has_source_members dans _build), mais le message affiché
            # peut être légèrement périmé si tout le monde vient de quitter.
            await interaction.response.send_message(
                view=warning_container(f"Le salon {self.source.mention} est vide : personne à muter/démuter."),
                ephemeral=True,
            )
            return

        channel = self.source
        target_mute = not is_channel_muted(channel)
        try:
            count = await apply_mute_all(channel, mute=target_mute, reason=self.reason)
        except Exception:
            log.exception("[VOICE_BUILDER] Échec mute guild=%s channel=%s", self.guild.id, channel.id)
            await interaction.response.send_message(
                view=error_container("Une erreur inattendue est survenue pendant le mute."), ephemeral=True,
            )
            return

        action_label = "Mute vocal de masse" if target_mute else "Démute vocal de masse"
        await log_channel_action(
            self.guild.id, action_label, self.moderator_id, channel,
            reason=self.reason, extra=f"{count} membre(s) affecté(s)",
        )
        await self._refresh(interaction)

        # Confirmation explicite du résultat (même convention que /mod clear et
        # /mod purge) : sans ça, un modérateur dont l'action échoue entièrement
        # (permission manquante) n'avait aucun moyen de le savoir — le panneau se
        # rafraîchissait silencieusement comme en cas de succès.
        verbe = "mutés" if target_mute else "démutés"
        if count > 0:
            await send_ephemeral(interaction, success_container(f"✅ **{count}** membre(s) {verbe} dans {channel.mention}."))
        else:
            await send_ephemeral(
                interaction,
                warning_container(
                    f"Aucun membre n'a pu être {'mute' if target_mute else 'démute'} dans {channel.mention} — "
                    f"vérifie ma permission **Muter les membres** dans ce salon."
                ),
            )

    async def _on_move(self, interaction: discord.Interaction) -> None:
        if self.source is None or self.destination is None:
            await interaction.response.send_message(
                view=warning_container("Veuillez sélectionner un salon source et un salon destination."), ephemeral=True,
            )
            return
        if not self.source.members:
            # Filet de sécurité, cf. _on_toggle_mute.
            await interaction.response.send_message(
                view=warning_container(f"Le salon {self.source.mention} est vide : personne à déplacer."),
                ephemeral=True,
            )
            return

        channel, destination = self.source, self.destination
        try:
            count = await apply_move_all(channel, destination, reason=self.reason)
        except VoiceManageError as e:
            view = warning_container(e.message) if e.warning else error_container(e.message)
            await interaction.response.send_message(view=view, ephemeral=True)
            return
        except Exception:
            log.exception("[VOICE_BUILDER] Échec déplacement guild=%s channel=%s", self.guild.id, channel.id)
            await interaction.response.send_message(
                view=error_container("Une erreur inattendue est survenue pendant le déplacement."), ephemeral=True,
            )
            return

        await log_channel_action(
            self.guild.id, "Déplacement vocal de masse", self.moderator_id, channel,
            reason=self.reason, extra=f"{count} membre(s) déplacé(s) vers {destination.mention}",
        )
        await self._refresh(interaction)

        if count > 0:
            await send_ephemeral(interaction, success_container(f"✅ **{count}** membre(s) déplacé(s) vers {destination.mention}."))
        else:
            await send_ephemeral(
                interaction,
                warning_container(
                    f"Aucun membre n'a pu être déplacé vers {destination.mention} — vérifie ma permission "
                    f"**Déplacer les membres**, ou si le salon destination est plein."
                ),
            )

    async def _on_disconnect(self, interaction: discord.Interaction) -> None:
        if self.source is None:
            await interaction.response.send_message(
                view=warning_container("Veuillez sélectionner un salon source avant de continuer."), ephemeral=True,
            )
            return
        if not self.source.members:
            # Filet de sécurité, cf. _on_toggle_mute.
            await interaction.response.send_message(
                view=warning_container(f"Le salon {self.source.mention} est vide : personne à expulser."),
                ephemeral=True,
            )
            return

        channel = self.source
        try:
            count = await apply_disconnect_all(channel, reason=self.reason)
        except Exception:
            log.exception("[VOICE_BUILDER] Échec expulsion guild=%s channel=%s", self.guild.id, channel.id)
            await interaction.response.send_message(
                view=error_container("Une erreur inattendue est survenue pendant l'expulsion."), ephemeral=True,
            )
            return

        await log_channel_action(
            self.guild.id, "Expulsion vocale de masse", self.moderator_id, channel,
            reason=self.reason, extra=f"{count} membre(s) déconnecté(s)",
        )
        await self._refresh(interaction)

        if count > 0:
            await send_ephemeral(interaction, success_container(f"✅ **{count}** membre(s) déconnecté(s) de {channel.mention}."))
        else:
            await send_ephemeral(
                interaction,
                warning_container(
                    f"Aucun membre n'a pu être déconnecté de {channel.mention} — vérifie ma permission "
                    f"**Déplacer les membres** dans ce salon."
                ),
            )