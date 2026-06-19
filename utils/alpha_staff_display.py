"""
utils/alpha_staff_display.py — Affichage centralisé d'un membre du staff
Alpha (badges de statuts secondaires), utilisé par stafflist.py et
edit_list_view.py pour rester synchronisés.
"""
from __future__ import annotations

from utils.db.models.alpha_staff import SECONDARY_STATUSES, STATUTS_SECONDAIRES_ORDER


def build_member_badges(member: dict) -> str:
    """
    Construit la chaîne de badges (ex: " 📰 🎥") pour un membre, à partir des
    statuts secondaires actifs ayant un badge défini (Builder n'en a pas —
    il a sa propre section dédiée dans la stafflist, pas de badge inline).

    Retourne une chaîne commençant par un espace si au moins un badge est
    présent, sinon une chaîne vide (directement concaténable après le pseudo).
    """
    badges = [
        SECONDARY_STATUSES[key]["badge"]
        for key in STATUTS_SECONDAIRES_ORDER
        if member.get(f"is_{key}") and SECONDARY_STATUSES[key]["badge"]
    ]
    return (" " + " ".join(badges)) if badges else ""


def build_member_line(member: dict, *, with_id: bool = True) -> str:
    """
    Construit la ligne d'affichage standard d'un membre dans la stafflist
    (ou l'édition) : "{skin} **{pseudo}** — @mention — `id`{badges}".
    """
    badges = build_member_badges(member)
    id_part = f" — `{member['discord_id']}`" if with_id else ""
    skin = member.get("skin_head_emoji") or ""
    skin_part = f"{skin} " if skin else ""
    return f"{skin_part}**{member['pseudo_jeu']}** — <@{member['discord_id']}>{id_part}{badges}"