"""
views/exp/levelup_view.py — Annonce de passage de niveau.
"""

from __future__ import annotations

import discord
from discord.ui import Container, LayoutView, Section, Separator, TextDisplay, Thumbnail


def _avatar_url(member: discord.Member) -> str:
    avatar = member.display_avatar
    return avatar.replace(size=256, format="gif" if avatar.is_animated() else "png").url


def build_levelup_view(member: discord.Member, new_level: int, tier: str, *, tier_changed: bool = False) -> LayoutView:
    """Construit l'annonce de level-up."""
    
    view = LayoutView(timeout=None)
    container = Container()

    header = "## 🏔️ Nouveau palier atteint !" if tier_changed else "## 🎉 Level Up !"
    container.add_item(TextDisplay(header))
    container.add_item(Separator())

    if tier_changed:
        body = (
            f"{member.mention} passe au **niveau {new_level}** et rejoint "
            f"désormais le rang **{tier}** !"
        )
    else:
        body = f"{member.mention} passe au **niveau {new_level}** — {tier} !"
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view