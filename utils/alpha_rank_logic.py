"""
utils/alpha_rank_logic.py — Logique centralisée des rôles Discord Alpha
(grades de la hiérarchie staff, rôle équipe transverse, statuts secondaires).

Point d'entrée principal : apply_staff_roles(), appelé par rank.py et
derank.py pour mettre les rôles Discord d'un membre en cohérence avec son
état staff Alpha CIBLE — et non un diff ancien/nouveau. La fonction
recalcule l'état complet à chaque appel (idempotente, auto-réparatrice).

Second point d'entrée : strip_incompatible_statuses(), qui calcule l'état
"statuts secondaires" après retrait automatique de ceux devenus incompatibles
suite à une promotion vers un grade de STATUT_INCOMPATIBLE_GRADES (Admin/SM).
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

# Ordre de priorité du préfixe de pseudo Discord quand AUCUN grade staff
# n'est présent. Builder est volontairement en dernier : il a son propre
# pseudo dédié (pseudo_jeu_builder), donc son label ne sert de préfixe que
# si c'est le SEUL statut actif (aucun autre statut à afficher).
NICK_PREFIX_PRIORITY: tuple[str, ...] = ("affilie", "journaliste", "builder")


def compute_nick_prefix(grade: str | None, secondary: dict[str, bool]) -> str | None:
    """
    Détermine le préfixe de pseudo Discord ("Guide", "Affilié", "Builder"...)
    selon la règle de priorité du projet :

      1. Un grade staff (s'il y en a un) prime toujours sur tout le reste.
      2. Sinon, parmi les statuts secondaires actifs : Affilié > Journaliste > Builder.
      3. Sinon (aucun grade, aucun statut actif) : pas de préfixe (None).

    Retourne le libellé brut (ex: "Guide", "Affilié", "Builder"), à combiner
    par l'appelant avec le pseudo : f"{prefix} | {pseudo}".
    """
    if grade:
        return GRADE_PREFIXES.get(grade, grade)

    for key in NICK_PREFIX_PRIORITY:
        if secondary.get(key):
            return SECONDARY_STATUSES[key]["label"]

    return None


def strip_incompatible_statuses(grade: str | None, secondary: dict[str, bool]) -> dict[str, bool]:
    """
    Retourne une copie de `secondary` avec tous les flags mis à False si
    `grade` est dans STATUT_INCOMPATIBLE_GRADES (administrateur, super_moderateur).
    Ne modifie rien si le grade est compatible — `secondary` est renvoyé tel quel.
    """
    if grade not in STATUT_INCOMPATIBLE_GRADES:
        return dict(secondary)
    return {key: False for key in secondary}


def _all_managed_role_ids(cfg: dict) -> set[int]:
    """Tous les IDs de rôles Discord gérés par ce système (configurés, non-None)."""
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
    """IDs de rôles Discord que le membre DOIT avoir, d'après son état cible."""
    ids: set[int] = set()

    if grade in GRADE_TO_ROLE_ATTR:
        rid = cfg.get(GRADE_TO_ROLE_ATTR[grade])
        if rid:
            ids.add(rid)

        if grade in STAFF_GENERAL_GRADES:
            rid = cfg.get("role_equipe_id")
            if rid:
                ids.add(rid)

    # Si le grade est incompatible (Admin/SM), les statuts cibles sont
    # ignorés ici par sécurité — l'appelant est censé avoir déjà appelé
    # strip_incompatible_statuses() en amont, mais on ne fait pas confiance
    # aveuglément à l'état reçu pour le calcul des rôles Discord.
    effective_secondary = strip_incompatible_statuses(grade, secondary)

    for key, meta in SECONDARY_STATUSES.items():
        if effective_secondary.get(key):
            rid = cfg.get(meta["role_attr"])
            if rid:
                ids.add(rid)

    return ids


async def apply_staff_roles(
    membre: discord.Member,
    cfg: dict,
    *,
    grade: str | None,
    secondary: dict[str, bool] | None = None,
    reason: str = "GuideOn Alpha",
) -> None:
    """
    Met les rôles Discord de `membre` en cohérence avec son état staff Alpha cible.

    grade : un grade de GRADE_TO_ROLE_ATTR (administrateur..guide), ou None
            si le membre n'a aucun grade de la hiérarchie (derank complet
            de la partie grade, ou membre purement journaliste/affilié/builder).
    secondary : {"journaliste": bool, "affilie": bool, "builder": bool}.
                Clé absente = False. Si `grade` est dans
                STATUT_INCOMPATIBLE_GRADES, ces flags sont ignorés pour le
                calcul des rôles (sécurité — voir strip_incompatible_statuses).

    Échecs de permission/HTTP sont loggés en warning sans interrompre l'appelant.
    """
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
            log.warning("[ALPHA ROLES] Ajout impossible pour %s : %s", membre.id, e)

    if to_remove:
        try:
            await membre.remove_roles(*to_remove, reason=reason)
        except (discord.Forbidden, discord.HTTPException) as e:
            log.warning("[ALPHA ROLES] Retrait impossible pour %s : %s", membre.id, e)