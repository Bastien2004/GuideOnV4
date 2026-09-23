"""
utils/gestion_stats.py — Gestion des statistiques de commandes.

Implémentation : incrémente le compteur quotidien (command_stats_daily)
via utils.managers.command_stats_manager, par serveur (guild_id). Ne
lève jamais d'exception côté appelant — tracker_commande englobe déjà
l'appel dans un try/except, mais on protège aussi ici par défense en
profondeur (si la DB est indisponible, on log et on continue sans
bloquer la commande).
"""
from __future__ import annotations

import logging

from utils.managers.command_stats_manager import increment_command_stat

log = logging.getLogger(__name__)


async def incrementer_commande(nom_commande: str, user_id: int, guild_id: int | None) -> None:
    """
    Incrémente le compteur quotidien d'utilisation de `nom_commande` pour
    `guild_id`. Si guild_id est None (commande utilisée en DM), on ne
    logge pas : une stat "par serveur" n'a pas de sens hors contexte
    serveur.

    Ne doit jamais lever d'exception : si la DB est indisponible, on log
    et on retourne silencieusement.
    """
    if guild_id is None:
        return
    try:
        await increment_command_stat(nom_commande, guild_id)
    except Exception as e:
        log.warning("[GESTION_STATS] Échec incrémentation '%s' (guild=%s) : %s", nom_commande, guild_id, e)