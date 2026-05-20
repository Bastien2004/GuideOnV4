"""
PaginatedView générique pour afficher une liste paginée.

Hérite-en et override build_embed() pour ton cas spécifique.
Adapté à : leaderboard EXP, liste de panels, sanctions, etc.
"""
from typing import Sequence

import discord

from views._components.base_view import BaseView


class PaginatedView(BaseView):
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
        self._refresh_button_states()

    def page_items(self) -> list:
        start = self.page * self.per_page
        return self.items[start : start + self.per_page]

    def build_embed(self) -> discord.Embed:
        """À OVERRIDE par les sous-classes."""
        raise NotImplementedError

    def _refresh_button_states(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "page_prev":
                    child.disabled = self.page == 0
                elif child.custom_id == "page_next":
                    child.disabled = self.page >= self.total_pages - 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, custom_id="page_prev")
    async def _prev(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        self.page -= 1
        self._refresh_button_states()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, custom_id="page_next")
    async def _next(self, interaction: discord.Interaction, _b: discord.ui.Button) -> None:
        self.page += 1
        self._refresh_button_states()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
