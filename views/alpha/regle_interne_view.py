"""
views/alpha/regle_interne_view.py — Règles internes du serveur Alpha.
"""

from __future__ import annotations

from discord.ui import Container, LayoutView, Separator, TextDisplay

# ============================================================
# 🧩 Construction de la view
# ============================================================

def build_regle_interne_view() -> LayoutView:
    """Construction de la view."""
    view = LayoutView(timeout=None)
    c = Container()

    c.add_item(TextDisplay("# <:Alpha:1500414179650048070> Les Règles Internes du Alpha"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        "●  Règles **spécifiques** du Alpha : 📙 [Consulter](https://nationsglory.fr/forums/thread/les-regles-diverses.77236).\n"
        "●  Règles sur les **Unescos** : 🏦 [Consulter](https://nationsglory.fr/forums/thread/les-regles-sur-les-unesco.77231).\n"
        "●  Règles sur le **Full-build** : 🏗️ [Consulter](https://nationsglory.fr/forums/thread/les-regles-sur-les-full-build.77232).\n"
        "●  Règles sur les **Assauts** : 🪖 [Consulter](https://nationsglory.fr/forums/thread/les-regles-sur-les-assauts.77234).\n"
        "●  Règles sur l'**Architecture** : 🧱 [Consulter](https://nationsglory.fr/forums/thread/les-regles-sur-l039architecture.77233)."
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(c)
    return view