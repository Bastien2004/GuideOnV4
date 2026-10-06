"""
utils/managers/qr_manager.py — Accès DB pour l'historique des QR codes.

2026-10-06 (Paul) : `guild_id` est conservé en écriture (save_qr) et pour
/qr scan (find_qr_by_content — on ne veut PAS attribuer un QR scanné à
quelqu'un d'un autre serveur, ça reste une fuite d'identité cross-serveur).
En revanche, à la demande de Paul, l'historique personnel d'un membre
(/qr list, et donc list_qr_by_user/count_qr_by_user/delete_qr) n'est PLUS
cloisonné par serveur : un membre doit retrouver TOUS ses QR codes, générés
sur n'importe quel serveur où tourne GuideOn, pas seulement celui courant.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import delete, func, select

from utils.db.models.qr_code import QRCode
from utils.db.session import get_session

log = logging.getLogger(__name__)


# ============================================================
# 💾 Écriture
# ============================================================

async def save_qr(user_id: int, guild_id: int, contenu: str) -> QRCode:
    """Enregistre un nouveau QR code généré par un utilisateur.

    `guild_id` reste enregistré (utile pour /qr scan, voir plus bas) même
    si l'historique personnel (list_qr_by_user) ne filtre plus dessus.

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


async def delete_qr(entry_id: int, *, user_id: int) -> bool:
    """Supprime UNE entrée d'historique, seulement si elle appartient bien à
    `user_id` (vérifié en SQL, pas juste côté appelant) — évite qu'un id
    arbitraire permette de supprimer l'entrée d'un autre utilisateur. Pas de
    filtre serveur : l'historique est désormais global, un membre peut
    supprimer n'importe laquelle de ses propres entrées. Renvoie True si une
    ligne a bien été supprimée."""

    async with get_session() as session:
        result = await session.execute(
            delete(QRCode).where(QRCode.id == entry_id, QRCode.user_id == user_id)
        )
        return result.rowcount > 0


# ============================================================
# 📖 Lecture
# ============================================================

async def list_qr_by_user(user_id: int, limit: int = 100) -> Sequence[QRCode]:
    """Renvoie TOUS les derniers QR codes générés par un utilisateur, tous
    serveurs confondus (plus récents en premier). `limit` est volontairement
    généreux (100) — la pagination côté view (views/qr/list_view.py) se
    charge de l'affichage page par page, pas cette requête."""

    async with get_session() as session:
        result = await session.execute(
            select(QRCode)
            .where(QRCode.user_id == user_id)
            .order_by(QRCode.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


async def count_qr_by_user(user_id: int) -> int:
    """Nombre total de QR codes actuellement dans l'historique d'un
    utilisateur (tous serveurs confondus) — utilisé pour la limite de
    génération (voir cogs/qr/generate.py : 3 par défaut, 10 pour les VIP)."""

    async with get_session() as session:
        result = await session.execute(
            select(func.count()).select_from(QRCode).where(QRCode.user_id == user_id)
        )
        return result.scalar_one()


async def find_qr_by_content(contenu: str, guild_id: int) -> Optional[QRCode]:
    """Retrouve l'entrée correspondant à un contenu de QR scanné SUR CE
    SERVEUR (le plus récent match) — jamais un match généré sur un autre
    serveur (seule requête qui reste cloisonnée : révéler l'auteur d'un QR
    identique généré ailleurs serait une fuite d'identité cross-serveur,
    indépendante de la question de l'historique personnel)."""

    async with get_session() as session:
        result = await session.execute(
            select(QRCode)
            .where(QRCode.contenu == contenu, QRCode.guild_id == guild_id)
            .order_by(QRCode.created_at.desc())
        )
        return result.scalars().first()
