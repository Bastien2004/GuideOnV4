"""
views/qr/list_view.py — Vue listant l'historique QR d'un utilisateur (/qr list).
"""

from __future__ import annotations

import logging
from typing import Sequence

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container, success_container
from views._components.paginated_view import PaginatedView
from views.qr._shared import format_date, truncate

log = logging.getLogger(__name__)

_PER_PAGE = 8


# ============================================================
# 🎨 View — /qr list
# ============================================================

class QRListView(PaginatedView):
    """Historique paginé des QR codes d'un membre, sur CE serveur.

    `peut_supprimer` n'autorise la suppression que quand on consulte son
    PROPRE historique — un modérateur qui consulte celui d'un autre membre
    (voir la permission "Gérer le serveur" dans cogs/qr/list.py) le voit en
    lecture seule, pas d'action de suppression proposée.
    """

    def __init__(
        self,
        historique: Sequence,
        *,
        cible: discord.abc.User,
        guild_id: int,
        owner_id: int,
        peut_supprimer: bool,
        per_page: int = _PER_PAGE,
    ) -> None:
        self.cible = cible
        self.guild_id = guild_id
        self.peut_supprimer = peut_supprimer
        super().__init__(list(historique), per_page=per_page, owner_id=owner_id, timeout=300)

    def build_page_container(self, page_items: list) -> Container:
        c = Container()
        nb_total = len(self.items)
        c.add_item(TextDisplay(
            f"# 📋 Historique QR — {self.cible.display_name}\n"
            f"-# {nb_total} QR code(s) sur ce serveur"
        ))
        c.add_item(Separator())

        if not page_items:
            c.add_item(TextDisplay("-# Aucun QR code généré pour l'instant."))
        else:
            for entry in page_items:
                ligne = f"`{truncate(entry.contenu, 60)}`\n-# <t:{format_date(entry.created_at)}:R>"
                if self.peut_supprimer:
                    del_btn = Button(label="", style=ButtonStyle.danger, emoji="<:supprimer:1495444051623809075>")
                    del_btn.callback = self._make_delete_cb(entry.id)
                    c.add_item(Section(TextDisplay(ligne), accessory=del_btn))
                else:
                    c.add_item(TextDisplay(ligne))

        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))
        return c

    def _make_delete_cb(self, entry_id: int):
        async def _on_delete(interaction: Interaction) -> None:
            from utils.managers.qr_manager import delete_qr

            try:
                supprime = await delete_qr(entry_id, user_id=self.cible.id, guild_id=self.guild_id)
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
