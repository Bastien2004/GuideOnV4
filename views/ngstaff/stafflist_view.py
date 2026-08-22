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

from utils.ng_staff_display import build_member_line
from utils.ng_server_display import get_server_display_name, get_server_emoji
from utils.db.models.staff_grades import GRADE_EMOJIS, GRADE_LABELS, GRADES_ORDER

# ============================================================
# 🧩 Construction de la view
# ============================================================

def build_stafflist_view(members: list[dict], *, server: str = "alpha") -> LayoutView:
    """
    Affiche les 6 grades de la hiérarchie staff (administrateur → guide) en
    sections, plus une section dédiée par statut ayant `requires_second_pseudo`
    (ex : Builder sur Alpha — pseudo secondaire affiché à la place du pseudo
    staff, pas de badge inline puisque déjà listé dans sa propre section).

    Statuts (Paul, 2026-08-22) : auparavant une section "🧱 Builders" codée
    en dur (is_builder=True) — remplacée par une boucle générique sur les
    statuts du serveur (member["statuts"], enrichi par ng_staff_manager)
    ayant `requires_second_pseudo=True`, pour rester valable quel que soit
    le nom du statut défini par le serveur NG. Un membre purement statut
    (grade=None) sans statut à second pseudo n'apparaît dans AUCUNE section
    — invisible dans la stafflist, comme voulu.

    `server` : sélectionne le titre affiché (nom du serveur NG). Auparavant
    codé en dur "Effectif Staff Alpha" avec l'emoji <:AlphaStaff:...> pour
    tous les serveurs NG — corrigé (Paul, 2026-08-22).
    """
    view = LayoutView(timeout=None)

    # ── Header ────────────────────────────────────────────────
    display_name = get_server_display_name(server)
    emoji = get_server_emoji(server)
    header = Container()
    header.add_item(TextDisplay(f"# {emoji} Effectif Staff {display_name}"))
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

    # ── Une section dédiée par statut "second pseudo" (ex: Builder) ──────
    # Un membre peut apparaître dans plusieurs de ces sections s'il cumule
    # plusieurs statuts à second pseudo (cas rare mais pas interdit).
    seen_second_pseudo_statuts: dict[str, dict] = {}
    for m in members:
        for s in m.get("statuts", []):
            if s.get("requires_second_pseudo"):
                seen_second_pseudo_statuts.setdefault(s["key"], s)

    for key, statut_meta in seen_second_pseudo_statuts.items():
        holders = [
            (m, s) for m in members for s in m.get("statuts", [])
            if s["key"] == key and s.get("requires_second_pseudo")
        ]
        if not holders:
            continue

        emoji = statut_meta.get("emoji") or "🎖️"
        c = Container()
        c.add_item(TextDisplay(f"## {emoji} {statut_meta['label']}s"))
        c.add_item(Separator())

        block = "\n".join(
            f"**{s.get('second_pseudo') or m['pseudo_jeu']}** — <@{m['discord_id']}> — `{m['discord_id']}`"
            for m, s in holders
        )

        c.add_item(TextDisplay(block))
        c.add_item(Separator())
        view.add_item(c)

    # ── Footer ────────────────────────────────────────────────
    footer = Container()
    footer.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(footer)

    return view