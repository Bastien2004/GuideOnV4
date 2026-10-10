"""
views/eco/leaderboard_view.py — Classement paginé /eco leaderboard.
"""

from __future__ import annotations

from typing import Optional

import discord
from discord.ui import Container, Separator, TextDisplay

from utils.managers.eco_manager import format_amount
from views._components.paginated_view import PaginatedView

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


class EcoLeaderboardView(PaginatedView):
    """Classement paginé des soldes d'un serveur."""

    def __init__(self, entries: list[tuple[int, dict]], *, guild: discord.Guild, owner_id: int, per_page: int = 10):

        items_with_rank = [(i + 1, uid, data) for i, (uid, data) in enumerate(entries)]
        self.guild = guild
        super().__init__(items_with_rank, per_page=per_page, owner_id=owner_id)

    def build_page_container(self, page_items: list) -> Container:
        container = Container()

        container.add_item(TextDisplay("# 🏆 Classement Économie"))
        container.add_item(Separator())

        if not page_items:
            container.add_item(TextDisplay(
                "-# 🐦 Aucun membre n'a encore de solde sur ce serveur."
            ))
            return container

        lines: list[str] = []
        for rank, user_id, data in page_items:
            member = self.guild.get_member(user_id)
            display = member.mention if member else f"`utilisateur {user_id}`"
            prefix = MEDALS.get(rank, f"**#{rank}**")
            lines.append(f"{prefix} {display} — **{format_amount(data['balance'])}**")

        container.add_item(TextDisplay("\n".join(lines)))
        return container


# ======================================================
# ====== COMPAT COMMANDE : build_leaderboard_view ======
# ======================================================

def build_leaderboard_view(entries: list[tuple[int, dict]], guild: discord.Guild,
    owner_id: int, per_page: int = 10) -> Optional[EcoLeaderboardView]:

    if not entries:
        return EcoLeaderboardView([], guild=guild, owner_id=owner_id, per_page=per_page)
    return EcoLeaderboardView(entries, guild=guild, owner_id=owner_id, per_page=per_page)