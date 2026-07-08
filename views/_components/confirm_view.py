"""
views/_components/confirm_view.py — Base commune de toutes les views de confirmation du bot.
"""

from __future__ import annotations

import discord
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay

from views._components.base_view import BaseLayoutView


# ============================================================
# 🧩 Class utilitaires
# ============================================================

class ConfirmView(BaseLayoutView):
    def __init__(
        self,
        *,
        owner_id: int,
        question: str = "Voulez vous confirmer cette action ?",
        confirm_label: str = "Confirmer",
        cancel_label: str = "Annuler",
        confirm_style: discord.ButtonStyle = discord.ButtonStyle.danger,
    ):
        super().__init__(owner_id=owner_id, timeout=60)
        self.confirmed: bool | None = None

        self._confirm_btn = Button(label=confirm_label, style=confirm_style, emoji="<:valider:1495444292867723284>")
        self._confirm_btn.callback = self._on_confirm

        self._cancel_btn = Button(
            label=cancel_label, style=discord.ButtonStyle.secondary, emoji="<:annuler:1495444256754761979>"
        )
        self._cancel_btn.callback = self._on_cancel

        container = Container()
        container.add_item(TextDisplay(f"### <:erreur:1495443907281031359> {question}"))
        container.add_item(Separator())
        container.add_item(ActionRow(self._confirm_btn, self._cancel_btn))
        self.add_item(container)

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        self.confirmed = True
        await self._finish(interaction, "L'action a été **confirmée** !")

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        self.confirmed = False
        await self._finish(interaction, "L'action a été **annulée**.")

    async def _finish(self, interaction: discord.Interaction, recap: str) -> None:
        done = BaseLayoutView(timeout=None)
        c = Container()
        c.add_item(TextDisplay(recap))
        done.add_item(c)
        await self.push_update(interaction, view=done)
        self.stop()