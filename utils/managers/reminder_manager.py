"""
utils/managers/reminder_manager.py — Système de rappel personnel (/rappel).

V1 : rappels ponctuels uniquement (pas de récurrence). Quota par membre
(MAX_PENDING_PER_USER) pour éviter qu'un membre n'empile des milliers de
rappels — même logique défensive que les autres systèmes (ex: quotas
implicites de blacklist/limites /giveaway).

Pas de verrou asyncio ici (contrairement à eco_manager) : il n'y a pas de
mutation lecture-modification-écriture concurrente à protéger (chaque
rappel est une ligne indépendante, créée/lue/supprimée par id — pas de
solde partagé à additionner).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import delete, select

from utils.db.models.reminder import Reminder, ReminderDestination
from utils.db.session import get_session

MAX_PENDING_PER_USER = 25


class ReminderError(Exception):
    """Erreur métier /rappel destinée à être affichée telle quelle à l'utilisateur."""


class ReminderLimitError(ReminderError):
    """Le membre a déjà atteint MAX_PENDING_PER_USER rappels en attente."""

    def __init__(self, limit: int = MAX_PENDING_PER_USER) -> None:
        self.limit = limit
        super().__init__(f"Limite de {limit} rappels en attente atteinte.")


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

    async with get_session() as session:
        existing_ids = (
            await session.execute(select(Reminder.id).where(Reminder.user_id == user_id))
        ).all()
        if len(existing_ids) >= MAX_PENDING_PER_USER:
            raise ReminderLimitError()

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
