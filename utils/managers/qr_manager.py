"""
utils/managers/qr_manager.py — Accès DB pour l'historique des QR codes.

2026-10-06 (Paul) : toutes les requêtes sont désormais cloisonnées par
`guild_id` (voir utils/db/models/qr_code.py pour le détail du problème
corrigé) — un utilisateur ne peut plus faire remonter/retrouver un QR code
généré sur un AUTRE serveur que celui où la commande est exécutée.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import delete, select

from utils.db.models.qr_code import QRCode
from utils.db.session import get_session

log = logging.getLogger(__name__)


# ============================================================
# 💾 Écriture
# ============================================================

async def save_qr(user_id: int, guild_id: int, contenu: str) -> QRCode:
    """Enregistre un nouveau QR code généré par un utilisateur sur ce serveur.

    get_session() commit automatiquement en sortie de bloc (succès) et rollback
    sur exception — pas besoin d'appeler session.commit() ici. Le flush() sert
    juste à récupérer l'id et created_at générés par la base avant la fermeture
    de la session (expire_on_commit=False garde les valeurs accessibles ensuite).
    """

    async with get_session() as session:
        qr = QRCode(user_id=user_id, guild_id=guild_id, contenu=contenu)
        session.add(qr)
        await session.flush()

    return qr


async def delete_qr(entry_id: int, *, user_id: int, guild_id: int) -> bool:
    """Supprime UNE entrée d'historique, seulement si elle appartient bien à
    `user_id` sur `guild_id` (double vérification faite en SQL, pas juste côté
    appelant) — évite qu'un id arbitraire permette de supprimer l'entrée d'un
    autre utilisateur. Renvoie True si une ligne a bien été supprimée."""

    async with get_session() as session:
        result = await session.execute(
            delete(QRCode).where(
                QRCode.id == entry_id,
                QRCode.user_id == user_id,
                QRCode.guild_id == guild_id,
            )
        )
        return result.rowcount > 0


# ============================================================
# 📖 Lecture
# ============================================================

async def list_qr_by_user(user_id: int, guild_id: int, limit: int = 100) -> Sequence[QRCode]:
    """Renvoie les derniers QR codes générés par un utilisateur SUR CE SERVEUR
    (plus récents en premier). `limit` est volontairement généreux (100) —
    la pagination côté view (views/qr/list_view.py) se charge de l'affichage
    page par page, pas cette requête."""

    async with get_session() as session:
        result = await session.execute(
            select(QRCode)
            .where(QRCode.user_id == user_id, QRCode.guild_id == guild_id)
            .order_by(QRCode.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


async def find_qr_by_content(contenu: str, guild_id: int) -> Optional[QRCode]:
    """Retrouve l'entrée correspondant à un contenu de QR scanné SUR CE
    SERVEUR (le plus récent match) — jamais un match généré sur un autre
    serveur."""

    async with get_session() as session:
        result = await session.execute(
            select(QRCode)
            .where(QRCode.contenu == contenu, QRCode.guild_id == guild_id)
            .order_by(QRCode.created_at.desc())
        )
        return result.scalars().first()
