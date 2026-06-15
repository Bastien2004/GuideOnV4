"""
utils/gestion_ban.py — Gestion des bans bot.

🟡 STUB à remplir par le collègue (DB).

Signatures attendues :
    def est_banni(user_id: int) -> tuple[bool, str]
        Retourne (True, "raison du ban") si l'user est ban, sinon (False, "").

    def obtenir_info_ban(user_id: int) -> dict | None
        Retourne {
            "date_ban": "ISO datetime string",
            "expiration": "ISO datetime string" | None,
            "raison": str,
            "moderator_id": int,
        } si ban existant, sinon None.

Doit lire la table `bot_bans` en DB.

Pour l'instant : aucun user n'est ban (no-op safe).
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def est_banni(user_id: int) -> tuple[bool, str]:
    """
    🟡 STUB : retourne (False, "") = personne n'est ban.

    À câbler à la DB par le collègue.
    """
    # TODO (collègue) :
    #   from utils.managers.ban_manager import is_user_banned_sync
    #   return is_user_banned_sync(user_id)
    return (False, "")


def obtenir_info_ban(user_id: int) -> dict | None:
    """
    🟡 STUB : retourne None = pas d'info de ban.

    À câbler à la DB par le collègue.
    """
    # TODO (collègue) :
    #   from utils.managers.ban_manager import get_ban_info_sync
    #   return get_ban_info_sync(user_id)
    return None