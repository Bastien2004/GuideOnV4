"""
utils/ng_staff_display.py — Affichage centralisé d'un membre du staff NG
(badges de statuts secondaires), utilisé par stafflist_view.py et
edit_list_view.py pour rester synchronisés.

Malgré le nommage historique "alpha_*" des symboles internes qu'il
utilise (SECONDARY_STATUSES, STATUTS_SECONDAIRES_ORDER), ce module est
100% multi-serveurs : les badges sont identiques quel que soit le
serveur NG (les grades et statuts sont hard-codés dans la refonte, cf.
§10 du prompt). Renommé alpha_staff_display.py → ng_staff_display.py
pour clarifier sa nature réelle.
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