"""
utils/medialink/scheduler.py — Transite du MediaEventdéclenche vers le processor.
"""

from __future__ import annotations

import logging

import discord

from utils.db.models.medialink_connection import ConnectionStatus
from utils.db.models.medialink_log import MediaLog, MediaLogLevel
from utils.db.session import get_session

from utils.managers import medialink_manager as medialink_mgr
from utils.medialink import event_manager, processor
from utils.medialink.providers.base import BaseMediaProvider
from utils.medialink.providers.youtube import YouTubeProvider

log = logging.getLogger(__name__)

# Classe de Provider réelle. À compléter ! 
_PROVIDER_CLASSES: dict[str, type[BaseMediaProvider]] = {
    "youtube": YouTubeProvider,
}


async def run_once(bot: discord.Client) -> None:
    connections = await medialink_mgr.list_all_connections()

    for connection in connections:
        if connection["status"] == ConnectionStatus.DISABLED.value:
            continue

        provider_cls = _PROVIDER_CLASSES.get(connection["platform"])
        if provider_cls is None:
            continue

        await _poll_connection(bot, connection, provider_cls)


async def _poll_connection(bot: discord.Client, connection: dict, provider_cls: type[BaseMediaProvider]) -> None:
    provider = provider_cls()
    try:
        await provider.connect(connection["external_id"])
        events = await provider.fetch_events()

    except Exception as exc:
        log.warning("[MEDIALINK] fetch_events() échoué connection=%s platform=%s: %s", connection["id"], connection["platform"], exc)
        await medialink_mgr.set_connection_status(connection["id"], connection["guild_id"], ConnectionStatus.ERROR.value)
        await _log(connection["guild_id"], connection["id"], MediaLogLevel.ERROR, "connection.check_failed", str(exc))
        return
    
    finally:
        try:
            await provider.disconnect()
        except Exception:
            log.debug("[MEDIALINK] disconnect() a levé une exception (ignorée) connection=%s", connection["id"])

    await medialink_mgr.set_connection_status(connection["id"], connection["guild_id"], ConnectionStatus.OPERATIONAL.value)

    for event in events:
        event.connection_id = connection["id"]

        routed = await event_manager.ingest(event)
        if routed is None:
            continue

        await medialink_mgr.touch_last_event(connection["id"], connection["guild_id"])
        await processor.process(bot, routed)


async def _log(guild_id: int, connection_id: int, level: MediaLogLevel, event_type: str, message: str) -> None:
    async with get_session() as session:
        session.add(MediaLog(
            guild_id=guild_id,
            connection_id=connection_id,
            level=level.value,
            event_type=event_type,
            message=message[:2000],
        ))