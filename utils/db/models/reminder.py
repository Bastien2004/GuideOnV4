"""
utils/db/models/reminder.py — Modèle du système de rappel personnel (/rappel).

V1 (Paul, 2026-10-12) : rappels personnels ponctuels uniquement (pas de
récurrence pour l'instant — même logique incrémentale que /eco : on pose
la base de la base, la récurrence pourra être ajoutée plus tard).

Contrairement à /eco (solde isolé PAR serveur), un rappel est une donnée
PERSONNELLE de l'utilisateur, pas du serveur : un membre crée un rappel
depuis un serveur, mais /rappel liste et /rappel annuler ne filtrent PAS
par guild_id — un membre voit/annule tous ses rappels, peu importe sur
quel serveur ils ont été créés. `guild_id` est conservé uniquement comme
métadonnée (contexte de création), jamais comme filtre d'accès.

`channel_id` est TOUJOURS renseigné, même quand `destination` est MP :
c'est le salon de secours utilisé par le scheduler si le DM échoue
(membre ayant fermé ses DMs) — cf. cogs/events/reminder_scheduler.py.

Un seul statut implicite : une ligne existe = le rappel est en attente.
Il n'y a pas de colonne "sent"/"done" — le scheduler supprime la ligne
après l'avoir traité (succès ou échec), cf. reminder_manager.delete_reminder.
Pas d'historique conservé en V1 (contrairement à EcoTransactionLog) : rien
dans la demande de Paul n'appelle à un futur "/rappel historique", on
pourra ajouter une table d'archive plus tard si besoin.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class ReminderDestination(str, enum.Enum):
    """Où envoyer le rappel au déclenchement, choisi par le membre à la création."""

    MP = "mp"
    SALON = "salon"


class Reminder(Base, TimestampMixin):
    """Un rappel personnel ponctuel en attente de déclenchement."""

    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Propriétaire du rappel — PAS de filtre par guild_id (cf. docstring module).
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Contexte de création, conservé en métadonnée (jamais utilisé comme
    # filtre d'accès pour liste/annuler).
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Salon d'origine. Toujours renseigné (y compris destination=MP) :
    # sert de secours si le DM échoue au déclenchement.
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    destination: Mapped[ReminderDestination] = mapped_column(
        Enum(ReminderDestination, name="reminder_destination", native_enum=False, length=8),
        nullable=False,
        default=ReminderDestination.MP,
        server_default=ReminderDestination.MP.value,
    )

    message: Mapped[str] = mapped_column(Text, nullable=False)

    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # Interrogée en continu par le scheduler (WHERE due_at <= now).
        Index("ix_reminders_due_at", "due_at"),
        # /rappel liste et /rappel annuler : tous les rappels d'un membre.
        Index("ix_reminders_user", "user_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "destination": self.destination.value,
            "message": self.message,
            "due_at": self.due_at,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"<Reminder id={self.id} user_id={self.user_id} "
            f"destination={self.destination.value} due_at={self.due_at}>"
        )
