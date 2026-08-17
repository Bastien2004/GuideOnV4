"""
utils/db/models/mod_automod_general.py — Paramètres généraux d'auto-modération.

Une seule ligne par guild. Regroupe les réglages transverses à tous les
sous-systèmes d'automod (ban word, no link, anti spam, etc.).

Champs :
  - alert_channel_id            : salon où le staff reçoit les alertes détaillées
  - staff_role_id               : rôle ping dans les alertes de mute auto
  - notify_in_channel           : si True, un message container est envoyé dans le
                                  salon d'origine pour prévenir le membre
  - notification_window_seconds : fenêtre temporelle (en secondes) pendant laquelle
                                  une SECONDE infraction du même système déclenche
                                  un mute Discord natif (bornée 10s → 180s côté UI)
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class ModAutomodGeneral(Base, TimestampMixin):
    """Réglages généraux d'auto-modération, par serveur."""

    __tablename__ = "mod_automod_general"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    alert_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    staff_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    notify_in_channel: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true",
    )

    notification_window_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, server_default="60",
    )

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "alert_channel_id": self.alert_channel_id,
            "staff_role_id": self.staff_role_id,
            "notify_in_channel": self.notify_in_channel,
            "notification_window_seconds": self.notification_window_seconds,
        }