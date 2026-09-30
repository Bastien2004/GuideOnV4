"""
views/ngstaff/stafflist_view.py — Effectif staff, multi-serveurs
(ex-views/alpha/stafflist_view.py).

Extrait à l'origine de cogs/alpha/stafflist.py (supprimé depuis, remplacé
par /ngstaff stafflist).

Reste en LayoutView simple, PAS BaseLayoutView : ce message n'a aucun
composant interactif (aucun bouton, aucun select) et est posté/édité
publiquement dans un salon pour tout le monde, avec timeout=None (persiste
indéfiniment, volontairement). BaseLayoutView n'apporterait rien ici.

PAGINATION (2026-09, bug de prod sur Iris — voir
utils/managers/ng_stafflist_manager.py) : Discord refuse un message dont
le texte cumulé de tous les composants dépasse 4000 caractères
("Components displayable text size exceeds maximum size of 4000"). Ce
n'était pas un problème quand la stafflist était courte, mais un serveur
avec suffisamment de staff/statuts finit par dépasser cette limite sur un
message unique. `build_stafflist_view` retourne donc maintenant une LISTE
de LayoutView (une par "page"), chacune tenant sous la limite — jamais un
seul LayoutView. Les appelants (ng_stafflist_manager.sync_stafflist_messages,
partagé par /ngstaff stafflist et refresh_staff_message) gèrent l'envoi/
édition d'un message Discord par page.
"""
from __future__ import annotations

from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.ng_staff_display import build_member_line
from utils.ng_server_display import get_server_display_name, get_server_emoji
from utils.db.models.staff_grades import GRADE_EMOJIS, GRADE_LABELS, GRADES_ORDER

# Marge de sécurité sous la limite Discord réelle de 4000 caractères de
# texte cumulé par message (Components V2) — laisse de la place pour les
# écarts entre notre comptage (longueur des chaînes ajoutées) et le
# comptage exact de Discord (formatage, emojis, etc.).
_PAGE_CHAR_BUDGET = 3800

_FOOTER_TEXT = "-# GuideOn Studio"


def _split_block_into_containers(emoji: str, label: str, lines: list[str], budget: int) -> list[tuple[Container, int]]:
    """
    Découpe un bloc (grade ou statut à catégorie dédiée) en un ou plusieurs
    Container tenant chacun sous `budget` caractères. La quasi-totalité des
    blocs tiennent en un seul Container (comportement identique à avant) ;
    seul un bloc anormalement volumineux (beaucoup de membres dans un même
    grade/statut) est réparti sur plusieurs, avec un « (suite) » sur les
    continuations.

    Retourne une liste de (Container, coût_en_caractères) — le coût sert
    au remplissage glouton des pages dans build_stafflist_view.
    """
    containers: list[tuple[Container, int]] = []
    remaining = lines[:]
    first = True
    while remaining:
        title = f"## {emoji} {label}" + ("" if first else " *(suite)*")
        used = len(title)
        chunk: list[str] = []
        while remaining:
            joiner_cost = 1 if chunk else 0  # le "\n" de jointure entre lignes
            candidate_cost = len(remaining[0]) + joiner_cost
            if chunk and used + candidate_cost > budget:
                break
            chunk.append(remaining.pop(0))
            used += candidate_cost
        if not chunk:
            # Une ligne isolée dépasse déjà le budget à elle seule (cas
            # extrême) — on la garde seule plutôt que de boucler à l'infini
            # sans jamais progresser.
            chunk.append(remaining.pop(0))
            used = len(title) + len(chunk[0])

        c = Container()
        c.add_item(TextDisplay(title))
        c.add_item(Separator())
        c.add_item(TextDisplay("\n".join(chunk)))
        c.add_item(Separator())
        containers.append((c, used))
        first = False

    return containers


def build_stafflist_view(members: list[dict], *, server: str) -> list[LayoutView]:
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

    Retourne une LISTE de LayoutView (une par page — voir note pagination
    en tête de fichier), jamais un LayoutView unique.
    """
    display_name = get_server_display_name(server)
    header_emoji = get_server_emoji(server)

    # ── Construction des blocs (indépendants de la pagination) ──────────
    blocks: list[tuple[str, str, list[str]]] = []  # (emoji, label, lignes)

    for grade in GRADES_ORDER:
        grade_members = [m for m in members if m["grade"] == grade]
        if not grade_members:
            continue
        emoji = GRADE_EMOJIS.get(grade, "•")
        label = GRADE_LABELS.get(grade, grade.replace("_", " ").title())
        lines = [build_member_line(m) for m in grade_members]
        blocks.append((emoji, label, lines))

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
        label = f"{statut_meta['label']}s"
        lines = [
            build_member_line(m, pseudo_override=s.get("second_pseudo"))
            for m, s in holders
        ]
        blocks.append((emoji, label, lines))

    # ── Découpage de chaque bloc en Container(s) taillés au budget ───────
    scored_containers: list[tuple[Container, int]] = []
    for emoji, label, lines in blocks:
        scored_containers.extend(_split_block_into_containers(emoji, label, lines, _PAGE_CHAR_BUDGET))

    # ── Répartition gloutonne des Container sur les pages ─────────────────
    # Marge pessimiste pour le header et le footer (réservée même avant de
    # savoir le nombre total de pages) — la pagination "(12/12)" est
    # affichée dans le FOOTER, à côté de "GuideOn Studio" (Paul,
    # 2026-09-28 : elle était auparavant dans le titre du header).
    header_reserve = len(f"# {header_emoji} Effectif Staff {display_name}")
    footer_reserve = len(_FOOTER_TEXT) + len(" (99/99)")
    base_reserve = header_reserve + footer_reserve

    pages_containers: list[list[Container]] = [[]]
    pages_chars: list[int] = [base_reserve]

    for container, cost in scored_containers:
        if pages_containers[-1] and pages_chars[-1] + cost > _PAGE_CHAR_BUDGET:
            pages_containers.append([])
            pages_chars.append(base_reserve)
        pages_containers[-1].append(container)
        pages_chars[-1] += cost

    total_pages = len(pages_containers)

    # ── Construction des LayoutView finales ───────────────────────────────
    views: list[LayoutView] = []
    for page_no, containers in enumerate(pages_containers, start=1):
        view = LayoutView(timeout=None)

        header = Container()
        title = f"# {header_emoji} Effectif Staff {display_name}"
        header.add_item(TextDisplay(title))
        view.add_item(header)

        for c in containers:
            view.add_item(c)

        footer = Container()
        footer_text = _FOOTER_TEXT
        if total_pages > 1:
            footer_text += f" ({page_no}/{total_pages})"
        footer.add_item(TextDisplay(footer_text))
        view.add_item(footer)

        views.append(view)

    return views