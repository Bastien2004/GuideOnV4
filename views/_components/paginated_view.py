"""
PaginatedView générique pour afficher une liste paginée, en Components V2 (CV2).
"""
from __future__ import annotations

from typing import Sequence

from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay

from views._components.base_view import BaseLayoutView


class PaginatedView(BaseLayoutView):
    def __init__(
        self,
        items: Sequence,
        *,
        per_page: int = 10,
        owner_id: int,
        timeout: float = 180,
    ):
        super().__init__(owner_id=owner_id, timeout=timeout)
        self.items = list(items)
        self.per_page = per_page
        self.page = 0
        self.total_pages = max(1, (len(self.items) + per_page - 1) // per_page)
        self._build()

    # ---- API à override -----------------------------------------------------

    def build_page_container(self, page_items: list) -> Container:
        """
        À OVERRIDE : construit le Container affichant `page_items`.
        Ne PAS ajouter les boutons de navigation ici, c'est automatique.
        """
        raise NotImplementedError

    # ---- Interne ------------------------------------------------------------

    def page_items(self) -> list:
        start = self.page * self.per_page
        return self.items[start : start + self.per_page]

    def _build(self) -> None:
        self.clear_items()
        container = self.build_page_container(self.page_items())

        prev_btn = Button(
            label="◀", style=ButtonStyle.secondary, disabled=self.page == 0
        )
        prev_btn.callback = self._prev
        next_btn = Button(
            label="▶",
            style=ButtonStyle.secondary,
            disabled=self.page >= self.total_pages - 1,
        )
        next_btn.callback = self._next

        container.add_item(Separator())
        container.add_item(TextDisplay(
            f"-# Page {self.page + 1} / {self.total_pages}"
        ))
        container.add_item(ActionRow(prev_btn, next_btn))
        self.add_item(container)

    async def _refresh(self, interaction: Interaction) -> None:
        self._build()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.edit_message(view=self)

    async def _prev(self, interaction: Interaction) -> None:
        if self.page > 0:
            self.page -= 1
        await self._refresh(interaction)

    async def _next(self, interaction: Interaction) -> None:
        if self.page < self.total_pages - 1:
            self.page += 1
        await self._refresh(interaction)