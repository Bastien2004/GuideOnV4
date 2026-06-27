"""
cogs/api/api_staff.py — API Staff pour V4
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from starlette import status
from typing import List

from utils.managers import staff_manager as sm
from cogs.api.base import app, require_token

import logging

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# 📋 MODÈLES PYDANTIC
# ══════════════════════════════════════════════════════════════════════════

class Blame(BaseModel):
    motif: str
    explication: str
    auteur: str


class StaffMember(BaseModel):
    discord_id: int
    pseudo_jeu: str
    grade: str
    skin_head_emoji: str = ""
    blames: List[Blame] = []


class StaffConfigUpdate(BaseModel):
    update_interval_minutes: int
    guild_id: int | str
    channel_id: int | str
    message_id: int | str
    grades_order: List[str]
    staff: List[StaffMember]

    @field_validator('guild_id', 'channel_id', 'message_id', mode='before')
    @classmethod
    def convert_ids_to_int(cls, v):
        """Convertir les IDs string en int"""
        if isinstance(v, str):
            try:
                return int(v)
            except (ValueError, TypeError):
                return v
        return v


class SetConfigPayload(BaseModel):
    channel_id: int | str | None = None
    guild_id: int | str | None = None
    update_interval_minutes: int | None = None

    @field_validator('channel_id', 'guild_id', mode='before')
    @classmethod
    def convert_ids_to_int(cls, v):
        """Convertir les IDs string en int"""
        if isinstance(v, str):
            try:
                return int(v)
            except (ValueError, TypeError):
                return v
        return v


# ══════════════════════════════════════════════════════════════════════════
# 🔄 ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════

@app.get("/staff", dependencies=[Depends(require_token)])
async def get_staff_config(request: Request):
    """Récupère toute la configuration et la liste du staff."""
    config = await sm.get_config()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune configuration staff en base."
        )
    return config


@app.post("/staff/update_config", dependencies=[Depends(require_token)])
async def update_full_staff_config(request: Request, config: StaffConfigUpdate):
    """Met à jour l'intégralité de la configuration."""
    updated = await sm.update_full_config(config.dict())
    return updated


@app.post("/staff/update_partial", dependencies=[Depends(require_token)])
async def update_staff_partial(request: Request, payload: SetConfigPayload):
    """Met à jour uniquement les champs fournis."""
    partial = {k: v for k, v in payload.dict().items() if v is not None}
    if not partial:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Au moins un champ doit être fourni."
        )
    updated = await sm.update_partial(partial)
    return updated


@app.post("/staff/member/add", dependencies=[Depends(require_token)])
async def add_staff_member(request: Request, member: StaffMember):
    """Ajoute ou met à jour un membre du staff."""
    config = await sm.get_config()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune configuration staff — initialisez d'abord."
        )

    # Supprimer l'ancienne entrée si elle existe
    staff_list = config.get("staff", [])
    staff_list = [m for m in staff_list if m.get("discord_id") != member.discord_id]
    staff_list.append(member.dict())

    updated = await sm.update_partial({"staff": staff_list})
    return {"message": f"Membre {member.pseudo_jeu} ajouté/mis à jour.", "member": member}


@app.delete("/staff/member/remove/{discord_id}", dependencies=[Depends(require_token)])
async def remove_staff_member(request: Request, discord_id: int):
    """Supprime un membre du staff."""
    config = await sm.get_config()
    if config is None:
        raise HTTPException(status_code=404, detail="Configuration staff introuvable.")

    staff_list = config.get("staff", [])
    original_count = len(staff_list)
    staff_list = [m for m in staff_list if m.get("discord_id") != discord_id]

    if len(staff_list) == original_count:
        raise HTTPException(status_code=404, detail="Membre non trouvé.")

    await sm.update_partial({"staff": staff_list})
    return {"message": "Membre supprimé avec succès."}


@app.post("/staff/member/{discord_id}/blame/add", dependencies=[Depends(require_token)])
async def add_member_blame(request: Request, discord_id: int, blame: Blame):
    """Ajoute un blâme à un membre."""
    config = await sm.get_config()
    if config is None:
        raise HTTPException(status_code=404, detail="Configuration staff introuvable.")

    staff_list = config.get("staff", [])
    member = next((m for m in staff_list if m.get("discord_id") == discord_id), None)
    if not member:
        raise HTTPException(status_code=404, detail="Membre non trouvé.")

    if "blames" not in member:
        member["blames"] = []
    member["blames"].append(blame.dict())

    await sm.update_partial({"staff": staff_list})
    return {"message": "Blâme ajouté.", "blames": member["blames"]}


@app.delete("/staff/member/{discord_id}/blame/remove/{index}", dependencies=[Depends(require_token)])
async def remove_member_blame(request: Request, discord_id: int, index: int):
    """Supprime un blâme d'un membre."""
    config = await sm.get_config()
    if config is None:
        raise HTTPException(status_code=404, detail="Configuration staff introuvable.")

    staff_list = config.get("staff", [])
    member = next((m for m in staff_list if m.get("discord_id") == discord_id), None)
    if not member:
        raise HTTPException(status_code=404, detail="Membre non trouvé.")

    blames = member.get("blames", [])
    if index < 0 or index >= len(blames):
        raise HTTPException(status_code=404, detail="Blâme non trouvé.")

    removed = blames.pop(index)
    await sm.update_partial({"staff": staff_list})
    return {"message": "Blâme supprimé.", "removed": removed}