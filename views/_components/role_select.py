"""
views/_components/role_select.py — Composant RoleSelect pour les interfaces Discord.
"""

from typing import Awaitable, Callable

import discord


# ============================================================
# 🧩 Class principale
# ============================================================

class RoleSelect(discord.ui.RoleSelect):
    def __init__(
        self,
        *,
        placeholder: str,
        on_select: Callable[[discord.Interaction, list[int]], Awaitable[None]],
        min_values: int = 1,
        max_values: int = 1,
        custom_id: str | None = None,
        row: int | None = None,
    ):
        super().__init__(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            custom_id=custom_id or f"role_select_{id(self)}",
            row=row,
        )
        self._on_select = on_select

    async def callback(self, interaction: discord.Interaction) -> None:
        ids = [r.id for r in self.values]
        await self._on_select(interaction, ids)