"""
utils/db/models/mod_sanction.py — Sanctions de modération (warn/mute/kick/ban/
tempban/softban) et config associée.

Une seule table `Sanction` pour tous les types : c'est le "casier judiciaire"
d'un membre (historique 100% consultatif, aucune escalade automatique — cf.
discussion avec Paul). L'id est un code court (utils.id_sanction.sanction_id,
6 caractères), prévu depuis la V3 mais jamais utilisé jusqu'ici.

`active` distingue une sanction encore "en vigueur" (mute/ban/softban non
expiré et non révoqué) d'une sanction terminée (warn/kick, instantanés,
toujours active=False dès la création ; ou mute/ban/softban expiré/révoqué).
Ce n'est PAS une notion d'escalade, juste "est-ce que l'effet Discord est
toujours actif". SOFTBAN est un ban permanent (avec purge de messages à la
création) : il ne se lève jamais tout seul, uniquement via /mod unban.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin

DEFAULT_SOFTBAN_PURGE_SECONDS = 86_400  # 1 jour


class SanctionType(str, enum.Enum):
    """Type de sanction. Détermine la présence de duration_seconds/expires_at."""

    WARN = "warn"
    MUTE = "mute"
    KICK = "kick"
    BAN = "ban"
    TEMPBAN = "tempban"
    SOFTBAN = "softban"


# Types pouvant être révoqués manuellement (unwarn / unmute / unban).
# SOFTBAN est un ban permanent (avec purge de messages) : révocable comme BAN.
REVOCABLE_TYPES = (SanctionType.WARN, SanctionType.MUTE, SanctionType.BAN, SanctionType.TEMPBAN, SanctionType.SOFTBAN)

# Types instantanés : aucun état Discord persistant, active=False dès la création.
INSTANT_TYPES = (SanctionType.WARN, SanctionType.KICK)


class Sanction(Base, TimestampMixin):
    """Une sanction appliquée à un membre sur un serveur."""

    __tablename__ = "mod_sanctions"

    # Code court (6 caractères), généré par utils.id_sanction.sanction_id().
    id: Mapped[str] = mapped_column(String(6), primary_key=True, autoincrement=False)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    moderator_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    type: Mapped[SanctionType] = mapped_column(
        Enum(SanctionType, name="mod_sanction_type", native_enum=False, length=16),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Uniquement pour mute/tempban.
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # True tant que l'effet Discord est en vigueur (mute/ban non expiré/révoqué).
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # A-t-on réussi à notifier le membre en MP ? (best-effort, jamais bloquant)
    dm_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_mod_sanctions_guild_user", "guild_id", "user_id"),
        Index("ix_mod_sanctions_guild_active", "guild_id", "active"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "user_id": self.user_id,
            "moderator_id": self.moderator_id,
            "type": self.type.value,
            "reason": self.reason,
            "duration_seconds": self.duration_seconds,
            "expires_at": self.expires_at,
            "active": self.active,
            "revoked_at": self.revoked_at,
            "revoked_by": self.revoked_by,
            "revoked_reason": self.revoked_reason,
            "dm_sent": self.dm_sent,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"<Sanction id={self.id} type={self.type.value} guild_id={self.guild_id} "
            f"user_id={self.user_id} active={self.active}>"
        )


class ModSanctionConfig(Base, TimestampMixin):
    """Réglages généraux du système de sanctions, par serveur."""

    __tablename__ = "mod_sanction_configs"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    # Durée de purge des messages lors d'un softban (0 à 604800s = 7 jours,
    # borne dure de l'API Discord pour delete_message_seconds).
    softban_purge_seconds: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_SOFTBAN_PURGE_SECONDS, nullable=False
    )

    def to_dict(self) -> dict:
        return {"softban_purge_seconds": self.softban_purge_seconds}

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<ModSanctionConfig guild_id={self.guild_id} softban_purge_seconds={self.softban_purge_seconds}>"