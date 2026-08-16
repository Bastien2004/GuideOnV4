"""
utils/db/models/mod_automod_general.py — Paramètres généraux d'auto-modération, par serveur.

Une seule ligne par guild. Regroupe les réglages transverses à tous les
sous-systèmes d'automod (ban word, no link, anti spam, etc.) :
  - alert_channel_id : salon où le staff reçoit un log détaillé à chaque infraction
  - notify_in_channel : si True, un message court est envoyé dans le salon
    d'origine pour prévenir le membre que son message a été supprimé

Aucune escalade automatique : le staff décide manuellement de toute sanction
en consultant l'historique via /mod historique. Il n'y a donc PAS de champ
threshold / mute_duration / window ici.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class ModAutomodGeneral(Base, TimestampMixin):
    """Réglages généraux d'auto-modération, par serveur."""

    __tablename__ = "mod_automod_general"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    alert_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    notify_in_channel: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true",
    )

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "alert_channel_id": self.alert_channel_id,
            "notify_in_channel": self.notify_in_channel,
        }