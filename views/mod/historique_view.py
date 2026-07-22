"""
views/mod/historique_view.py — Historique des sanctions d'un membre.
"""

from __future__ import annotations

import discord
from discord.ui import Container, Separator, TextDisplay

from utils.managers.mod_sanction_manager import SANCTION_LABELS, SanctionType
from views._components.paginated_view import PaginatedView


def _status_label(sanction: dict) -> str:
    """Statut d'une sanction."""

    if sanction["revoked_at"] is not None:
        return "*Révoquée*"
    
    if sanction["type"] in (SanctionType.MUTE.value, SanctionType.TEMPBAN.value):
        if sanction["active"]:
            return "*En cours*"
        return "*Expirée*"
    
    if sanction["type"] in (SanctionType.BAN.value, SanctionType.SOFTBAN.value):
        return "*En cours*" if sanction["active"] else "*Terminée*"
    
    return "*Terminée*"


class HistoriqueView(PaginatedView):
    """Liste paginée des sanctions d'un membre."""

    def __init__(self, entries: list[dict], *, target_display: str, stats: dict, guild: discord.Guild, owner_id: int, per_page: int = 8):
        self.target_display = target_display
        self.stats = stats
        self.guild = guild
        super().__init__(entries, per_page=per_page, owner_id=owner_id)

    def build_page_container(self, page_items: list) -> Container:
        container = Container()

        container.add_item(TextDisplay(f"# <:fichier:1495446721520730242> Historique de {self.target_display}"))
        container.add_item(Separator())

        if not page_items:
            container.add_item(TextDisplay("-# <:annuler:1495444256754761979> Aucune sanction enregistrée pour ce membre."))
            return container

        lines = []
        for sanction in page_items:
            label = SANCTION_LABELS[SanctionType(sanction["type"])]
            status = _status_label(sanction)
            created_ts = int(sanction["created_at"].timestamp())
            lines.append(
                f"➤ `#{sanction['id']}` - **{label}** — {status}\n"
                f"➥ {sanction['reason']} · <t:{created_ts}:R>\n"
                f"Par <@{sanction['moderator_id']}>."
            )

        container.add_item(TextDisplay("\n\n".join(lines)))
        return container