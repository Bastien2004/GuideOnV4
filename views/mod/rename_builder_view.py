"""
views/mod/rename_builder_view.py — Panneau interactif pour /mod rename.

Zéro paramètre de commande : cible et nouveau pseudo choisis entièrement
dans l'interface, même style que SanctionBuilderView (Section+accessory,
icônes maison).
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container, success_container, warning_container
from utils.managers.mod_rename_manager import MAX_NICKNAME_LENGTH, RenameError
from utils.managers.mod_rename_manager import rename_member as apply_rename
from utils.mod_hierarchy import validate_sanction_target
from utils.settings import settings
from views._components.base_view import BaseLayoutView
from views._components.text_modal import TextModal
from views._components.user_select import UserSelect

log = logging.getLogger(__name__)

MIN_REASON_LENGTH = 3
MAX_REASON_LENGTH = 500

ICON_MODIFIER = "<:modifier:1495444144712192003>"
ICON_VALIDER = "<:valider:1495444292867723284>"


class RenameBuilderView(BaseLayoutView):
    """Panneau /mod rename : cible + nouveau pseudo + raison + confirmation."""

    def __init__(self, *, guild: discord.Guild, moderator_id: int):
        super().__init__(owner_id=moderator_id, timeout=300)
        self.guild = guild
        self.moderator_id = moderator_id

        self.target: discord.Member | None = None
        self.new_nickname: str | None = None
        self.nickname_set = False
        self.reason: str | None = None

        self._build()

    def _is_complete(self) -> bool:
        return self.target is not None and self.nickname_set and bool(self.reason)

    def _build(self) -> None:
        self.clear_items()

        container = Container()
        container.add_item(TextDisplay("# 🖊️ Renommer"))
        container.add_item(Separator())

        target_display = self.target.mention if self.target is not None else "`Non sélectionnée`"
        select = UserSelect(placeholder="Choisir un membre", on_select=self._on_select_target)
        container.add_item(TextDisplay(f"**🎯 Cible**\n-# {target_display}"))
        container.add_item(ActionRow(select))
        container.add_item(Separator())

        if not self.nickname_set:
            nick_display = "`Non défini`"
        elif self.new_nickname is None:
            nick_display = "`Réinitialisation (retour au nom Discord)`"
        else:
            nick_display = f"« {self.new_nickname} »"
        btn_nick = Button(label="Modifier", style=ButtonStyle.secondary, emoji=ICON_MODIFIER)
        btn_nick.callback = self._on_click_nickname
        container.add_item(Section(
            TextDisplay(f"**🖊️ Nouveau pseudo**\n-# {nick_display}"),
            accessory=btn_nick,
        ))
        container.add_item(Separator())

        reason_display = f"« {self.reason} »" if self.reason else "`Non définie`"
        btn_reason = Button(label="Modifier", style=ButtonStyle.secondary, emoji=ICON_MODIFIER)
        btn_reason.callback = self._on_click_reason
        container.add_item(Section(
            TextDisplay(f"**📝 Raison**\n-# {reason_display}"),
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

    async def _on_select_target(self, interaction: discord.Interaction, ids: list[int]) -> None:
        member = self.guild.get_member(ids[0])
        if member is None:
            try:
                member = await self.guild.fetch_member(ids[0])
            except discord.NotFound:
                await interaction.response.send_message(
                    view=error_container("Ce membre ne semble plus être sur ce serveur."), ephemeral=True,
                )
                return
            except discord.HTTPException:
                await interaction.response.send_message(
                    view=error_container("Impossible de récupérer ce membre."), ephemeral=True,
                )
                return

        refus = validate_sanction_target(interaction, member)
        if refus is not None:
            await interaction.response.send_message(view=warning_container(refus), ephemeral=True)
            return

        self.target = member
        await self._refresh(interaction)

    async def _on_click_nickname(self, interaction: discord.Interaction) -> None:
        async def on_submit(inter: discord.Interaction, value: str) -> None:
            value = value.strip()
            if len(value) > MAX_NICKNAME_LENGTH:
                await inter.response.send_message(
                    view=warning_container(f"Le pseudo doit contenir au maximum **{MAX_NICKNAME_LENGTH} caractères**."),
                    ephemeral=True,
                )
                return
            self.new_nickname = value or None
            self.nickname_set = True
            await self._refresh(inter)

        modal = TextModal(
            title="Nouveau pseudo",
            label="Pseudo (laisser vide pour réinitialiser)",
            placeholder="Nouveau pseudo, ou vide pour revenir au nom Discord",
            default=self.new_nickname or "",
            required=False,
            max_length=MAX_NICKNAME_LENGTH,
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _on_click_reason(self, interaction: discord.Interaction) -> None:
        async def on_submit(inter: discord.Interaction, value: str) -> None:
            value = value.strip()
            if len(value) < MIN_REASON_LENGTH:
                await inter.response.send_message(
                    view=warning_container(f"La raison doit contenir au moins **{MIN_REASON_LENGTH} caractères**."),
                    ephemeral=True,
                )
                return
            if len(value) > MAX_REASON_LENGTH:
                await inter.response.send_message(
                    view=warning_container(f"La raison doit contenir au maximum **{MAX_REASON_LENGTH} caractères**."),
                    ephemeral=True,
                )
                return
            self.reason = value
            await self._refresh(inter)

        modal = TextModal(
            title="Raison du renommage",
            label="Raison",
            placeholder="Explique la raison de ce renommage...",
            default=self.reason or "",
            min_length=MIN_REASON_LENGTH,
            max_length=MAX_REASON_LENGTH,
            style=discord.TextStyle.paragraph,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        if not self._is_complete():
            await interaction.response.send_message(
                view=warning_container("Veuillez compléter tous les champs requis avant de confirmer."),
                ephemeral=True,
            )
            return

        refus = validate_sanction_target(interaction, self.target)
        if refus is not None:
            await interaction.response.send_message(view=warning_container(refus), ephemeral=True)
            return

        try:
            result = await apply_rename(self.target, self.new_nickname, self.moderator_id, self.reason)
        except RenameError as e:
            view = warning_container(e.message) if e.warning else error_container(e.message)
            await interaction.response.send_message(view=view, ephemeral=True)
            return
        except Exception:
            log.exception("[RENAME_BUILDER] Échec inattendu guild=%s user=%s", self.guild.id, self.target.id)
            await interaction.response.send_message(
                view=error_container("Une erreur inattendue est survenue lors du **renommage**."), ephemeral=True,
            )
            return

        done_view = success_container(
            f"**{self.target.mention}** a été renommé en **{result['new_nickname']}**.\n-# Raison : {self.reason}"
        )
        await self.push_update(interaction, view=done_view)
        self.stop()