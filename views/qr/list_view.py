"""
views/qr/list_view.py — Vue listant l'historique QR personnel (/qr list).
"""

from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, Interaction, MediaGalleryItem
from discord.ui import Button, Container, LayoutView, MediaGallery, Section, Separator, TextDisplay

from utils.container_universel import error_container, success_container
from views._components.paginated_view import PaginatedView
from views.qr._shared import FILENAME, format_date, generate_qr_bytes, truncate

log = logging.getLogger(__name__)

_PER_PAGE = 8


# ============================================================
# 🎨 View — /qr list
# ============================================================

class QRListView(PaginatedView):
    """Historique paginé des QR codes d'un membre — toujours SON PROPRE
    historique (plus de consultation d'un autre membre), tous serveurs
    confondus. Chaque entrée propose deux actions : voir l'image (régénérée
    à la demande — elle n'est jamais stockée, seul le contenu texte l'est)
    et supprimer."""

    def __init__(self, historique, *, owner_id: int, per_page: int = _PER_PAGE) -> None:
        super().__init__(list(historique), per_page=per_page, owner_id=owner_id, timeout=300)

    def build_page_container(self, page_items: list) -> Container:
        c = Container()
        nb_total = len(self.items)
        c.add_item(TextDisplay(
            f"# 📋 Mon historique QR\n"
            f"-# {nb_total} QR code(s) — tous serveurs confondus"
        ))
        c.add_item(Separator())

        if not page_items:
            c.add_item(TextDisplay("-# Aucun QR code généré pour l'instant."))
        else:
            for entry in page_items:
                ligne = f"`{truncate(entry.contenu, 60)}`\n-# <t:{format_date(entry.created_at)}:R>"

                voir_btn = Button(label="", style=ButtonStyle.secondary, emoji="👁️")
                voir_btn.callback = self._make_view_cb(entry.id, entry.contenu)
                c.add_item(Section(TextDisplay(ligne), accessory=voir_btn))

                del_btn = Button(label="Supprimer", style=ButtonStyle.danger, emoji="<:supprimer:1495444051623809075>")
                del_btn.callback = self._make_delete_cb(entry.id)
                row = discord.ui.ActionRow()
                row.add_item(del_btn)
                c.add_item(row)

        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))
        return c

    def _make_view_cb(self, entry_id: int, contenu: str):
        async def _on_view(interaction: Interaction) -> None:
            # L'image n'est jamais stockée (seul le texte l'est en DB) — on
            # la régénère à la demande, exactement comme /qr generate.
            buffer = generate_qr_bytes(contenu)
            file = discord.File(buffer, filename=FILENAME)

            view = LayoutView(timeout=None)
            preview = Container()
            preview.add_item(TextDisplay(f"**Lien encodé**\n`{truncate(contenu, 100)}`"))
            preview.add_item(MediaGallery(MediaGalleryItem(media=f"attachment://{FILENAME}")))
            preview.add_item(Separator())
            preview.add_item(TextDisplay("-# GuideOn Studio"))
            view.add_item(preview)

            try:
                await interaction.response.send_message(view=view, files=[file], ephemeral=True)
            except discord.HTTPException:
                log.warning("[QR] Envoi de l'aperçu (historique) échoué (entry=%s)", entry_id)

        return _on_view

    def _make_delete_cb(self, entry_id: int):
        async def _on_delete(interaction: Interaction) -> None:
            from utils.managers.qr_manager import delete_qr

            try:
                supprime = await delete_qr(entry_id, user_id=self.owner_id)
            except Exception:
                log.exception("[QR] Suppression d'une entrée d'historique échouée (id=%s)", entry_id)
                await interaction.response.send_message(
                    view=error_container("Impossible de **supprimer** cette entrée."), ephemeral=True,
                )
                return

            if not supprime:
                await interaction.response.send_message(
                    view=error_container("Cette entrée a déjà été supprimée."), ephemeral=True,
                )
                return

            self.items = [e for e in self.items if e.id != entry_id]
            self.total_pages = max(1, (len(self.items) + self.per_page - 1) // self.per_page)
            self.page = min(self.page, self.total_pages - 1)
            self._build()

            await interaction.response.edit_message(view=self)
            await interaction.followup.send(view=success_container("Entrée supprimée."), ephemeral=True)

        return _on_delete
