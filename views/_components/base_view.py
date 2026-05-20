"""
Classe de base pour TOUTES les Views du bot.

Apporte par défaut :
- owner_check : seul l'auteur de la commande peut interagir
- gestion d'erreur uniforme avec error_id corrélé (résout OBS-002)
- timeout configurable

Toutes les views du projet héritent de BaseView, jamais de discord.ui.View directement.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import discord

log = logging.getLogger(__name__)


class BaseView(discord.ui.View):
    def __init__(
        self,
        *,
        owner_id: int | None = None,
        timeout: float | None = 300,
    ):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Bloque les interactions des non-propriétaires si owner_id est défini."""
        if self.owner_id is None:
            return True
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "❌ Ce menu ne t'appartient pas.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Désactive tous les composants à l'expiration."""
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True  # type: ignore[attr-defined]

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: Any,
    ) -> None:
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
