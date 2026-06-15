"""
Bouton "Retour" générique pour navigation entre sous-vues.

Usage : passer une fonction async qui remplace la view affichée.
"""
from typing import Awaitable, Callable

import discord


class BackButton(discord.ui.Button):
    def __init__(
        self,
        *,
        on_back: Callable[[discord.Interaction], Awaitable[None]],
        label: str = "Retour",
        emoji: str = "🔙",
        row: int | None = None,
    ):
        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            row=row,
        )
        self._on_back = on_back

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._on_back(interaction)
