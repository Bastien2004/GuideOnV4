"""
utils/ng_staff_display.py — Affichage centralisé des grades secondaire stafflist.
"""

from __future__ import annotations


def build_member_badges(member: dict) -> str:
    """Gestion des badges stafflist."""
    badges = [s["emoji"] for s in member.get("statuts", []) if s.get("emoji")]
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