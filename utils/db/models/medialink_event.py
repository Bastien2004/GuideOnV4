"""
utils/db/models/medialink_event.py — MEDIALINK : journal des événements
détectés (table media_events).

Distinct de utils/medialink/event.py::MediaEvent (l'objet métier en
mémoire que les Providers produisent et que l'Event Manager fait
circuler dans le pipeline, §4/§8). Cette table-ci est la PERSISTANCE de cet
objet, une fois traité — elle sert à la fois :
  - à l'anti-doublon (§9.1) : la contrainte unique (connection_id,
    external_event_id) EST l'implémentation de la clé
    "platform + connection_id + external_event_id" — inutile de répéter
    platform ici puisqu'une connexion a une plateforme fixe.
  - au replay (§9.4) : le statut suit PENDING → PROCESSING → SENT
    (ou FAILED / SKIPPED).
  - à l'historique consultable (§10, §16 "Historique").
"""
from __future__ import annotations

import enum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db.base import Base, TimestampMixin


class MediaEventStatus(str, enum.Enum):
    """Cf. §9.4 "Replay" : PENDING → PROCESSING → SENT, ou FAILED / SKIPPED."""

    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class MediaEventRecord(Base, TimestampMixin):
    """Une ligne = un événement détecté par un Provider, normalisé, et son
    résultat de traitement."""

    __tablename__ = "media_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    connection_id: Mapped[int] = mapped_column(
        ForeignKey("media_connections.id", ondelete="CASCADE"), nullable=False,
    )

    # Identifiant fourni par la plateforme (ex: id de vidéo YouTube) — voir
    # docstring de module pour le rôle de external_event_id dans l'anti-doublon.
    external_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)

    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(
        String(16), default=MediaEventStatus.PENDING.value,
        server_default=MediaEventStatus.PENDING.value, nullable=False,
    )
    # Rempli quand le pipeline a fini de traiter l'événement (succès ou échec
    # définitif) — distinct de created_at (moment de détection).
    processed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Message d'erreur le plus récent si status == FAILED (§9.3 Retry) —
    # ajout hors tableau §13.1, nécessaire pour que l'historique (§16) soit
    # réellement "consultable" en cas d'échec.
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    connection: Mapped["MediaConnection"] = relationship()  # noqa: F821

    __table_args__ = (
        # L'anti-doublon (§9.1) EST cette contrainte : un même événement
        # externe ne peut être enregistré qu'une fois par connexion.
        UniqueConstraint("connection_id", "external_event_id", name="uq_medialink_event_connection_external"),
        Index("ix_medialink_event_connection", "connection_id"),
        Index("ix_medialink_event_status", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "connection_id": self.connection_id,
            "external_event_id": self.external_event_id,
            "event_type": self.event_type,
            "title": self.title,
            "url": self.url,
            "thumbnail": self.thumbnail,
            "author": self.author,
            "published_at": self.published_at,
            "status": self.status,
            "processed_at": self.processed_at,
            "last_error": self.last_error,
            "attempts": self.attempts,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"<MediaEventRecord id={self.id} connection_id={self.connection_id} "
            f"event_type={self.event_type!r} status={self.status!r}>"
        )
