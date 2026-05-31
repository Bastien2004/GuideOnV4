"""
views/birthday/list_view.py — Vue paginée /birthday list (VIP).

Hérite de PaginatedView. Affiche les anniversaires des 30 prochains jours,
triés par proximité, avec mention du membre + date + âge (si année connue).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import discord
from discord.ui import Container, Separator, TextDisplay

from utils.managers.birthday_manager import compute_age
from views._components.paginated_view import PaginatedView


# Médailles sur le podium (les 3 plus proches)
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

MONTHS_FR = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}


def _format_days_until(d: date, today: date) -> str:
    days = (d - today).days
    if days == 0:
        return "**aujourd'hui** 🎉"
    if days == 1:
        return "**demain**"
    return f"dans **{days}** jours"


class BirthdayListView(PaginatedView):
    """Classement paginé des prochains anniversaires."""

    def __init__(
        self,
        entries: list[tuple[date, dict]],
        *,
        guild: discord.Guild,
        owner_id: int,
        today: date,
        per_page: int = 20,
    ):
        # On ajoute le rang absolu pour les médailles
        items_with_rank = [(i + 1, nxt, user) for i, (nxt, user) in enumerate(entries)]
        self.guild = guild
        self.today = today
        super().__init__(items_with_rank, per_page=per_page, owner_id=owner_id)

    def build_page_container(self, page_items: list) -> Container:
        container = Container()
        container.add_item(TextDisplay(
            f"# 🎂 Anniversaires à venir · {self.guild.name}\n"
            f"-# 30 prochains jours"
        ))
        container.add_item(Separator())

        if not page_items:
            container.add_item(TextDisplay(
                "-# 🎈 Aucun anniversaire enregistré dans les 30 prochains jours."
            ))
            return container

        lines: list[str] = []
        for rank, nxt, user in page_items:
            member = self.guild.get_member(user["user_id"])
            display = member.mention if member else f"`utilisateur {user['user_id']}`"
            prefix = MEDALS.get(rank, f"**#{rank}**")
            month_name = MONTHS_FR.get(user["month"], str(user["month"]))
            age_txt = ""
            if user.get("year"):
                age = compute_age(user["year"], nxt)
                age_txt = f" *({age} ans)*"
            when = _format_days_until(nxt, self.today)
            lines.append(
                f"{prefix} 🎂 {display} — **{user['day']:02d} {month_name}**{age_txt} · {when}"
            )

        container.add_item(TextDisplay("\n".join(lines)))
        return container