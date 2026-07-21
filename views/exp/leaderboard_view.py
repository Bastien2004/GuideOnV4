"""
views/exp/leaderboard_view.py — Classement paginé /exp leaderboard.

Hérite de PaginatedView (views/_components/paginated_view.py) :
- on lui passe la liste pré-classée des (user_id, total_exp)
- on override build_page_container() pour afficher la page courante

Médailles 🥇🥈🥉 sur le podium global (rangs 1-3, page 1 seulement).
"""
from __future__ import annotations

from typing import Optional

import discord
from discord.ui import Container, Separator, TextDisplay

from utils.managers.exp_manager import level_progress
from views._components.paginated_view import PaginatedView

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


class ExpLeaderboardView(PaginatedView):
    """Classement paginé de l'EXP des membres d'un serveur."""

    def __init__(
        self,
        entries: list[tuple[int, int]],
        *,
        guild: discord.Guild,
        owner_id: int,
        per_page: int = 10,
    ):
        # On stocke chaque item enrichi avec son rang absolu (1-indexé) pour
        # afficher les médailles correctement même après pagination.
        items_with_rank = [(i + 1, uid, total_exp) for i, (uid, total_exp) in enumerate(entries)]
        self.guild = guild
        super().__init__(items_with_rank, per_page=per_page, owner_id=owner_id)

    def build_page_container(self, page_items: list) -> Container:
        container = Container()

        container.add_item(TextDisplay(
            f"# <:analyser:1495446292963528798> Classement d'expérience\n-# {self.guild.name}"
        ))
        container.add_item(Separator())

        if not page_items:
            container.add_item(TextDisplay(
                "-# Aucun membre n'a encore gagné d'EXP sur ce serveur."
            ))
            return container

        lines: list[str] = []
        for rank, user_id, total_exp in page_items:
            member = self.guild.get_member(user_id)
            display = f"**{member.display_name}**" if member else f"`utilisateur {user_id}`"
            stats = level_progress(total_exp)
            prefix = MEDALS.get(rank, f"**#{rank}**")
            lines.append(
                f"{prefix} {display} — Niv. **{stats['level']}** {stats['tier']} — "
                f"`{total_exp:,} EXP`"
            )

        container.add_item(TextDisplay("\n".join(lines)))
        return container


# ======================================================
# ===== COMPAT COMMANDE : ExpLeaderboardView ===========
# ======================================================
# La classe est déjà directement utilisable, on expose simplement un constructeur
# explicite identique aux autres vues pour la cohérence d'appel.

def build_leaderboard_view(
    entries: list[tuple[int, int]],
    guild: discord.Guild,
    owner_id: int,
    per_page: int = 10,
) -> Optional[ExpLeaderboardView]:
    if not entries:
        return ExpLeaderboardView([], guild=guild, owner_id=owner_id, per_page=per_page)
    return ExpLeaderboardView(entries, guild=guild, owner_id=owner_id, per_page=per_page)
