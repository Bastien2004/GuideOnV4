"""
utils/medialink/processor.py — Gestion du processus d'envoi.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import discord

from utils.db.models.medialink_connection import MediaConnection
from utils.db.models.medialink_event import MediaEventRecord, MediaEventStatus
from utils.db.models.medialink_log import MediaLog, MediaLogLevel
from utils.db.models.medialink_rule import MediaRule
from utils.db.session import get_session

from utils.medialink import event_manager
from utils.medialink.event import MediaEvent
from utils.medialink.event_manager import RoutedEvent
from utils.medialink.notification import NotificationError, send

log = logging.getLogger(__name__)

MAX_SEND_ATTEMPTS = 3
_RETRY_DELAYS_SECONDS = (2.0, 5.0)
_NON_RETRYABLE = (discord.Forbidden, discord.NotFound, NotificationError)


async def process(bot: discord.Client, routed_event: RoutedEvent) -> None:
    """Traite un événement."""

    await _mark_processing(routed_event.record_id)

    if not routed_event.rules:
        await _mark_done(routed_event.record_id, MediaEventStatus.SKIPPED)
        return

    any_success = False
    last_error: str | None = None

    for rule in routed_event.rules:
        try:
            await _send_with_retry(bot, routed_event, rule)
            any_success = True

        except Exception as exc:
            last_error = str(exc) or exc.__class__.__name__
            log.warning("[MEDIALINK] Échec d'envoi rule=%s channel=%s: %s", rule.id, rule.channel_id, exc)
            await _log_failure(routed_event.event, rule, exc)

    if any_success:
        await _mark_done(routed_event.record_id, MediaEventStatus.SENT, last_error=None)
    else:
        await _mark_done(routed_event.record_id, MediaEventStatus.FAILED, last_error=last_error)


async def replay(bot: discord.Client, record_id: int) -> None:
    """Rejoue un événement déjà traité."""

    async with get_session() as session:
        record = await session.get(MediaEventRecord, record_id)
        
        if record is None:
            raise ValueError(f"MediaEventRecord {record_id} introuvable — impossible de le rejouer.")
        connection = await session.get(MediaConnection, record.connection_id)

    event = MediaEvent(
        platform=connection.platform if connection is not None else "",
        event_type=record.event_type,
        external_id=record.external_event_id,
        title=record.title,
        url=record.url,
        thumbnail=record.thumbnail,
        author=record.author,
        published_at=record.published_at,
        connection_id=record.connection_id,
    )
    rules = await event_manager.resolve_active_rules(record.connection_id, record.event_type)
    await process(bot, RoutedEvent(event=event, record_id=record.id, rules=rules))


async def _send_with_retry(bot: discord.Client, routed_event: RoutedEvent, rule: MediaRule) -> None:
    last_exc: Exception | None = None
    for attempt in range(MAX_SEND_ATTEMPTS):
        try:
            await send(bot, routed_event, rule)
            return
        except _NON_RETRYABLE:
            raise
        except discord.HTTPException as exc:
            last_exc = exc
            if attempt < MAX_SEND_ATTEMPTS - 1:
                await asyncio.sleep(_RETRY_DELAYS_SECONDS[attempt])
    assert last_exc is not None
    raise last_exc


async def _mark_processing(record_id: int) -> None:
    async with get_session() as session:
        record = await session.get(MediaEventRecord, record_id)
        if record is None:
            return
        record.status = MediaEventStatus.PROCESSING.value
        record.attempts += 1


async def _mark_done(record_id: int, status: MediaEventStatus, *, last_error: str | None = None) -> None:
    async with get_session() as session:
        record = await session.get(MediaEventRecord, record_id)
        if record is None:
            return
        record.status = status.value
        record.processed_at = datetime.now(timezone.utc)
        record.last_error = last_error


async def _log_failure(event: MediaEvent, rule: MediaRule, exc: Exception) -> None:
    async with get_session() as session:
        connection = await session.get(MediaConnection, event.connection_id)
        guild_id = connection.guild_id if connection is not None else 0
        session.add(MediaLog(
            guild_id=guild_id,
            connection_id=event.connection_id,
            level=MediaLogLevel.ERROR.value,
            event_type="event.send_failed",
            message=f"Échec d'envoi vers #{rule.channel_id} (règle {rule.id}) : {exc}"[:2000],
        ))