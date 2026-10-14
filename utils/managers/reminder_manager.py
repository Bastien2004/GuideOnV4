"""
utils/managers/reminder_manager.py — Système de rappel personnel (/rappel).

V1 : rappels ponctuels uniquement (pas de récurrence). Quota par membre
pour éviter qu'un membre n'empile des milliers de rappels — même logique
défensive que les autres systèmes (ex: quotas implicites de
blacklist/limites /giveaway).

Paliers VIP (Paul, 2026-10-14) : le nombre de rappels simultanés ET la
durée maximale programmable dépendent du statut VIP du membre (même
source que partout ailleurs dans le bot : utils.managers.boutique_manager
.is_vip_id — lecture sync pure cache, cf. utils/boutique/vip_manager.py
pour l'équivalent orienté-Discord utilisé par les autres commandes) :

    - VIP     : jusqu'à MAX_PENDING_VIP rappels en attente, durée jusqu'à
                MAX_DURATION_VIP_SECONDS (≈ 2 mois).
    - Non-VIP : jusqu'à MAX_PENDING_DEFAULT rappels en attente, durée
                jusqu'à MAX_DURATION_DEFAULT_SECONDS (1 semaine).

Les DEUX limites sont vérifiées ICI, dans create_reminder() — pas
seulement côté interface (views/rappel/creer_view.py) — pour que le quota
reste garanti même si un futur appelant (nouvelle commande, script admin,
etc.) oublie de revalider côté UI. L'interface fait sa propre vérification
en amont uniquement pour afficher une erreur immédiate sans aller-retour
serveur inutile ; la source de vérité reste ce module.

Pas de verrou asyncio ici (contrairement à eco_manager) : il n'y a pas de
mutation lecture-modification-écriture concurrente à protéger (chaque
rappel est une ligne indépendante, créée/lue/supprimée par id — pas de
solde partagé à additionner).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import delete, select

from utils.datetime_utils import now_utc
from utils.db.models.reminder import Reminder, ReminderDestination
from utils.db.session import get_session
from utils.managers.boutique_manager import is_vip_id

# Nombre de rappels en attente autorisés simultanément.
MAX_PENDING_DEFAULT = 3
MAX_PENDING_VIP = 10

# Durée maximale programmable pour un rappel (secondes depuis la création).
MAX_DURATION_DEFAULT_SECONDS = 7 * 86_400       # 1 semaine
MAX_DURATION_VIP_SECONDS = 60 * 86_400          # ≈ 2 mois


def is_vip_user(user_id: int) -> bool:
    """Statut VIP du membre — point d'entrée unique pour ce module."""
    return is_vip_id(user_id)


def max_pending_for(user_id: int) -> int:
    """Quota de rappels simultanés applicable à ce membre."""
    return MAX_PENDING_VIP if is_vip_user(user_id) else MAX_PENDING_DEFAULT


def max_duration_seconds_for(user_id: int) -> int:
    """Durée maximale (en secondes) programmable par ce membre."""
    return MAX_DURATION_VIP_SECONDS if is_vip_user(user_id) else MAX_DURATION_DEFAULT_SECONDS


class ReminderError(Exception):
    """Erreur métier /rappel destinée à être affichée telle quelle à l'utilisateur."""


class ReminderLimitError(ReminderError):
    """Le membre a déjà atteint son quota de rappels en attente (VIP ou non)."""

    def __init__(self, limit: int = MAX_PENDING_DEFAULT) -> None:
        self.limit = limit
        super().__init__(f"Limite de {limit} rappels en attente atteinte.")


class ReminderDurationError(ReminderError):
    """La durée demandée dépasse le plafond autorisé pour ce membre (VIP ou non)."""

    def __init__(self, max_seconds: int) -> None:
        self.max_seconds = max_seconds
        super().__init__(f"Durée maximale autorisée : {max_seconds}s.")


