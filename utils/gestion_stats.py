"""
utils/gestion_stats.py — Tracking statistiques.

🟡 STUB à remplir par le collègue (DB).

Signature attendue :
    def incrementer_commande(
        nom_commande: str,
        user_id: int,
        guild_id: int | None,
    ) -> None

Doit écrire dans la table `command_stats` (et éventuellement `user_command_stats`
si on veut tracker par utilisateur).

Pour l'instant : ne fait rien (no-op). N'impacte pas le bot.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def incrementer_commande(
    nom_commande: str,
    user_id: int,
    guild_id: int | None,
) -> None:
    """
    🟡 STUB : à câbler à la DB.

    Devra incrémenter la table command_stats pour cette commande.
    """
    # TODO (collègue) :
    #   from utils.managers.stats_manager import increment_command_sync
    #   increment_command_sync(nom_commande, user_id, guild_id)
    log.debug(
        "Stats stub | cmd=%s user=%s guild=%s",
        nom_commande, user_id, guild_id,
    )