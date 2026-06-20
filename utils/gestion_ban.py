"""
utils/gestion_ban.py — Gestion des bans globaux du bot.

Implémentation : délègue à utils.managers.bot_ban_manager (table bot_bans).
Tous les bans sont des tempbans (durée en jours) — un ban de facto
permanent est créé avec duree_jours=9999, il n'y a pas de notion de ban
"infini" distincte en DB.

⚠️ Ces deux fonctions sont ASYNC (contrairement au stub d'origine, qui les
définissait en synchrone). Seul appelant : utils.botbancmd.verifier_ban_utilisateur,
déjà adapté en conséquence.
"""
from __future__ import annotations

import logging

from utils.managers.bot_ban_manager import get_ban_info, is_banned

log = logging.getLogger(__name__)


async def est_banni(user_id: int) -> tuple[bool, str]:
    """
    Retourne (True, "raison du ban") si l'utilisateur est banni (et le ban
    est encore actif), sinon (False, "").

    Ne doit jamais lever d'exception côté appelant : si la DB est
    indisponible, on considère l'utilisateur NON banni par sécurité
    (ne jamais bloquer l'usage du bot à cause d'une panne DB).
    """
    try:
        return await is_banned(user_id)
    except Exception as e:
        log.warning("[GESTION_BAN] Échec vérification ban pour %s : %s", user_id, e)
        return False, ""


async def obtenir_info_ban(user_id: int) -> dict | None:
    """
    Retourne le détail du ban actif (discord_id, raison, moderator_id,
    date_ban, expiration — datetimes timezone-aware), ou None si absent,
    expiré, ou en cas d'erreur DB.
    """
    try:
        return await get_ban_info(user_id)
    except Exception as e:
        log.warning("[GESTION_BAN] Échec récupération info ban pour %s : %s", user_id, e)
        return None