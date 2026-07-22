"""
views/mod/historique_view.py — Casier judiciaire paginé d'un membre (/mod historique).
"""
from __future__ import annotations

import discord
from discord.ui import Container, Separator, TextDisplay

from utils.managers.mod_sanction_manager import SANCTION_LABELS, SanctionType
from views._components.paginated_view import PaginatedView


def _status_label(sanction: dict) -> str:
    """Statut lisible d'une sanction : révoquée / expirée / en cours / terminée."""
    if sanction["revoked_at"] is not None:
        return "🚫 Révoquée"
    if sanction["type"] in (SanctionType.MUTE.value, SanctionType.TEMPBAN.value):
        if sanction["active"]:
            return "🟢 En cours"
        return "⚪ Expirée"
    if sanction["type"] in (SanctionType.BAN.value, SanctionType.SOFTBAN.value):
        return "🟢 En cours" if sanction["active"] else "⚪ Terminée"
    return "⚪ Terminée"


class HistoriqueView(PaginatedView):
    """Casier judiciaire paginé d'un membre."""

    def __init__(
        self,
        entries: list[dict],
        *,
        target_display: str,
        stats: dict,
        guild: discord.Guild,
        owner_id: int,
        per_page: int = 8,
    ):
        self.target_display = target_display
        self.stats = stats
        self.guild = guild
        super().__init__(entries, per_page=per_page, owner_id=owner_id)

    def build_page_container(self, page_items: list) -> Container:
        container = Container()

        container.add_item(TextDisplay(f"# 📁 Casier judiciaire — {self.target_display}"))
        container.add_item(Separator())

        summary = " · ".join(
            f"{SANCTION_LABELS[t][0]} {SANCTION_LABELS[t][1]} : **{self.stats.get(t.value, 0)}**"
            for t in SanctionType
        )
        container.add_item(TextDisplay(summary))
        container.add_item(Separator())

        if not page_items:
            container.add_item(TextDisplay("-# 🤷 Aucune sanction enregistrée pour ce membre."))
            return container

        lines = []
        for sanction in page_items:
            emoji, label = SANCTION_LABELS[SanctionType(sanction["type"])]
            status = _status_label(sanction)
            created_ts = int(sanction["created_at"].timestamp())
            lines.append(
                f"{emoji} `#{sanction['id']}` **{label}** — {status}\n"
                f"-# {sanction['reason']} · <t:{created_ts}:R> · par <@{sanction['moderator_id']}>"
            )

        container.add_item(TextDisplay("\n\n".join(lines)))
        return container