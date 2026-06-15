"""
WizardView générique.
"""
from __future__ import annotations

from typing import Protocol

from discord import Interaction
from discord.ui import Container

from views._components.base_view import BaseLayoutView


class Draft(Protocol):
    """Interface que doivent respecter les drafts (état du wizard)."""

    def is_valid(self) -> bool:
        ...


class WizardView(BaseLayoutView):
    def __init__(self, draft: Draft, *, owner_id: int, timeout: float = 600):
        super().__init__(owner_id=owner_id, timeout=timeout)
        self.draft = draft
        self._build()

    def build_container(self) -> Container:
        """À OVERRIDE par les sous-classes : renvoie le Container de l'étape."""
        raise NotImplementedError

    def _build(self) -> None:
        """(Re)construit la vue à partir de build_container()."""
        self.clear_items()
        self.add_item(self.build_container())

    async def refresh(self, interaction: Interaction) -> None:
        """À appeler depuis chaque composant après modification du draft."""
        self._build()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.edit_message(view=self)