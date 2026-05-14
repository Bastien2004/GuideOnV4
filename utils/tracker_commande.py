"""
Tracker d'utilisation des commandes.

TODO (avec ton collègue dev) : appelle stats_manager.increment_command(name)
qui écrira en table command_stats.

En attendant, log juste.
"""
import logging

log = logging.getLogger(__name__)


async def track_command(command_name: str) -> None:
    """À appeler depuis chaque commande, après son exécution réussie."""
    # TODO: await stats_manager.increment_command(session, command_name)
    log.debug("Tracking commande : %s", command_name)