class ReminderNotFoundError(ReminderError):
    """Rappel introuvable, ou n'appartenant pas à l'appelant (cf. cancel_reminder)."""


# ============================================================
# ➕ Création
# ============================================================

async def create_reminder(
    *,
    user_id: int,
    guild_id: int,
    channel_id: int,
    destination: ReminderDestination | str,
    message: str,
    due_at: datetime,
) -> dict:
    """Crée un rappel ponctuel. Lève ReminderLimitError si le quota est atteint.

    `destination` accepte aussi bien un ReminderDestination qu'une chaîne
    brute ("mp"/"salon", ex: la value d'un app_commands.Choice) — convertie
    ici plutôt que de faire porter cette responsabilité à chaque appelant.
    """
    if not isinstance(destination, ReminderDestination):
        destination = ReminderDestination(destination)

    # Durée demandée vs plafond du membre (VIP ou non) — vérifié avant la
    # requête DB du quota pour fail-fast sur l'erreur la moins coûteuse.
    max_duration = max_duration_seconds_for(user_id)
    requested_seconds = (due_at - now_utc()).total_seconds()
    if requested_seconds > max_duration:
        raise ReminderDurationError(max_duration)

    async with get_session() as session:
        existing_ids = (
            await session.execute(select(Reminder.id).where(Reminder.user_id == user_id))
        ).all()
        limit = max_pending_for(user_id)
        if len(existing_ids) >= limit:
            raise ReminderLimitError(limit)

        row = Reminder(
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            destination=destination,
            message=message,
            due_at=due_at,
        )
        session.add(row)
        await session.flush()
        return row.to_dict()


# ============================================================
# 📋 Lecture
# ============================================================

async def get_reminders_for_user(user_id: int) -> list[dict]:
    """Tous les rappels en attente d'un membre, triés par échéance croissante.

    PAS de filtre par guild_id (cf. docstring de utils.db.models.reminder) :
    un membre voit tous ses rappels, peu importe le serveur de création.
    """
    async with get_session() as session:
        rows = (
            await session.execute(
                select(Reminder)
                .where(Reminder.user_id == user_id)
                .order_by(Reminder.due_at.asc())
            )
        ).scalars().all()
        return [r.to_dict() for r in rows]


async def count_pending_for_user(user_id: int) -> int:
    async with get_session() as session:
        rows = (
            await session.execute(select(Reminder.id).where(Reminder.user_id == user_id))
        ).all()
        return len(rows)


async def get_reminder(reminder_id: int) -> Optional[dict]:
    async with get_session() as session:
        row = await session.get(Reminder, reminder_id)
        return row.to_dict() if row is not None else None


async def get_due_reminders(now: datetime) -> list[dict]:
    """Rappels dont l'échéance est passée — interrogé par le scheduler."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(Reminder).where(Reminder.due_at <= now)
            )
        ).scalars().all()
        return [r.to_dict() for r in rows]


# ============================================================
# ❌ Suppression
# ============================================================

async def cancel_reminder(reminder_id: int, user_id: int) -> dict:
    """Annule (supprime) un rappel — vérifie que l'appelant en est le propriétaire.

    Lève ReminderNotFoundError si le rappel n'existe pas ou appartient à
    un autre membre (même message dans les deux cas : on ne révèle pas
    l'existence d'un rappel appartenant à quelqu'un d'autre).
    """
    async with get_session() as session:
        row = await session.get(Reminder, reminder_id)
        if row is None or row.user_id != user_id:
            raise ReminderNotFoundError(f"Rappel #{reminder_id} introuvable.")
        data = row.to_dict()
        await session.delete(row)
        return data


async def delete_reminder(reminder_id: int) -> bool:
    """Supprime un rappel par id, sans vérification de propriétaire —
    utilisé par le scheduler après traitement (succès ou échec d'envoi)."""
    async with get_session() as session:
        res = await session.execute(delete(Reminder).where(Reminder.id == reminder_id))
        return res.rowcount > 0
