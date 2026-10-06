"""
utils/medialink/event_manager.py — Traitement des MediaEvent jusqu'au processor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from utils.db.models.medialink_event import MediaEventRecord, MediaEventStatus
from utils.db.models.medialink_rule import MediaRule
from utils.db.session import get_session
from utils.medialink.event import MediaEvent


@dataclass(slots=True)
class RoutedEvent:

    event: MediaEvent
    record_id: int
    rules: list[MediaRule]


async def ingest(event: MediaEvent) -> RoutedEvent | None:

    if event.connection_id is None:
        raise ValueError("MediaEvent.connection_id doit être résolu avant ingest() (cf. scheduler.py)")

    record_id = await _persist_if_new(event)
    if record_id is None:
        return None

    rules = await resolve_active_rules(event.connection_id, event.event_type)
    return RoutedEvent(event=event, record_id=record_id, rules=rules)


async def _persist_if_new(event: MediaEvent) -> int | None:
    """Système anti doublon."""

    return await _persist_with_status(event, MediaEventStatus.PENDING)


async def _persist_with_status(
    event: MediaEvent, status: MediaEventStatus, *, processed_at: datetime | None = None,
) -> int | None:
    """Insère `event` dans media_events avec le statut donné, si son
    (connection_id, external_event_id) n'existe pas déjà — factorisé hors
    de _persist_if_new pour être réutilisé par seed_baseline_events()
    ci-dessous (même anti-doublon, statut différent). Renvoie None (sans
    lever) si l'événement existait déjà, exactement comme avant."""

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
            status=status.value,
            processed_at=processed_at,
        )
        session.add(row)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            return None
        return row.id


async def seed_baseline_events(connection_id: int, events: list[MediaEvent]) -> int:
    """Immunise une connexion tout juste créée contre un envoi rétroactif."""

    now = datetime.now(timezone.utc)
    seeded = 0
    for event in events:
        event.connection_id = connection_id
        record_id = await _persist_with_status(event, MediaEventStatus.SKIPPED, processed_at=now)
        if record_id is not None:
            seeded += 1
    return seeded


async def resolve_active_rules(connection_id: int, event_type: str) -> list[MediaRule]:
    """Gestion de la règle de l'évenement."""
    
    async with get_session() as session:
        result = await session.execute(
            select(MediaRule).where(
                MediaRule.connection_id == connection_id,
                MediaRule.event_type == event_type,
                MediaRule.enabled.is_(True),
            )
        )
        return list(result.scalars().all())