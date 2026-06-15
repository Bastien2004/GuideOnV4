"""
views/_components/user_select.py — Sélecteur d'utilisateur réutilisable.
"""
from __future__ import annotations

from typing import Awaitable, Callable

import discord
from discord.ui import UserSelect as DiscordUserSelect

OnSelect = Callable[[discord.Interaction, list[int]], Awaitable[None]]


class UserSelect(DiscordUserSelect):
    """UserSelect avec callback fermé personnalisé."""

    def __init__(
        self,
        *,
        placeholder: str = "Sélectionner un utilisateur",
        on_select: OnSelect,
        min_values: int = 1,
        max_values: int = 1,
    ):
        super().__init__(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
        )
        self._on_select = on_select

    async def callback(self, interaction: discord.Interaction) -> None:
        ids = [u.id for u in self.values]
        await self._on_select(interaction, ids)