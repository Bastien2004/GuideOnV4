"""
utils/alpha_rank_logic.py — Logique centralisée de la gestion des rôles Discord Alpha.
"""

from __future__ import annotations

import logging

import discord

from utils.db.models.alpha_staff import (
    GRADE_PREFIXES,
    GRADE_TO_ROLE_ATTR,
    SECONDARY_STATUSES,
    STAFF_GENERAL_GRADES,
    STATUT_INCOMPATIBLE_GRADES,
)

log = logging.getLogger(__name__)

NICK_PREFIX_PRIORITY: tuple[str, ...] = ("affilie", "journaliste", "builder")


def compute_nick_prefix(grade: str | None, secondary: dict[str, bool]) -> str | None:
    """Détermine le préfixe de rename de pseudo Discord ("Guide", "Affilié", "Builder"...). """

    if grade:
        return GRADE_PREFIXES.get(grade, grade)

    for key in NICK_PREFIX_PRIORITY:
        if secondary.get(key):
            return SECONDARY_STATUSES[key]["label"]

    return None


def strip_incompatible_statuses(grade: str | None, secondary: dict[str, bool]) -> dict[str, bool]:
    """Vérification de compatibilité."""

    if grade not in STATUT_INCOMPATIBLE_GRADES:
        return dict(secondary)
    return {key: False for key in secondary}


def _all_managed_role_ids(cfg: dict) -> set[int]:
    """Récupère tous les IDs de rôle géré."""

    ids: set[int] = set()

    for grade in GRADE_TO_ROLE_ATTR:
        rid = cfg.get(GRADE_TO_ROLE_ATTR[grade])
        if rid:
            ids.add(rid)

    rid = cfg.get("role_equipe_id")
    if rid:
        ids.add(rid)

    for meta in SECONDARY_STATUSES.values():
        rid = cfg.get(meta["role_attr"])
        if rid:
            ids.add(rid)

    return ids


def _target_role_ids(cfg: dict, grade: str | None, secondary: dict[str, bool]) -> set[int]:
    """Récupération du rôle à distribuer."""

    ids: set[int] = set()

    if grade in GRADE_TO_ROLE_ATTR:
        rid = cfg.get(GRADE_TO_ROLE_ATTR[grade])
        if rid:
            ids.add(rid)

        if grade in STAFF_GENERAL_GRADES:
            rid = cfg.get("role_equipe_id")
            if rid:
                ids.add(rid)

    effective_secondary = strip_incompatible_statuses(grade, secondary)

    for key, meta in SECONDARY_STATUSES.items():
        if effective_secondary.get(key):
            rid = cfg.get(meta["role_attr"])
            if rid:
                ids.add(rid)

    return ids


async def apply_staff_roles(membre: discord.Member, cfg: dict, *, grade: str | None, secondary: dict[str, bool] | None = None, reason: str = "GuideOn Alpha") -> None:
    """Applique le don ou le retrait de rôle."""

    secondary = secondary or {}

    target_ids = _target_role_ids(cfg, grade, secondary)
    managed_ids = _all_managed_role_ids(cfg)
    current_ids = {r.id for r in membre.roles}

    to_add_ids = target_ids - current_ids
    to_remove_ids = (managed_ids - target_ids) & current_ids

    guild = membre.guild
    to_add = [r for rid in to_add_ids if (r := guild.get_role(rid)) is not None]
    to_remove = [r for rid in to_remove_ids if (r := guild.get_role(rid)) is not None]

    if to_add:
        try:
            await membre.add_roles(*to_add, reason=reason)
        except (discord.Forbidden, discord.HTTPException) as e:
            log.warning("[ALPHA RANK] Ajout du rôle impossible pour %s : %s", membre.id, e)

    if to_remove:
        try:
            await membre.remove_roles(*to_remove, reason=reason)
        except (discord.Forbidden, discord.HTTPException) as e:
            log.warning("[ALPHA RANK] Retrait du rôle impossible pour %s : %s", membre.id, e)