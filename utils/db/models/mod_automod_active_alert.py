"""
utils/db/models/mod_automod_active_alert.py — Alertes automod en cours (mute auto).

Une ligne créée à chaque déclenchement d'un mute automatique (=récidive dans
la fenêtre). Persistée en DB pour :
  - garder trace même après restart du bot (view "Je m'en occupe" persistante)
  - historique des interventions staff (qui a pris quoi et quand)
  - futur panel côté site (statistiques d'intervention)

Cycle de vie :
  1. Récidive détectée → INSERT (taken_by_user_id = NULL, taken_at = NULL)
     + mute Discord natif appliqué + message staff avec bouton "Je m'en occupe"
  2. Clic staff sur "Je m'en occupe" → UPDATE (taken_by_user_id + taken_at)
     + mute levé + message actualisé
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base


class ModAutomodActiveAlert(Base):
    """Une alerte automod avec mute auto en cours ou traitée."""

    __tablename__ = "mod_automod_active_alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    system_key: Mapped[str] = mapped_column(String(32), nullable=False)

    # Le message d'alerte staff (celui qui contient le bouton "Je m'en occupe").
    alert_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    alert_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Contexte du message qui a déclenché l'alerte.
    matched_term: Mapped[str | None] = mapped_column(String(200), nullable=True)
    message_excerpt: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    # Renseignés au clic sur "Je m'en occupe" (None tant que pending).
    taken_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_automod_alert_message", "alert_message_id"),
        Index("ix_automod_alert_guild_user", "guild_id", "user_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "system_key": self.system_key,
            "alert_channel_id": self.alert_channel_id,
            "alert_message_id": self.alert_message_id,
            "matched_term": self.matched_term,
            "message_excerpt": self.message_excerpt,
            "created_at": self.created_at,
            "taken_by_user_id": self.taken_by_user_id,
            "taken_at": self.taken_at,
        }

    @property
    def is_taken(self) -> bool:
        return self.taken_by_user_id is not None