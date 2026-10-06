"""
views/qr/generate_view.py — Vue de résultat pour /qr generate.
"""

from __future__ import annotations

import logging
from typing import Tuple

import discord
from discord import ButtonStyle, Interaction, MediaGalleryItem
from discord.ui import ActionRow, Button, Container, MediaGallery, Separator, TextDisplay

from views._components.base_view import BaseLayoutView
from views.qr._shared import FILENAME, generate_qr_bytes, truncate

log = logging.getLogger(__name__)


# ============================================================
# 🎨 View — /qr generate
# ============================================================

class QRGenerateResultView(BaseLayoutView):
    """Résultat compact d'une génération de QR code : aperçu + accès rapide
    à l'historique personnel."""

    def __init__(self, lien: str, *, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=600)
        self.lien = lien
        self._build()

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("# 🔳 QR code généré"))
        c.add_item(Separator())

        c.add_item(TextDisplay(f"**Lien encodé**\n`{truncate(self.lien, 100)}`"))
        c.add_item(MediaGallery(MediaGalleryItem(media=f"attachment://{FILENAME}")))
        c.add_item(Separator())

        hist_btn = Button(label="Mon historique", style=ButtonStyle.secondary, emoji="📋")
        hist_btn.callback = self._on_history
        c.add_item(ActionRow(hist_btn))

        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_history(self, interaction: Interaction) -> None:
        # Imports locaux pour éviter tout import circulaire entre les vues /qr.
        from utils.managers.qr_manager import list_qr_by_user
        from views.qr.list_view import QRListView

        try:
            historique = await list_qr_by_user(interaction.user.id)
        except Exception:
            log.exception("Lecture historique QR échouée (user=%s)", interaction.user.id)
            historique = []

        new_view = QRListView(historique, owner_id=self.owner_id)
        try:
            await interaction.response.edit_message(view=new_view, attachments=[])
        except (discord.NotFound, discord.HTTPException):
            log.warning("[QR] Édition (historique) échouée (user=%s)", interaction.user.id)


def build_qr_generate_view(lien: str, *, owner_id: int) -> Tuple[QRGenerateResultView, discord.File]:
    """Construit la vue de résultat après génération d'un QR code."""

    buffer = generate_qr_bytes(lien)
    file = discord.File(buffer, filename=FILENAME)
    return QRGenerateResultView(lien, owner_id=owner_id), file
