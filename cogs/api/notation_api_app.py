"""
cogs/api/notation_api_app.py — API Notations
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from starlette import status

from utils.managers import notations_manager as nm

from cogs.api.base import app, limiter, require_token

import logging
log = logging.getLogger(__name__)


_VALID_TIME_KEYS = [
    "time_ask_availability",
    "time_ask_beginning",
    "time_ask_finish",
    "time_send_notations",
]


TIME_KEY_MAPPING = {
    "time_ask_availability": {
        "weekday": "send_presence_weekday",
        "hour": "send_presence_hour",
        "minute": "send_presence_minute",
    },
    "time_ask_beginning": {  # Deadline
        "weekday": "deadline_weekday",
        "hour": "deadline_hour",
        "minute": "deadline_minute",
    },
    "time_ask_finish": {  # Envoi public
        "weekday": "send_public_weekday",
        "hour": "send_public_hour",
        "minute": "send_public_minute",
    },
    "time_send_notations": {
        "weekday": "send_public_weekday",
        "hour": "send_public_hour",
        "minute": "send_public_minute",
    },
}

IDS_MAPPING = {
    "guild_id": "guild_id",
    "staff_chan_id": "channel_staff_id",
    "notif_chan_id": "channel_public_id",
    "logs_chan_id": "channel_logs_id",
    "role_id": "role_id",
}


class TimeSchedule(BaseModel):
    weekday: int
    hour: int
    minute: int


class NotationConfigUpdate(BaseModel):
    id_guild_notations: int
    id_channel_staff_notations: int
    id_channel_notations: int
    id_channel_logs: int
    id_role_notation: int
    time_ask_availability: TimeSchedule | None = None
    time_ask_beginning: TimeSchedule | None = None
    time_ask_finish: TimeSchedule | None = None
    time_send_notations: TimeSchedule | None = None


class SetIdsPayload(BaseModel):
    guild_id: int | None = None
    staff_chan_id: int | None = None
    notif_chan_id: int | None = None
    logs_chan_id: int | None = None
    role_id: int | None = None


class SetTimePayload(BaseModel):
    key: str
    schedule: TimeSchedule


# ──────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────

@app.get("/notations", dependencies=[Depends(require_token)])
async def get_notation_config(request: Request):
    """Récupère la config notations et retourne directement les champs BD"""
    return await nm.get_config()


@app.post("/notations/update_all", dependencies=[Depends(require_token)])
async def update_full_config(request: Request, config: NotationConfigUpdate):
    """Met à jour la config complète (tous les champs)"""

    payload = {
        "guild_id": config.id_guild_notations,
        "channel_staff_id": config.id_channel_staff_notations,
        "channel_public_id": config.id_channel_notations,
        "channel_logs_id": config.id_channel_logs,
        "role_id": config.id_role_notation,
    }

    if config.time_ask_availability:
        payload["send_presence_weekday"] = config.time_ask_availability.weekday
        payload["send_presence_hour"] = config.time_ask_availability.hour
        payload["send_presence_minute"] = config.time_ask_availability.minute

    if config.time_ask_beginning:
        payload["deadline_weekday"] = config.time_ask_beginning.weekday
        payload["deadline_hour"] = config.time_ask_beginning.hour
        payload["deadline_minute"] = config.time_ask_beginning.minute

    if config.time_ask_finish:
        payload["send_public_weekday"] = config.time_ask_finish.weekday
        payload["send_public_hour"] = config.time_ask_finish.hour
        payload["send_public_minute"] = config.time_ask_finish.minute

    log.info("[Notations] update_full_config payload: %s", payload)

    updated = await nm.update_full_config(payload)
    return updated


@app.post("/notations/set_ids", dependencies=[Depends(require_token)])
async def set_ids(request: Request, payload: SetIdsPayload):
    """Met à jour les IDs (channels et role)"""

    partial = {}

    if payload.guild_id is not None:
        partial["guild_id"] = payload.guild_id
    if payload.staff_chan_id is not None:
        partial["channel_staff_id"] = payload.staff_chan_id
    if payload.notif_chan_id is not None:
        partial["channel_public_id"] = payload.notif_chan_id
    if payload.logs_chan_id is not None:
        partial["channel_logs_id"] = payload.logs_chan_id
    if payload.role_id is not None:
        partial["role_id"] = payload.role_id

    if not partial:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Au moins un champ doit être fourni.",
        )

    log.info("[Notations] set_ids partial: %s", partial)

    updated = await nm.update_partial(partial)
    return updated


@app.post("/notations/set_time", dependencies=[Depends(require_token)])
async def set_specific_time(request: Request, payload: SetTimePayload):
    """Met à jour un timing spécifique"""

    if payload.key not in _VALID_TIME_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Clé de temps **invalide**. Valeurs acceptées : {_VALID_TIME_KEYS}",
        )

    mapping = TIME_KEY_MAPPING.get(payload.key)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mapping introuvable pour {payload.key}",
        )

    partial = {
        mapping["weekday"]: payload.schedule.weekday,
        mapping["hour"]: payload.schedule.hour,
        mapping["minute"]: payload.schedule.minute,
    }

    log.info("[Notations] set_time key=%s → partial=%s", payload.key, partial)

    updated = await nm.update_partial(partial)
    return updated