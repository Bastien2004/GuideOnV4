"""
cogs/api/api_notations.py — API Notations
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from starlette import status

from utils.managers import notations_manager as nm

# ✅ Importer l'app partagée
from cogs.api.base import app, limiter, require_token

import logging
log = logging.getLogger(__name__)


_VALID_TIME_KEYS = [
    "time_ask_availability",
    "time_ask_beginning",
    "time_ask_finish",
    "time_send_notations",
]


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
    time_ask_availability: TimeSchedule
    time_ask_beginning: TimeSchedule
    time_ask_finish: TimeSchedule
    time_send_notations: TimeSchedule


class SetIdsPayload(BaseModel):
    guild_id: int | None = None
    staff_chan_id: int | None = None
    notif_chan_id: int | None = None
    logs_chan_id: int | None = None
    role_id: int | None = None


class SetTimePayload(BaseModel):
    key: str
    schedule: TimeSchedule


# Endpoints (gardez ceux-ci)

@app.get("/notations", dependencies=[Depends(require_token)])
@limiter.limit("2/minute")
async def get_notation_config(request: Request):
    return await nm.get_config()


@app.post("/notations/update_all", dependencies=[Depends(require_token)])
@limiter.limit("1/minute")
async def update_full_config(request: Request, config: NotationConfigUpdate):
    updated = await nm.update_full_config(config.dict())
    return updated


@app.post("/notations/set_ids", dependencies=[Depends(require_token)])
@limiter.limit("1/minute")
async def set_ids(request: Request, payload: SetIdsPayload):
    mapping = {
        "id_guild_notations": payload.guild_id,
        "id_channel_staff_notations": payload.staff_chan_id,
        "id_channel_notations": payload.notif_chan_id,
        "id_channel_logs": payload.logs_chan_id,
        "id_role_notation": payload.role_id,
    }
    partial = {k: v for k, v in mapping.items() if v is not None}
    if not partial:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Au moins un champ doit être fourni.",
        )
    updated = await nm.update_partial(partial)
    return updated


@app.post("/notations/set_time", dependencies=[Depends(require_token)])
@limiter.limit("1/minute")
async def set_specific_time(request: Request, payload: SetTimePayload):
    if payload.key not in _VALID_TIME_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Clé de temps **invalide**. Valeurs acceptées : {_VALID_TIME_KEYS}",
        )
    updated = await nm.update_partial({payload.key: payload.schedule.dict()})
    return updated