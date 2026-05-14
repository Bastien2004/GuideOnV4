"""Bouton qui ouvre un modal pour saisir la description du panel."""
from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from views.components.text_modal import TextModal

if TYPE_CHECKING:
    from cogs.ticket._state import TicketPanelDraft
    from views.ticket.panel_setup_view import PanelSetupView


class DescriptionButton(discord.ui.Button):
    def __init__(self, draft: "TicketPanelDraft", *, parent: "PanelSetupView", row: int):
        self._draft = draft
        self._parent = parent
        super().__init__(
            label="📄 Description",
            style=discord.ButtonStyle.secondary,
            custom_id="ticket_setup_desc_btn",
            row=row,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        modal = TextModal(
            title="Description du panel",
            label="Description (visible des utilisateurs)",
            placeholder="Explique quand ouvrir un ticket sur ce panel.",
            default=self._draft.description or "",
            min_length=1,
            max_length=2000,
            style=discord.TextStyle.paragraph,
            on_submit=self._on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _on_submit(self, interaction: discord.Interaction, value: str) -> None:
        self._draft.description = value
        await self._parent.refresh(interaction)
