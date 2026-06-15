"""
Classe de base pour toutes les views du bot.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import discord
from discord.ui import LayoutView

from utils.container_universel import error_container

log = logging.getLogger(__name__)


def _disable_recursive(item: Any) -> None:
    """Désactive un composant et tous ses enfants (Container -> Section -> Button...)."""
    if hasattr(item, "disabled"):
        try:
            item.disabled = True
        except (AttributeError, TypeError):
            pass
    for child in getattr(item, "children", []) or []:
        _disable_recursive(child)

    accessory = getattr(item, "accessory", None)
    if accessory is not None:
        _disable_recursive(accessory)


class BaseLayoutView(LayoutView):
    """Base commune à toutes les vues Components V2 du bot."""

    def __init__(self, *, owner_id: int | None = None, timeout: float | None = 300,):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Bloque les interactions des non-propriétaires si owner_id est défini."""
        if self.owner_id is None:
            return True
        if interaction.user.id != self.owner_id:
            msg_kwargs = {"view": error_container("❌ Ce menu ne t'appartient pas."), "ephemeral": True}
            if interaction.response.is_done():
                await interaction.followup.send(**msg_kwargs)
            else:
                await interaction.response.send_message(**msg_kwargs)
            return False

    async def on_timeout(self) -> None:
        """Désactive récursivement tous les composants à l'expiration."""
        for child in self.children:
            _disable_recursive(child)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: Any,) -> None:
        error_id = uuid.uuid4().hex[:8]
        log.error(
            "View error [%s] in %s.%s: %s",
            error_id,
            self.__class__.__name__,
            item.__class__.__name__,
            error,
            exc_info=True,
        )
        msg = f"❌ Erreur dans le menu. Code : `{error_id}`"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            pass

BaseView = BaseLayoutView