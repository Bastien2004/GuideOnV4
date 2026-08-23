"""
views/ngstaff/stafflist_view.py — Effectif staff, multi-serveurs
(ex-views/alpha/stafflist_view.py).

Extrait à l'origine de cogs/alpha/stafflist.py (supprimé depuis, remplacé
par /ngstaff stafflist).

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

def build_stafflist_view(members: list[dict], *, server: str) -> LayoutView:
    """
    Affiche les 6 grades de la hiérarchie staff (administrateur → guide) en
    sections, plus une section dédiée par statut ayant `has_stafflist_category`
    et/ou `requires_second_pseudo` (ex : Builder — pseudo secondaire affiché
    à la place du pseudo staff ; Journaliste/Affilié/Avocat/Com... — pseudo
    staff normal). Un statut avec l'un OU l'autre flag obtient sa section.

    Statuts (Paul, 2026-08-22) : auparavant une section "🧱 Builders" codée
    en dur (is_builder=True) — remplacée par une boucle générique sur les
    statuts du serveur (member["statuts"], enrichi par ng_staff_manager).
    D'abord limitée aux statuts `requires_second_pseudo=True` (seul Builder
    en avait besoin) ; généralisée (retour utilisateur, même date) avec le
    flag indépendant `has_stafflist_category`, pour que N'IMPORTE QUEL statut
    (com, affilié, journaliste, avocat...) puisse avoir sa propre catégorie
    dans la stafflist, configurable via /ngstaff config → Rank/Derank →
    Statuts, sans avoir besoin d'un pseudo secondaire. Un membre purement
    statut (grade=None) sans catégorie dédiée n'apparaît dans AUCUNE section
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

    # ── Une section dédiée par statut "catégorie stafflist" ──────────────
    # Déclenchée par `has_stafflist_category` OU `requires_second_pseudo`
    # (généralisation, Paul 2026-08-22 — voir docstring). Un membre peut
    # apparaître dans plusieurs de ces sections s'il cumule plusieurs
    # statuts à catégorie dédiée (cas rare mais pas interdit).
    def _has_own_category(s: dict) -> bool:
        return bool(s.get("has_stafflist_category") or s.get("requires_second_pseudo"))

    seen_category_statuts: dict[str, dict] = {}
    for m in members:
        for s in m.get("statuts", []):
            if _has_own_category(s):
                seen_category_statuts.setdefault(s["key"], s)

    for key, statut_meta in seen_category_statuts.items():
        holders = [
            (m, s) for m in members for s in m.get("statuts", [])
            if s["key"] == key and _has_own_category(s)
        ]
        if not holders:
            continue

        emoji = statut_meta.get("emoji") or "🎖️"
        c = Container()
        c.add_item(TextDisplay(f"## {emoji} {statut_meta['label']}s"))
        c.add_item(Separator())

        block = "\n".join(
            build_member_line(m, pseudo_override=s.get("second_pseudo"))
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