"""
utils/medialink/scheduler.py — déclenche fetch_events() sur chaque
Provider actif à intervalle régulier (§9.2 "Fréquence de polling").

STUB volontairement léger : c'est un composant de la roadmap V1 (B4/B6),
pas un bloquant Phase 0/A1. Le contrat qu'il devra respecter est déjà
fixé par providers/base.py et event_manager.py, donc il peut être
implémenté indépendamment une fois les premiers Providers réels
disponibles (partie API de Bastien).

Ce que ce module devra faire, une fois écrit pour de vrai :
  1. Charger les connexions actives (utils.managers.medialink_manager.
     list_connections, par guild ou globalement selon la stratégie de
     boucle retenue).
  2. Instancier/réutiliser le BaseMediaProvider correspondant à chaque
     connexion (connect() déjà fait, ou fait ici — à trancher).
  3. Appeler fetch_events() à une fréquence qui respecte les limites de
     l'API de chaque plateforme (§9.2) — probablement configurable PAR
     plateforme, pas une constante globale unique.
  4. Résoudre event.connection_id pour chaque MediaEvent produit (un
     Provider ne le connaît pas nativement, cf. event_manager.ingest).
  5. Transmettre à event_manager.ingest(), puis les RoutedEvent renvoyés
     à processor.py.
  6. Mettre à jour MediaConnection.last_checked_at (et status via
     check_status()) après chaque passage, succès ou échec.
"""
from __future__ import annotations


async def run_once() -> None:
    """Un seul passage de polling sur toutes les connexions actives.

    Non implémenté dans ce squelette — voir docstring de module pour le
    contrat attendu. Volontairement une fonction `run_once` plutôt
    qu'une boucle infinie interne : la boucle temporelle (asyncio task
    périodique, ou task loop discord.ext.tasks) doit être décidée avec
    Paul selon comment le reste du bot gère déjà ce genre de tâches
    récurrentes.
    """
    raise NotImplementedError("scheduler.run_once() — à implémenter (roadmap V1, B4/B6)")
