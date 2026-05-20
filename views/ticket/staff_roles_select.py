"""Sélecteur des rôles staff (1 à 3)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from views._components.role_select import RoleSelect

if TYPE_CHECKING:
    import discord

    from cogs.ticket._state import TicketPanelDraft
    from views.ticket.panel_setup_view import PanelSetupView


class StaffRolesSelect(RoleSelect):
    def __init__(self, draft: "TicketPanelDraft", *, parent: "PanelSetupView", row: int):
        self._draft = draft
        self._parent = parent
        super().__init__(
            placeholder="👮 Rôles staff (1 à 3)",
            on_select=self._update,
            min_values=1,
            max_values=3,
            custom_id="ticket_setup_staff",
            row=row,
        )

    async def _update(self, interaction: "discord.Interaction", role_ids: list[int]) -> None:
        self._draft.staff_role_ids = role_ids
        await self._parent.refresh(interaction)
