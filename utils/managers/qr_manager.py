"""
utils/managers/qr_manager.py — Accès DB pour l'historique des QR codes.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import select

from utils.db.models.qr_code import QRCode
from utils.db.session import get_session

log = logging.getLogger(__name__)


# ============================================================
# 💾 Écriture
# ============================================================

async def save_qr(user_id: int, contenu: str) -> QRCode:
    """Enregistre un nouveau QR code généré par un utilisateur.

    get_session() commit automatiquement en sortie de bloc (succès) et rollback
    sur exception — pas besoin d'appeler session.commit() ici. Le flush() sert
    juste à récupérer l'id et created_at générés par la base avant la fermeture
    de la session (expire_on_commit=False garde les valeurs accessibles ensuite).
    """

    async with get_session() as session:
        qr = QRCode(user_id=user_id, contenu=contenu)
        session.add(qr)
        await session.flush()

    return qr


# ============================================================
# 📖 Lecture
# ============================================================

async def list_qr_by_user(user_id: int, limit: int = 20) -> Sequence[QRCode]:
    """Renvoie les derniers QR codes générés par un utilisateur (plus récents en premier)."""

    async with get_session() as session:
        result = await session.execute(
            select(QRCode)
            .where(QRCode.user_id == user_id)
            .order_by(QRCode.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


async def find_qr_by_content(contenu: str) -> Optional[QRCode]:
    """Retrouve l'entrée correspondant à un contenu de QR scanné (le plus récent match)."""

    async with get_session() as session:
        result = await session.execute(
            select(QRCode)
            .where(QRCode.contenu == contenu)
            .order_by(QRCode.created_at.desc())
        )
        return result.scalars().first()