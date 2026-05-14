"""
ConfirmView générique — boîte de dialogue Oui/Non.

Usage :
    view = ConfirmView(owner_id=interaction.user.id)
    await interaction.response.send_message("Sûr ?", view=view, ephemeral=True)
    await view.wait()
    if view.confirmed:
        # confirmé
        ...
"""
import discord

from views.components.base_view import BaseView


class ConfirmView(BaseView):
    def __init__(
        self,
        *,
        owner_id: int,
        confirm_label: str = "Confirmer",
        cancel_label: str = "Annuler",
        confirm_style: discord.ButtonStyle = discord.ButtonStyle.danger,
    ):
        super().__init__(owner_id=owner_id, timeout=60)
        self.confirmed: bool | None = None

        confirm_btn = discord.ui.Button(label=confirm_label, style=confirm_style)
        confirm_btn.callback = self._on_confirm
        self.add_item(confirm_btn)

        cancel_btn = discord.ui.Button(
            label=cancel_label, style=discord.ButtonStyle.secondary
        )
        cancel_btn.callback = self._on_cancel
        self.add_item(cancel_btn)

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        self.confirmed = True
        await self._disable_and_finish(interaction)

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        self.confirmed = False
        await self._disable_and_finish(interaction)

    async def _disable_and_finish(self, interaction: discord.Interaction) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True  # type: ignore[attr-defined]
        await interaction.response.edit_message(view=self)
        self.stop()
