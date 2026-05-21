"""
utils/permission.py — Accès aux permissions.
"""
from __future__ import annotations

import logging

from utils.managers.permission_manager import get_ids_sync, role_from_str

log = logging.getLogger(__name__)


def get_ids(role: str) -> list[int]:
    """
    Retourne la liste des IDs (int) pour un rôle donné (ex: 'DEV', 'OP_ALPHA').
    Lecture sync depuis le cache. Renvoie [] si rôle inconnu ou cache vide.
    """
    try:
        perm_role = role_from_str(role)
    except ValueError:
        log.warning("get_ids appelé avec un rôle inconnu : %r", role)
        return []
    return [int(i) for i in get_ids_sync(perm_role)]


def has_id(role: str, user_id: int) -> bool:
    """True si user_id possède le rôle donné."""
    return user_id in get_ids(role)