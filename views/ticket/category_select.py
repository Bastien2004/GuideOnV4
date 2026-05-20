"""Sélecteur de la catégorie où les tickets ouverts seront créés."""
from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from views._components.channel_select import ChannelSelect

if TYPE_CHECKING:
    from cogs.ticket._state import TicketPanelDraft
    from views.ticket.panel_setup_view import PanelSetupView


class CategorySelect(ChannelSelect):
    def __init__(self, draft: "TicketPanelDraft", *, parent: "PanelSetupView", row: int):
        self._draft = draft
        self._parent = parent
        super().__init__(
            placeholder="📁 Catégorie où créer les tickets",
            on_select=self._update,
            channel_types=[discord.ChannelType.category],
            custom_id="ticket_setup_category",
            row=row,
        )

    async def _update(self, interaction: discord.Interaction, channel_id: int) -> None:
        self._draft.category_open_id = channel_id
        await self._parent.refresh(interaction)
