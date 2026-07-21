"""
views/exp/levelup_view.py — Annonce de passage de niveau (Components V2).

Vue purement informative (aucun callback bot-side) : LayoutView(timeout=...)
simple, pas de BaseLayoutView. Envoyée avec delete_after par l'appelant.
"""
from __future__ import annotations

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay


def build_levelup_view(member: discord.Member, new_level: int, tier: str) -> LayoutView:
    """Construit l'annonce de level-up affichée dans le salon du message."""
    view = LayoutView(timeout=10)
    container = Container()

    container.add_item(TextDisplay(
        f"## 🎉 Level Up !\n"
        f"{member.mention} passe au **niveau {new_level}** — {tier} !"
    ))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view
