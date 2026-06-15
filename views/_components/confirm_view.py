"""
ConfirmView générique.
"""
from __future__ import annotations

import discord
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay

from views._components.base_view import BaseLayoutView


class ConfirmView(BaseLayoutView):
    def __init__(
        self,
        *,
        owner_id: int,
        question: str = "Confirmer cette action ?",
        confirm_label: str = "Confirmer",
        cancel_label: str = "Annuler",
        confirm_style: discord.ButtonStyle = discord.ButtonStyle.danger,
    ):
        super().__init__(owner_id=owner_id, timeout=60)
        self.confirmed: bool | None = None

        self._confirm_btn = Button(label=confirm_label, style=confirm_style, emoji="✅")
        self._confirm_btn.callback = self._on_confirm

        self._cancel_btn = Button(
            label=cancel_label, style=discord.ButtonStyle.secondary, emoji="✖️"
        )
        self._cancel_btn.callback = self._on_cancel

        container = Container()
        container.add_item(TextDisplay(f"### ⚠️ {question}"))
        container.add_item(Separator())
        container.add_item(ActionRow(self._confirm_btn, self._cancel_btn))
        self.add_item(container)

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        self.confirmed = True
        await self._finish(interaction, "✅ Confirmé.")

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        self.confirmed = False
        await self._finish(interaction, "✖️ Annulé.")

    async def _finish(self, interaction: discord.Interaction, recap: str) -> None:
        done = BaseLayoutView(timeout=None)
        c = Container()
        c.add_item(TextDisplay(recap))
        done.add_item(c)
        await interaction.response.edit_message(view=done)
        self.stop()