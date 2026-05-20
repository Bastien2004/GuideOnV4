"""Bouton qui ouvre un modal pour saisir le titre du panel."""
from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from views._components.text_modal import TextModal

if TYPE_CHECKING:
    from cogs.ticket._state import TicketPanelDraft
    from views.ticket.panel_setup_view import PanelSetupView


class TitleButton(discord.ui.Button):
    def __init__(self, draft: "TicketPanelDraft", *, parent: "PanelSetupView", row: int):
        self._draft = draft
        self._parent = parent
        super().__init__(
            label="📝 Titre",
            style=discord.ButtonStyle.secondary,
            custom_id="ticket_setup_title_btn",
            row=row,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        modal = TextModal(
            title="Titre du panel",
            label="Titre affiché aux utilisateurs",
            placeholder="Ex : Support · Aide · Signalement",
            default=self._draft.title or "",
            min_length=1,
            max_length=100,
            on_submit=self._on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _on_submit(self, interaction: discord.Interaction, value: str) -> None:
        self._draft.title = value
        await self._parent.refresh(interaction)
