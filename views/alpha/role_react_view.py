"""
views/alpha/role_react_view.py — Création du message public du système Rôle Réaction Alpha.
"""

from __future__ import annotations

import discord

from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

ROLE_SEPARATOR = "➤"

def _parse_emoji(s: str | None) -> discord.PartialEmoji | str | None:
    """Convertit une chaîne emoji en objet Discord si c'est un emoji custom."""
    if not s:
        return None
    s = s.strip()
    if s.startswith("<") and ":" in s and s.endswith(">"):
        try:
            return discord.PartialEmoji.from_str(s)
        except Exception:
            pass
    return s


def build_role_react_view(entries: list[dict]) -> LayoutView:
    """Création de l'interface du Rôle Réaction Alpha (vue persistante)."""
    view = LayoutView(timeout=None)

    # ── Header ──────────────────────────────────────────────
    c_header = Container()
    c_header.add_item(TextDisplay("# 🔔 Vos abonnements"))
    c_header.add_item(Separator())

    c_header.add_item(TextDisplay("Personnalisez vos abonnements avec les boutons ci-dessous."))
    c_header.add_item(Separator())

    view.add_item(c_header)

    if not entries:
        c_empty = Container()
        c_empty.add_item(TextDisplay("*Aucun rôle configuré pour le moment.*"))
        c_empty.add_item(TextDisplay("-# GuideOn Studio"))
        view.add_item(c_empty)
        return view

    # ── Liste descriptive ────────────────────────────────────
    c_list = Container()    
    lines = []
    for e in entries:
        emoji = f"{e['emoji']} " if e.get("emoji") else ""
        desc = f"\n-# {e['description']}" if e.get("description") else ""
        lines.append(f"{ROLE_SEPARATOR} {emoji}**{e['label']}**{desc}")

    c_list.add_item(TextDisplay("\n".join(lines)))
    view.add_item(c_list)

    # ── Boutons (rangées de 5) ───────────────────────────────
    c_btns = Container()
    chunk_size = 5
    for i in range(0, len(entries), chunk_size):
        chunk = entries[i : i + chunk_size]
        buttons = []
        for e in chunk:
            buttons.append(Button(
                label=e["label"],
                style=ButtonStyle.secondary,
                custom_id=f"role_react_{e['role_id']}",
                emoji=_parse_emoji(e.get("emoji")),
            ))
        c_btns.add_item(ActionRow(*buttons))

    c_btns.add_item(Separator())
    c_btns.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c_btns)

    return view