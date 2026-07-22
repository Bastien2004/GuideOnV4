"""
views/mod/_revocation_common.py — Sous-etape commune "raison optionnelle +
confirmation" pour /mod unban, /mod unmute, /mod unwarn.

Factorise le panneau de confirmation partage par les trois vues de
selection specialisees (unban_select_view / unmute_select_view /
unwarn_select_view), qui different uniquement par la maniere dont la
cible est listee (bannis Discord / mutes actifs / warns actifs).

Style aligne sur views/bienvenue/config_view.py : Section(TextDisplay, accessory=Button)
par champ, icones maison (modifier/valider/retour) plutot que des emojis unicode.
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container, success_container, warning_container
from utils.managers.mod_sanction_manager import SanctionError
from views._components.base_view import BaseLayoutView
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

MAX_REVOKE_REASON_LENGTH = 500

# Icones maison — cohérence avec views/bienvenue et views/autorole.
ICON_MODIFIER = "<:modifier:1495444144712192003>"
ICON_VALIDER = "<:valider:1495444292867723284>"
ICON_RETOUR = "<:retour:1515658955190308995>"

RevokeAction = Callable[[str | None], Awaitable[dict]]
BuildBackView = Callable[[], Awaitable[discord.ui.View]]


class RevocationConfirmView(BaseLayoutView):
    """Confirme la revocation d'une sanction (unban/unmute/unwarn), raison optionnelle."""

    def __init__(
        self,
        *,
        title: str,
        target_display: str,
        moderator_id: int,
        on_confirm: RevokeAction,
        build_back_view: BuildBackView,
        action_label: str = "révocation",
    ):
        super().__init__(owner_id=moderator_id, timeout=180)
        self._title = title
        self._target_display = target_display
        self._on_confirm = on_confirm
        self._build_back_view = build_back_view
        self._action_label = action_label
        self.reason: str | None = None
        self._build()

    def _build(self) -> None:
        self.clear_items()
        container = Container()
        container.add_item(TextDisplay(f"# {self._title}"))
        container.add_item(Separator())

        container.add_item(TextDisplay(f"**🎯 Cible**\n-# {self._target_display}"))
        container.add_item(Separator())

        reason_display = f"« {self.reason} »" if self.reason else "`Aucune (optionnel)`"
        btn_reason = Button(label="Modifier", style=ButtonStyle.secondary, emoji=ICON_MODIFIER)
        btn_reason.callback = self._on_click_reason
        container.add_item(Section(
            TextDisplay(f"**📝 Raison**\n-# {reason_display}"),
            accessory=btn_reason,
        ))
        container.add_item(Separator())

        btn_confirm = Button(label="Confirmer", emoji=ICON_VALIDER, style=ButtonStyle.danger)
        btn_confirm.callback = self._on_confirm_click
        btn_back = Button(label="Retour", emoji=ICON_RETOUR, style=ButtonStyle.secondary)
        btn_back.callback = self._on_back
        container.add_item(ActionRow(btn_confirm, btn_back))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self._build()
        await self.push_update(interaction)

    async def _on_click_reason(self, interaction: discord.Interaction) -> None:
        async def on_submit(inter: discord.Interaction, value: str) -> None:
            value = value.strip()
            if len(value) > MAX_REVOKE_REASON_LENGTH:
                await inter.response.send_message(
                    view=warning_container(
                        f"La raison doit contenir au maximum **{MAX_REVOKE_REASON_LENGTH} caractères**."
                    ),
                    ephemeral=True,
                )
                return
            self.reason = value or None
            await self._refresh(inter)

        modal = TextModal(
            title="Raison (optionnel)",
            label="Raison de la révocation",
            placeholder="Laisser vide si aucune raison particulière",
            default=self.reason or "",
            required=False,
            max_length=MAX_REVOKE_REASON_LENGTH,
            style=discord.TextStyle.paragraph,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _on_back(self, interaction: discord.Interaction) -> None:
        back_view = await self._build_back_view()
        await self.push_update(interaction, view=back_view)

    async def _on_confirm_click(self, interaction: discord.Interaction) -> None:
        try:
            result = await self._on_confirm(self.reason)
        except SanctionError as e:
            view = warning_container(e.message) if e.warning else error_container(e.message)
            await interaction.response.send_message(view=view, ephemeral=True)
            return
        except Exception:
            log.exception("[REVOCATION] Échec inattendu lors de la %s", self._action_label)
            await interaction.response.send_message(
                view=error_container(f"Une erreur inattendue est survenue lors de la **{self._action_label}**."),
                ephemeral=True,
            )
            return

        done_view = success_container(f"La **{self._action_label}** a bien été appliquée (`#{result['id']}`).")
        await self.push_update(interaction, view=done_view)
        self.stop()
