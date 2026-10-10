"""
views/ngstaff/rank_view.py — Annonces publiques du système de rank,
généralisé multi-serveurs (ex-views/alpha/rank_view.py).

Extrait à l'origine de cogs/alpha/rank.py (supprimé depuis, remplacé par
cogs/ngstaff/ngstaff_rank.py) : cog + logique métier allégés, construction
des views ici.

Toutes en LayoutView simple, PAS BaseLayoutView : aucun de ces messages n'a
de composant interactif (aucun bouton, aucun select) — ce sont des annonces
publiques postées une fois, avec timeout=None.
"""
from __future__ import annotations

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.db.models.staff_grades import GRADE_LABELS

# ============================================================
# 🧩 Construction des views
# ============================================================

def build_grade_announcement(
    membre: discord.Member, grade: str, is_promotion: bool, old_grade: str | None,
    *, emoji: str | None = None, ping_role_id: int | None = None,
) -> LayoutView:
    """Annonce publique pour un changement de grade (staff).

    `emoji` : emoji d'annonce configuré par serveur (NGRankConfig.rank_emoji,
    cf. /ngstaff config → Rank/Derank → Emoji annonce). Auparavant codé en
    dur sur l'emoji custom d'Alpha (<:Alpha:1500414179650048070>) pour tous
    les serveurs NG — corrigé (Paul, 2026-08-22). Absent/vide = pas de préfixe.
    `ping_role_id` : rôle à @mentionner dans ce message, configuré par
    serveur (NGRankConfig.rank_ping_id, cf. /ngstaff config → Rank/Derank →
    Pings). Option ajoutée le 2026-10-10 ; None/absent = pas de ping, comme
    avant.
    """
    label = GRADE_LABELS.get(grade, grade)
    old_label = GRADE_LABELS.get(old_grade, old_grade) if old_grade else None
    prefix = f"{emoji} " if emoji else ""
    ping = f"<@&{ping_role_id}> " if ping_role_id else ""

    view = LayoutView(timeout=None)
    c = Container()

    if is_promotion and old_label:
        c.add_item(TextDisplay(
            f"{prefix}{ping}Félicitations à <@{membre.id}> qui passe de **{old_label}** à **{label}** !"
        ))
    else:
        c.add_item(TextDisplay(
            f"{prefix}{ping}Bienvenue à <@{membre.id}> qui rejoint l'équipe en tant que **{label}** !"
        ))

    view.add_item(c)
    return view


def build_statut_announcement(
    membre: discord.Member, label: str, *, badge: str | None = None, emoji: str | None = None,
    ping_role_id: int | None = None,
) -> LayoutView:
    """Annonce publique pour l'attribution d'un statut secondaire (statut
    librement défini par serveur, ex: journaliste/affilié/builder).

    `label`/`badge` viennent désormais directement de la définition du
    statut (NGStatutDef, via ng_statut_manager) plutôt que du dict figé
    SECONDARY_STATUSES — généralisation multi-serveurs (Paul, 2026-08-22).
    `emoji` : voir build_grade_announcement — même correction (emoji configuré
    par serveur au lieu du logo Alpha en dur).
    `ping_role_id` : voir build_grade_announcement — même rôle de ping
    optionnel (NGRankConfig.rank_ping_id), même message public.
    """
    badge = badge or ""
    prefix = f"{emoji} " if emoji else ""
    ping = f"<@&{ping_role_id}> " if ping_role_id else ""

    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(
        f"{prefix}{ping}<@{membre.id}> rejoint l'équipe des **{label}** ! {badge}".rstrip()
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
