"""
views/alpha/stafflist_view.py — Effectif staff du serveur Alpha.

Extrait de cogs/alpha/stafflist.py, même traitement que regle_interne,
nous_rejoindre, index et event_start (cog réduit à la commande, la
construction de la view vit ici).

Reste en LayoutView simple, PAS BaseLayoutView : ce message n'a aucun
composant interactif (aucun bouton, aucun select) et est posté/édité
publiquement dans un salon pour tout le monde, avec timeout=None (persiste
indéfiniment, volontairement). BaseLayoutView n'apporterait rien ici.
"""
from __future__ import annotations

from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.alpha_staff_display import build_member_line
from utils.db.models.alpha_staff import GRADE_EMOJIS, GRADE_LABELS, GRADES_ORDER

# ============================================================
# 🧩 Construction de la view
# ============================================================

def build_stafflist_view(members: list[dict]) -> LayoutView:
    """
    Affiche UNIQUEMENT les 6 grades de la hiérarchie staff (administrateur
    → guide) en sections, plus une section Builders dédiée (tous les
    is_builder=True, avec leur pseudo builder — pas de badge, déjà listés
    avec leur pseudo dédié).

    Un membre purement Journaliste/Affilié (grade=None, aucun is_builder)
    n'apparaît dans AUCUNE section — invisible dans la stafflist, comme
    voulu (seuls les 6 grades + Builders y figurent).
    """
    view = LayoutView(timeout=None)

    # ── Header ────────────────────────────────────────────────
    header = Container()
    header.add_item(TextDisplay("# <:AlphaStaff:1493512964337307698> Effectif Staff Alpha"))
    view.add_item(header)

    # ── Un Container par grade présent (administrateur → guide) ──
    for grade in GRADES_ORDER:
        grade_members = [m for m in members if m["grade"] == grade]
        if not grade_members:
            continue

        emoji = GRADE_EMOJIS.get(grade, "•")
        label = GRADE_LABELS.get(grade, grade.replace("_", " ").title())

        c = Container()
        c.add_item(TextDisplay(f"## {emoji} {label}"))
        c.add_item(Separator())

        block = "\n".join(build_member_line(m) for m in grade_members)

        c.add_item(TextDisplay(block))
        c.add_item(Separator())
        view.add_item(c)

    # ── Section Builders dédiée (tous les is_builder=True) ────
    builders = [m for m in members if m.get("is_builder")]
    if builders:
        c = Container()
        c.add_item(TextDisplay("## 🧱 Builders"))
        c.add_item(Separator())

        block = "\n".join(
            f"**{m.get('pseudo_jeu_builder') or m['pseudo_jeu']}** — <@{m['discord_id']}> — `{m['discord_id']}`"
            for m in builders
        )

        c.add_item(TextDisplay(block))
        c.add_item(Separator())
        view.add_item(c)

    # ── Footer ────────────────────────────────────────────────
    footer = Container()
    footer.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(footer)

    return view