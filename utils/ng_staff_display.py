"""
utils/ng_staff_display.py — Affichage centralisé des grades secondaire stafflist.
"""

from __future__ import annotations


def build_member_badges(member: dict) -> str:
    """Gestion des badges stafflist."""
    badges = [s["emoji"] for s in member.get("statuts", []) if s.get("emoji")]
    return (" " + " ".join(badges)) if badges else ""


def build_member_line(member: dict, *, with_id: bool = True, pseudo_override: str | None = None) -> str:
    """Construit l'affichage des membres dans la stafflist."""
    badges = build_member_badges(member)
    id_part = f" — `{member['discord_id']}`" if with_id else ""
    skin = member.get("skin_head_emoji") or ""
    skin_part = f"{skin} " if skin else ""
    pseudo = pseudo_override or member["pseudo_jeu"]
    return f"{skin_part}**{pseudo}** — <@{member['discord_id']}>{id_part}{badges}"