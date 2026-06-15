"""
ChannelSelect réutilisable.

Permet de demander à l'utilisateur de choisir un salon, en appelant
un callback typé avec l'ID choisi.

Usage :
    select = ChannelSelect(
        placeholder="Salon de log",
        on_select=lambda i, ch_id: setattr(draft, "log_channel", ch_id) or view.refresh(i),
        channel_types=[discord.ChannelType.text],
    )
    view.add_item(select)
"""
from typing import Awaitable, Callable

import discord


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
            channel_types=channel_types or [discord.ChannelType.text],
            min_values=1,
            max_values=1,
            custom_id=custom_id or f"channel_select_{id(self)}",
            row=row,
        )
        self._on_select = on_select

    async def callback(self, interaction: discord.Interaction) -> None:
        await self._on_select(interaction, self.values[0].id)
