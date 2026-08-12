"""
cogs/api/api_staff.py — API Staff.
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from starlette import status

from utils.managers import ng_staff_manager as asm
from cogs.api.base import app, require_token

log = logging.getLogger(__name__)

# Refonte multi-serveurs phase 7 : l'API site n'est pas encore
# multi-serveurs (§11 du prompt : "Extension future : site pourra lire
# ces tables"). En attendant, câblée en dur sur "alpha".
SERVER = "alpha"


# ══════════════════════════════════════════════════════════════════════════
# 📋 MODÈLES PYDANTIC
# ══════════════════════════════════════════════════════════════════════════

class StaffMember(BaseModel):
    discord_id: int
    pseudo_jeu: str
    grade: str
    skin_head_emoji: str = ""
    is_journaliste: bool = False
    is_affilie: bool = False
    is_builder: bool = False
    pseudo_jeu_builder: str | None = None


class UpdateMemberPayload(BaseModel):
    discord_id: int
    pseudo_jeu: str | None = None
    grade: str | None = None
    skin_head_emoji: str | None = None
    is_journaliste: bool | None = None
    is_affilie: bool | None = None
    is_builder: bool | None = None
    pseudo_jeu_builder: str | None = None


class Blame(BaseModel):
    motif: str
    explication: str
    auteur: str


# ══════════════════════════════════════════════════════════════════════════
# 🔄 ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════

@app.get("/staff", dependencies=[Depends(require_token)])
async def get_staff(request: Request):
    """Récupère toute la liste du staff."""
    members = await asm.list_staff(SERVER)
    return {"staff": members}


@app.get("/staff/{discord_id}", dependencies=[Depends(require_token)])
async def get_staff_member(request: Request, discord_id: int):
    """Récupère un membre spécifique."""
    member = await asm.get_staff_member(SERVER, discord_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Membre non trouvé.")
    return member


@app.post("/staff/member/add", dependencies=[Depends(require_token)])
async def add_staff_member(request: Request, member: StaffMember):
    """Ajoute un membre (échoue si déjà présent)."""
    created = await asm.add_staff_member(
        SERVER,
        discord_id=member.discord_id,
        pseudo_jeu=member.pseudo_jeu,
        grade=member.grade,
        skin_head_emoji=member.skin_head_emoji,
        is_journaliste=member.is_journaliste,
        is_affilie=member.is_affilie,
        is_builder=member.is_builder,
        pseudo_jeu_builder=member.pseudo_jeu_builder,
    )
    if not created:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce membre est déjà dans le staff. Utilisez /staff/member/update pour le modifier."
        )
    return {"message": f"Membre {member.pseudo_jeu} ajouté.", "member": member}


@app.post("/staff/member/upsert", dependencies=[Depends(require_token)])
async def upsert_staff_member(request: Request, member: StaffMember):
    """Ajoute ou met à jour un membre."""
    created = await asm.upsert_staff_member(
        SERVER,
        discord_id=member.discord_id,
        pseudo_jeu=member.pseudo_jeu,
        grade=member.grade,
        skin_head_emoji=member.skin_head_emoji,
        is_journaliste=member.is_journaliste,
        is_affilie=member.is_affilie,
        is_builder=member.is_builder,
        pseudo_jeu_builder=member.pseudo_jeu_builder,
    )
    action = "ajouté" if created else "mis à jour"
    return {"message": f"Membre {member.pseudo_jeu} {action}.", "created": created, "member": member}


@app.post("/staff/member/update", dependencies=[Depends(require_token)])
async def update_staff_member(request: Request, payload: UpdateMemberPayload):
    """Met à jour les champs fournis d'un membre."""
    fields = {k: v for k, v in payload.model_dump().items() if k != "discord_id" and v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="Au moins un champ doit être fourni.")

    updated = await asm.update_staff_member(SERVER, payload.discord_id, **fields)
    if not updated:
        raise HTTPException(status_code=404, detail="Membre non trouvé.")
    return {"message": "Membre mis à jour.", "discord_id": payload.discord_id, "fields": fields}


@app.delete("/staff/member/remove/{discord_id}", dependencies=[Depends(require_token)])
async def remove_staff_member(request: Request, discord_id: int):
    """Supprime un membre du staff."""
    deleted = await asm.remove_staff_member(SERVER, discord_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Membre non trouvé.")
    return {"message": "Membre supprimé avec succès.", "discord_id": discord_id}


@app.post("/staff/member/{discord_id}/blame/add", dependencies=[Depends(require_token)])
async def add_blame(request: Request, discord_id: int, blame: Blame):
    """Ajoute un blâme à un membre."""
    member = await asm.get_staff_member(SERVER, discord_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Membre non trouvé.")

    blames = member.get("blames") or []
    blames.append(blame.model_dump())

    updated = await asm.update_staff_member(SERVER, discord_id, blames=blames)
    if not updated:
        raise HTTPException(status_code=500, detail="Mise à jour échouée.")
    return {"message": "Blâme ajouté.", "blames": blames}


@app.delete("/staff/member/{discord_id}/blame/remove/{index}", dependencies=[Depends(require_token)])
async def remove_blame(request: Request, discord_id: int, index: int):
    """Supprime un blâme d'un membre."""
    member = await asm.get_staff_member(SERVER, discord_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Membre non trouvé.")

    blames = member.get("blames") or []
    if index < 0 or index >= len(blames):
        raise HTTPException(status_code=404, detail="Blâme non trouvé.")

    removed = blames.pop(index)
    await asm.update_staff_member(SERVER, discord_id, blames=blames)
    return {"message": "Blâme supprimé.", "removed": removed}