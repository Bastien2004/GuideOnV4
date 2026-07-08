"""
views/_components/base_view.py — Base commune de toutes les views du bot.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import discord
from discord.ui import LayoutView

from utils.container_universel import error_container, send_ephemeral

log = logging.getLogger(__name__)


# ============================================================
# 🛠️ Fontions utilitaires
# ============================================================

def _disable_recursive(item: Any) -> None:
    """Désactive un container."""

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


# ============================================================
# 🧩 Class principale
# ============================================================

class BaseLayoutView(LayoutView):
    """Base commune à toutes les vues Components V2 du bot."""

    def __init__(self, *, owner_id: int | None = None, timeout: float | None = 300):
        super().__init__(timeout=timeout)

        self.owner_id = owner_id
        self.message: discord.Message | discord.InteractionMessage | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Bloque les interactions des autres si owner_id (auteur de la commande) est défini."""

        if self.message is None and interaction.message is not None:
            self.message = interaction.message

        if self.owner_id is None:
            return True
        
        if interaction.user.id != self.owner_id:
            try:
                await send_ephemeral(interaction, error_container("Vous n'êtes pas à l'origine de la commande."))
            except discord.HTTPException:
                pass
            return False
        
        return True

    async def push_update(self, interaction: discord.Interaction, view: discord.ui.View | None = None) -> None:
        """Rafraichissement de la view."""

        target = view if view is not None else self

        if interaction.response.is_done():
            await interaction.edit_original_response(view=target)
        else:
            await interaction.response.edit_message(view=target)

    async def on_timeout(self) -> None:
        """Désactive l'interface après expiration du timeout."""

        for child in self.children:
            _disable_recursive(child)

        if self.message is not None:
            try:
                await self.message.edit(view=self)

            except discord.HTTPException:
                log.debug("[VIEW] Impossible de désactiver les composants à l'expiration (message introuvable/supprimé).")

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: Any,) -> None:
        """Gestion des erreurs interaction."""

        error_id = uuid.uuid4().hex[:8]
        log.error(
            "View error [%s] in %s.%s: %s",
            error_id,
            self.__class__.__name__,
            item.__class__.__name__,
            error,
            exc_info=True,
        )

        msg = f"Echec de l'interraction. Veuillez réessayer plus tard."
        try:
            await send_ephemeral(interaction, error_container(msg))
        except discord.HTTPException:
            pass

BaseView = BaseLayoutView