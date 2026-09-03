"""
utils/db/models/medialink_log.py — MEDIALINK : journal technique
(media_logs), pour l'écran "Historique / Logs" du dashboard (§16).

Distinct de media_events : un événement (media_events) = une vidéo/live/post
détecté et traité ; un log (media_logs) = une ligne de diagnostic sur le
fonctionnement du système lui-même (échec de connexion, rate-limit
plateforme, erreur d'envoi Discord...) — utile même quand il n'y a PAS
d'événement (ex: échec de vérification d'une connexion, §6.3).

Table volontairement append-only : pas de TimestampMixin (qui apporte
updated_at, inutile ici), seulement created_at.
"""
from __future__ import annotations

import enum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base


class MediaLogLevel(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class MediaLog(Base):
    """Une ligne de journal technique, rattachée ou non à une connexion."""

    __tablename__ = "media_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    # Nullable : certains logs sont globaux au module (ex: erreur du
    # scheduler) et ne concernent pas une connexion précise.
    connection_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_connections.id", ondelete="CASCADE"), nullable=True,
    )

    level: Mapped[str] = mapped_column(
        String(16), default=MediaLogLevel.INFO.value,
        server_default=MediaLogLevel.INFO.value, nullable=False,
    )

    # Ex: "connection.check_failed", "event.send_failed",
    # "provider.rate_limited"... même logique ouverte que
    # MediaRule.event_type (pas d'ENUM DB, contrat côté code).
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)

    message: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    __table_args__ = (
        Index("ix_medialink_log_guild_created", "guild_id", "created_at"),
        Index("ix_medialink_log_connection", "connection_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "connection_id": self.connection_id,
            "level": self.level,
            "event_type": self.event_type,
            "message": self.message,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<MediaLog id={self.id} level={self.level!r} event_type={self.event_type!r}>"
