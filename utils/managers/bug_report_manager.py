"""
utils/managers/bug_report_manager.py — Gestion des rapports de bug (/report).

Remplace utils/report_storage.py (stockage JSON) :
- DRAFTS : restent en MÉMOIRE (transitoires, expiration 30 min). On garde la
  classe ReportDraft et les helpers get_draft/clear_draft.
- REPORTS finalisés : persistés en DB (table bug_reports). create_report insère
  et renvoie le modèle ; la référence "RPT-0001" est dérivée de l'id auto.

Pas de cache (les reports ne sont pas relus en boucle). Lecture/écriture directe.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from utils.db.models.bug_report import BugReport
from utils.db.session import get_session

log = logging.getLogger(__name__)

DRAFT_EXPIRATION_MINUTES = 30


# ============================================================
# 🧩 DRAFT (mémoire)
# ============================================================

class ReportDraft:
    """Rapport en cours de rédaction (vit en mémoire, non persisté)."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.title: Optional[str] = None
        self.description: Optional[str] = None
        self.importance: Optional[str] = None
        self.attachment_url: Optional[str] = None
        self.created_at: datetime = datetime.now(timezone.utc)

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) - self.created_at > timedelta(
            minutes=DRAFT_EXPIRATION_MINUTES
        )

    def is_complete(self) -> bool:
        return all([self.title, self.description, self.importance])

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "importance": self.importance,
            "attachment_url": self.attachment_url,
            "created_at": self.created_at.isoformat(),
        }


_drafts: dict[int, ReportDraft] = {}


def get_draft(user_id: int) -> ReportDraft:
    """Renvoie un draft valide ; le recrée si absent ou expiré."""
    draft = _drafts.get(user_id)
    if draft is None or draft.is_expired():
        draft = ReportDraft(user_id)
        _drafts[user_id] = draft
    return draft


def clear_draft(user_id: int) -> None:
    """Supprime le draft d'un utilisateur."""
    _drafts.pop(user_id, None)


# ============================================================
# 💾 REPORTS (DB)
# ============================================================

async def create_report(
    *,
    user_id: int,
    user_tag: str,
    guild_id: Optional[int],
    title: str,
    description: str,
    importance: str,
    attachment_url: Optional[str] = None,
) -> BugReport:
    """Insère un rapport finalisé. Renvoie le modèle (avec .reference)."""
    async with get_session() as session:
        report = BugReport(
            user_id=user_id,
            user_tag=user_tag,
            guild_id=guild_id,
            title=title,
            description=description,
            importance=importance,
            attachment_url=attachment_url,
        )
        session.add(report)
        await session.flush()
        # Capture les valeurs avant fermeture de session (expire_on_commit).
        result = report.to_dict()
    log.info("Report créé : %s par %s (%s)", result["reference"], user_tag, user_id)
    return result


async def create_report_from_draft(
    draft: ReportDraft, user_id: int, user_tag: str, guild_id: Optional[int]
) -> dict:
    """Crée un report depuis un draft. Lève ValueError si draft invalide/incomplet."""
    if not isinstance(draft, ReportDraft):
        raise ValueError("Draft invalide : type incorrect")
    if not draft.is_complete():
        raise ValueError("Draft incomplet : champs obligatoires manquants")
    return await create_report(
        user_id=user_id,
        user_tag=user_tag,
        guild_id=guild_id,
        title=draft.title,
        description=draft.description,
        importance=draft.importance,
        attachment_url=draft.attachment_url,
    )


async def get_report(report_id: int) -> Optional[dict]:
    """Récupère un report par son id numérique."""
    async with get_session() as session:
        report = await session.get(BugReport, report_id)
        return report.to_dict() if report else None


async def list_reports(guild_id: Optional[int] = None, limit: int = 25) -> list[dict]:
    """Liste les reports (les plus récents d'abord), filtrables par serveur."""
    async with get_session() as session:
        stmt = select(BugReport).order_by(BugReport.id.desc()).limit(limit)
        if guild_id is not None:
            stmt = stmt.where(BugReport.guild_id == guild_id)
        rows = (await session.execute(stmt)).scalars().all()
    return [r.to_dict() for r in rows]