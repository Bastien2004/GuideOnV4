"""
utils/medialink/event_manager.py — Event Manager du pipeline (§8) :
reçoit les MediaEvent produits par les Providers, applique l'anti-doublon
(§9.1), résout les règles (Rules) à appliquer, et transmet au Processor
pour envoi.

Ce fichier ne connaît AUCUNE plateforme précise (§8.1) : il ne travaille
que sur des MediaEvent déjà normalisés et sur les tables media_connections
/ media_rules. Toute la logique spécifique YouTube/Twitch/TikTok/Reddit
reste dans les Providers respectifs (utils/medialink/providers/).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from utils.db.models.medialink_event import MediaEventRecord, MediaEventStatus
from utils.db.models.medialink_rule import MediaRule
from utils.db.session import get_session
from utils.medialink.event import MediaEvent


@dataclass(slots=True)
class RoutedEvent:
    """Un MediaEvent devenu persistant (MediaEventRecord créé) et associé
    aux règles qui doivent le traiter — c'est ce que consomme
    processor.py, PAS le MediaEvent brut."""

    event: MediaEvent
    record_id: int
    rules: list[MediaRule]


async def ingest(event: MediaEvent) -> RoutedEvent | None:
    """Point d'entrée unique du Core pour un événement fraîchement
    produit par un Provider (via le Scheduler, cf. scheduler.py).

    Renvoie None si l'événement est un doublon (déjà connu pour cette
    connexion) — dans ce cas il est silencieusement ignoré, ce n'est pas
    une erreur (§9.1 : le doublon est un cas normal, pas exceptionnel,
    ex: un polling qui re-liste les N derniers posts à chaque passage).
    """
    if event.connection_id is None:
        # Un Provider ne connaît pas les connection_id internes — c'est
        # au Scheduler de les assigner avant d'appeler ingest() (il sait
        # quelle instance de Provider correspond à quelle MediaConnection).
        raise ValueError(
            "MediaEvent.connection_id doit être résolu avant ingest() "
            "(cf. scheduler.py)"
        )

    record_id = await _persist_if_new(event)
    if record_id is None:
        return None

    rules = await _resolve_rules(event.connection_id, event.event_type)
    return RoutedEvent(event=event, record_id=record_id, rules=rules)


async def _persist_if_new(event: MediaEvent) -> int | None:
    """Implémente l'anti-doublon (§9.1) : la contrainte unique
    (connection_id, external_event_id) sur media_events FAIT le travail
    — on tente l'insertion, un IntegrityError signifie "déjà vu"."""
    async with get_session() as session:
        row = MediaEventRecord(
            connection_id=event.connection_id,
            external_event_id=event.external_id,
            event_type=event.event_type,
            title=event.title,
            url=event.url,
            thumbnail=event.thumbnail,
            author=event.author,
            published_at=event.published_at,
            status=MediaEventStatus.PENDING.value,
        )
        session.add(row)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            return None
        return row.id


async def _resolve_rules(connection_id: int, event_type: str) -> list[MediaRule]:
    """Règles actives correspondant à ce type d'événement pour cette
    connexion — "une même connexion peut posséder plusieurs règles
    indépendantes" (§3), donc toujours une LISTE, jamais une seule
    règle supposée unique."""
    async with get_session() as session:
        result = await session.execute(
            select(MediaRule).where(
                MediaRule.connection_id == connection_id,
                MediaRule.event_type == event_type,
                MediaRule.enabled.is_(True),
            )
        )
        return list(result.scalars().all())
