"""
views/birthday/next_view.py — Vue /birthday next (VIP).

Vue non-interactive. Affiche le prochain anniversaire à venir, en groupant
les utilisateurs qui partagent la même date. Si année connue, affiche l'âge
atteint à cette date.
"""
from __future__ import annotations

from datetime import date

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.managers.birthday_manager import compute_age

MONTHS_FR = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}


def _format_days_until(d: date, today: date) -> str:
    days = (d - today).days
    if days == 0:
        return "🎉 **aujourd'hui** !"
    if days == 1:
        return "**demain**"
    return f"dans **{days}** jours"


def build_next_view(
    next_date: date,
    users: list[dict],
    guild: discord.Guild,
    today: date,
) -> LayoutView:
    """
    Construit la vue. `users` est la liste des utilisateurs (dict) partageant
    cette même date. Au moins un user attendu.
    """
    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay(
        f"# 🎂 Prochain anniversaire\n-# {guild.name}"
    ))
    container.add_item(Separator())

    month_name = MONTHS_FR.get(next_date.month, str(next_date.month))
    container.add_item(TextDisplay(
        f"### 📅 {next_date.day:02d} {month_name}\n"
        f"-# {_format_days_until(next_date, today)}"
    ))
    container.add_item(Separator())

    # Bloc utilisateurs (mentions + âge si connu)
    lines: list[str] = []
    for u in users:
        member = guild.get_member(u["user_id"])
        display = member.mention if member else f"`utilisateur {u['user_id']}`"
        age_txt = ""
        if u.get("year"):
            age = compute_age(u["year"], next_date)
            age_txt = f" *({age} ans)*"
        lines.append(f"-# 🎈 {display}{age_txt}")

    if len(users) > 1:
        container.add_item(TextDisplay(f"### 👥 Membres concernés ({len(users)})"))
    else:
        container.add_item(TextDisplay("### 👤 Membre concerné"))
    container.add_item(TextDisplay("\n".join(lines)))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


class BirthdayNextView:
    """Wrapper pour la cohérence d'API avec les autres systèmes."""

    @classmethod
    def create(
        cls,
        next_date: date,
        users: list[dict],
        guild: discord.Guild,
        today: date,
    ) -> LayoutView:
        return build_next_view(next_date, users, guild, today)