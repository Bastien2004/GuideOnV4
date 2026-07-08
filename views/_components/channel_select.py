"""
views/_components/channel_select.py — Composant ChannelSelect pour les interfaces Discord.
"""

from typing import Awaitable, Callable

import discord

# ============================================================
# 📦 Constantes
# ============================================================

DEFAULT_CHANNEL_TYPES: list[discord.ChannelType] = [
    discord.ChannelType.text,
    discord.ChannelType.news,
]


# ============================================================
# 🧩 Class principale
# ============================================================

class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(
        self,
        *,
        placeholder: str,
        on_select: Callable[[discord.Interaction, int], Awaitable[None]],
        channel_types: list[discord.ChannelType] | None = None,
        custom_id: str | None = None,
        row: int | None = None,
    ):
        super().__init__(
            placeholder=placeholder,
            channel_types=channel_types or DEFAULT_CHANNEL_TYPES,
            min_values=1,
            max_values=1,
            custom_id=custom_id or f"channel_select_{id(self)}",
            row=row,
        )
        self._on_select = on_select

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._on_select(interaction, self.values[0].id)