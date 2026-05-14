"""
WizardView générique — assistant multi-étapes.

Pattern :
1. Une dataclass de "draft" (état) est gérée dans state.py du système concerné
2. Les composants modifient le draft
3. La WizardView assemble les composants et expose refresh() pour redessiner

Voir cogs/ticket/ticket_panel_create.py + views/ticket/panel_setup_view.py
pour un exemple concret.
"""
from typing import Protocol

import discord

from views.components.base_view import BaseView


class Draft(Protocol):
    """Interface que doivent respecter les drafts (état du wizard)."""

    def is_valid(self) -> bool:
        ...


class WizardView(BaseView):
    def __init__(self, draft: Draft, *, owner_id: int, timeout: float = 600):
        super().__init__(owner_id=owner_id, timeout=timeout)
        self.draft = draft

    def build_embed(self) -> discord.Embed:
        """À OVERRIDE par les sous-classes."""
        raise NotImplementedError

    async def refresh(self, interaction: discord.Interaction) -> None:
        """À appeler depuis chaque composant après modification du draft."""
        if interaction.response.is_done():
            await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )
        else:
            await interaction.response.edit_message(
                embed=self.build_embed(), view=self
            )
