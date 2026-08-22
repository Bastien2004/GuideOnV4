"""
views/alpha/rank_view.py — Annonces publiques du système de rank Alpha.

Extrait de cogs/alpha/rank.py, même traitement que event_start, event_regle,
index et derank : cog + logique métier allégés, construction des views ici.

Toutes en LayoutView simple, PAS BaseLayoutView : aucun de ces messages n'a
de composant interactif (aucun bouton, aucun select) — ce sont des annonces
publiques postées une fois, avec timeout=None. Même cas que
views/alpha/index_view.py, views/alpha/event_regle_view.py, etc.
"""
from __future__ import annotations

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.db.models.alpha_staff import GRADE_LABELS, SECONDARY_STATUSES

# ============================================================
# 🧩 Construction des views
# ============================================================

def build_grade_announcement(
    membre: discord.Member, grade: str, is_promotion: bool, old_grade: str | None,
    *, emoji: str | None = None,
) -> LayoutView:
    """Annonce publique pour un changement de grade (staff).

    `emoji` : emoji d'annonce configuré par serveur (NGRankConfig.rank_emoji,
    cf. /ngstaff config → Rank/Derank → Emoji annonce). Auparavant codé en
    dur sur l'emoji custom d'Alpha (<:Alpha:1500414179650048070>) pour tous
    les serveurs NG — corrigé (Paul, 2026-08-22). Absent/vide = pas de préfixe.
    """
    label = GRADE_LABELS.get(grade, grade)
    old_label = GRADE_LABELS.get(old_grade, old_grade) if old_grade else None
    prefix = f"{emoji} " if emoji else ""

    view = LayoutView(timeout=None)
    c = Container()

    if is_promotion and old_label:
        c.add_item(TextDisplay(
            f"{prefix}Félicitations à <@{membre.id}> qui passe de **{old_label}** à **{label}** !"
        ))
    else:
        c.add_item(TextDisplay(
            f"{prefix}Bienvenue à <@{membre.id}> qui rejoint l'équipe en tant que **{label}** !"
        ))

    view.add_item(c)
    return view


def build_statut_announcement(membre: discord.Member, statut: str, *, emoji: str | None = None) -> LayoutView:
    """Annonce publique pour l'attribution d'un statut secondaire (journaliste/affilié/builder).

    `emoji` : voir build_grade_announcement — même correction (emoji configuré
    par serveur au lieu du logo Alpha en dur).
    """
    meta = SECONDARY_STATUSES[statut]
    label = meta["label"]
    badge = meta["badge"] or ""
    prefix = f"{emoji} " if emoji else ""

    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(
        f"{prefix}<@{membre.id}> rejoint l'équipe des **{label}** ! {badge}".rstrip()
    ))
    view.add_item(c)
    return view


def build_journaliste_message(
    pseudo_jeu: str, label: str, journaliste_ping_id: int | None, is_promotion: bool
) -> LayoutView:
    """Message pour les journalistes (affiche de félicitations)."""
    ping = f"<@&{journaliste_ping_id}> " if journaliste_ping_id else ""
    action = "promu" if is_promotion else "rank"

    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# 📸 Affiche de rank"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"Hey {ping} ! **{pseudo_jeu}** a été **{action}** **{label}** !\n"
        f"Merci de lui préparer et de poster l'affiche de félicitations. 🎨"
    ))
    view.add_item(c)
    return view


def build_dev_message(pseudo_jeu: str, dev_ping_id: int | None) -> LayoutView:
    """Message pour les développeurs (emoji head)."""
    ping = f"<@&{dev_ping_id}> " if dev_ping_id else ""
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# 🖼️ Emoji — Nouveau staff"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"Hey {ping} ! Merci d'ajouter l'**emoji head** pour **{pseudo_jeu}** (nouveau staff).\n"
        f"Une fois l'emoji créé sur le DDP, n'oubliez pas de l'ajouter via `/dev edit_list`. 🎭"
    ))
    view.add_item(c)
    return view