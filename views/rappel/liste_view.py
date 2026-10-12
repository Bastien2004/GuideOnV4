"""
views/rappel/liste_view.py — Affichage /rappel liste.
"""
from __future__ import annotations

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

DESTINATION_LABELS = {
    "mp": "📩 MP",
    "salon": "💬 Salon",
}


def _truncate(s: str, n: int = 80) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def build_liste_view(target: discord.abc.User, reminders: list[dict]) -> LayoutView:
    """Construit l'interface du /rappel liste (rappels en attente du membre)."""

    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay(f"# ⏰ Rappels de {target.mention}"))
    container.add_item(Separator())

    if not reminders:
        container.add_item(TextDisplay("Tu n'as **aucun rappel** en attente."))
    else:
        lines = []
        for r in reminders:
            due_ts = int(r["due_at"].timestamp())
            label = DESTINATION_LABELS.get(r["destination"], r["destination"])
            lines.append(
                f"**#{r['id']}** · <t:{due_ts}:R> · {label}\n"
                f"-# {_truncate(r['message'])}"
            )
        container.add_item(TextDisplay("\n\n".join(lines)))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view
