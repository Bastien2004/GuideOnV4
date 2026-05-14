"""
TextModal réutilisable.

Une popup de saisie texte avec longueur min/max et callback typé.

Usage :
    modal = TextModal(
        title="Titre du panel",
        label="Titre affiché aux utilisateurs",
        placeholder="Ex: Support",
        default=draft.title or "",
        min_length=1,
        max_length=100,
        on_submit=lambda i, value: setattr(draft, "title", value) or view.refresh(i),
    )
    await interaction.response.send_modal(modal)
"""
from typing import Awaitable, Callable

import discord


class TextModal(discord.ui.Modal):
    def __init__(
        self,
        *,
        title: str,
        label: str,
        placeholder: str = "",
        default: str = "",
        min_length: int = 0,
        max_length: int = 1000,
        style: discord.TextStyle = discord.TextStyle.short,
        on_submit: Callable[[discord.Interaction, str], Awaitable[None]],
    ):
        super().__init__(title=title)
        self._on_submit = on_submit
        self.input = discord.ui.TextInput(
            label=label,
            placeholder=placeholder,
            default=default,
            style=style,
            min_length=min_length,
            max_length=max_length,
            required=True,
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._on_submit(interaction, self.input.value)
