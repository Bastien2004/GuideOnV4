"""
utils/medialink/processor.py — fait transiter un RoutedEvent (cf.
event_manager.py) jusqu'au Notification Engine, gère le retry (§9.3) et
le statut final de l'événement (PENDING → PROCESSING → SENT/FAILED,
cf. utils.db.models.medialink_event.MediaEventStatus).

STUB volontairement léger (roadmap V1) — le contrat de statut est déjà
fixé par le modèle DB, donc l'implémentation réelle peut suivre sans
revoir le schéma.

Ce que ce module devra faire, une fois écrit pour de vrai :
  1. Pour chaque règle d'un RoutedEvent, appeler
     notification.send(routed_event, rule) — une règle = un envoi
     indépendant (une règle peut échouer sans affecter les autres, cf.
     §9.3 "un échec sur un salon ne doit pas bloquer les autres").
  2. Marquer le MediaEventRecord PROCESSING avant l'envoi, puis
     SENT/FAILED après, avec last_error rempli sur échec.
  3. Retry (§9.3) : politique de nouvelle tentative à définir — nombre
     de tentatives (MediaEventRecord.attempts existe déjà pour ça),
     backoff, et à partir de quand on abandonne (→ status FAILED
     définitif, visible dans l'historique §16 via media_logs).
  4. Replay manuel (§9.4) : permettre de repasser un événement FAILED (ou
     même SENT, pour renvoyer) à PENDING puis retenter — probablement
     une fonction dédiée `replay(record_id)` plutôt que de réutiliser le
     chemin normal, pour ne pas re-déclencher l'anti-doublon.
"""
from __future__ import annotations

from utils.medialink.event_manager import RoutedEvent


async def process(routed_event: RoutedEvent) -> None:
    """Traite un événement routé : envoie une annonce par règle
    associée, met à jour son statut. Non implémenté dans ce squelette —
    voir docstring de module."""
    raise NotImplementedError("processor.process() — à implémenter (roadmap V1)")


async def replay(record_id: int) -> None:
    """Rejoue un événement déjà traité (§9.4) — non implémenté."""
    raise NotImplementedError("processor.replay() — à implémenter (roadmap V1, §9.4)")
