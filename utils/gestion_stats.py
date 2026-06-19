"""
utils/gestion_stats.py — Gestion des statistiques de commandes.

Implémentation : incrémente le compteur quotidien (command_stats_daily)
via utils.managers.command_stats_manager. Ne lève jamais d'exception côté
appelant — tracker_commande englobe déjà l'appel dans un try/except, mais
on protège aussi ici par défense en profondeur (si la DB est indisponible,
on log et on continue sans bloquer la commande).
"""
from __future__ import annotations

import logging

from utils.managers.command_stats_manager import increment_command_stat

log = logging.getLogger(__name__)


async def incrementer_commande(nom_commande: str, user_id: int, guild_id: int | None) -> None:
    """
    Incrémente le compteur quotidien d'utilisation de `nom_commande`.

    user_id et guild_id sont acceptés pour compatibilité avec la signature
    historique et un usage futur éventuel (granularité par utilisateur/
    serveur), mais ne sont PAS utilisés actuellement : le périmètre retenu
    pour /dev stat_cmd est global (toutes commandes confondues, tous
    serveurs/utilisateurs confondus).

    Ne doit jamais lever d'exception : si la DB est indisponible, on log
    et on retourne silencieusement.
    """
    try:
        await increment_command_stat(nom_commande)
    except Exception as e:
        log.warning("[GESTION_STATS] Échec incrémentation '%s' : %s", nom_commande, e)