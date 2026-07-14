"""
views/alpha/event_regle_view.py — Règlement des events M+ Alpha.
"""

from __future__ import annotations

from discord.ui import Container, LayoutView, Separator, TextDisplay

# ============================================================
# 📚 Règlement
# ============================================================

EVENT_RULES = [
    "➤ Le spawn kill est interdit.",
    "➤ Le team-up est interdit.",
    "➤ Le focus est interdit.",
    "➤ La fusion de stuff est interdite.",
    "➤ Camper lors d'un event est interdit.",
    "➤ Sortir ou tenter de sortir du stuff event est interdit.",
]


# ============================================================
# 🧩 Construction de la view
# ============================================================

def build_event_regle_view() -> LayoutView:
    """Construction de la view."""
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# 📚 Règlement events M+"))
    c.add_item(Separator())
    rules_txt = "\n".join(f"**{i+1}.** {r}" for i, r in enumerate(EVENT_RULES))
    c.add_item(TextDisplay(rules_txt))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c)
    return view