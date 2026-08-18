"""
views/qr/generate_view.py — Vue de résultat pour /qr generate.
"""

from __future__ import annotations

import logging
from typing import Tuple

import discord
from discord import ButtonStyle, Interaction, MediaGalleryItem
from discord.ui import ActionRow, Button, Container, LayoutView, MediaGallery, Separator, TextDisplay

from views.qr._shared import FILENAME, generate_qr_bytes

log = logging.getLogger(__name__)


# ============================================================
# 🎨 View — /qr generate
# ============================================================

def build_qr_generate_view(lien: str) -> Tuple[LayoutView, discord.File]:
    """Construit la vue de résultat après génération d'un QR code."""

    buffer = generate_qr_bytes(lien)
    file = discord.File(buffer, filename=FILENAME)

    view = LayoutView(timeout=600)
    container = Container()

    container.add_item(TextDisplay("# 🔳 __QR Code généré__"))
    container.add_item(Separator())

    lien_affiche = lien if len(lien) <= 100 else lien[:97] + "..."
    container.add_item(TextDisplay(f"**Lien encodé :**\n`{lien_affiche}`"))

    container.add_item(MediaGallery(MediaGalleryItem(media=f"attachment://{FILENAME}")))
    container.add_item(Separator())

    hist_btn = Button(label="Mon historique", style=ButtonStyle.secondary, emoji="📋")

    async def hist_callback(interaction: Interaction) -> None:
        # Imports locaux pour éviter tout import circulaire entre les vues /qr
        from utils.managers.qr_manager import list_qr_by_user
        from views.qr.list_view import build_qr_list_view

        try:
            historique = await list_qr_by_user(interaction.user.id)
        except Exception:
            log.exception("Lecture historique QR échouée (user=%s)", interaction.user.id)
            historique = []

        new_view = build_qr_list_view(interaction.user, historique)
        try:
            await interaction.response.edit_message(view=new_view, attachments=[])
        except (discord.NotFound, discord.HTTPException):
            log.warning("[QR] Édition (historique) échouée (user=%s)", interaction.user.id)

    hist_btn.callback = hist_callback
    container.add_item(ActionRow(hist_btn))

    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view, file