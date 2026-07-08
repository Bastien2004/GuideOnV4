"""
views/_components/wizard_view.py — Base commune de toutes les views à étape du bot.
"""

from __future__ import annotations

from typing import Protocol

from discord import Interaction
from discord.ui import Container

from views._components.base_view import BaseLayoutView


# ============================================================
# 🧩 Class utilitaires
# ============================================================

class Draft(Protocol):
    def is_valid(self) -> bool:
        ...


class WizardView(BaseLayoutView):
    def __init__(self, draft: Draft, *, owner_id: int, timeout: float = 600):
        super().__init__(owner_id=owner_id, timeout=timeout)
        self.draft = draft
        self._build()

    def build_container(self) -> Container:
        """Renvoie le container de l'étape."""
        raise NotImplementedError

    def _build(self) -> None:
        """(Re)construit la vue à partir de build_container()."""
        self.clear_items()
        self.add_item(self.build_container())

    async def refresh(self, interaction: Interaction) -> None:
        """Mise à jour des composants de la views."""
        self._build()
        await self.push_update(interaction)