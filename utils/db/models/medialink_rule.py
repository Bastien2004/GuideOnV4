"""
utils/db/models/medialink_rule.py — MEDIALINK : règles de diffusion.

Table media_rules du cahier des charges — c'est le 3e des 4 concepts de
§13 "Platform → Connection → Event Configuration → Announcement Template".
Une règle relie : une connexion, UN type d'événement, un salon Discord, un
template, un rôle à mentionner (optionnel), un état actif/inactif — cf.
l'exemple §3 :

    YouTube / GuideON
      Nouvelle vidéo → #youtube
      Nouveau Short  → #shorts
      Début de live  → #live

"Une même connexion peut posséder plusieurs règles indépendantes" — c'est
préférable à une config unique par compte : ça permet de router chaque
événement vers le salon et le template appropriés (§3).
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db.base import Base, TimestampMixin


class MediaRule(Base, TimestampMixin):
    """Une règle : SI cet event_type arrive sur cette connexion, ALORS
    publier dans ce salon avec ce template (et mentionner ce rôle)."""

    __tablename__ = "media_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    connection_id: Mapped[int] = mapped_column(
        ForeignKey("media_connections.id", ondelete="CASCADE"), nullable=False,
    )

    # Ex: "youtube.video_published", "youtube.short_published",
    # "youtube.live_started", "twitch.stream_started"... La liste canonique
    # par plateforme est définie côté Provider (contrat Phase 0, P0.2) — on
    # ne la fige pas ici en ENUM DB pour ne pas bloquer l'ajout d'un type
    # d'événement sur une migration.
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)

    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_templates.id", ondelete="SET NULL"), nullable=True,
    )

    # NOTE (ajout hors tableau §13.1) : la maquette §3 montre explicitement
    # "Mention : @Nouveautés" comme réglage d'une règle — champ nécessaire,
    # absent du tableau du cahier des charges mais présent dans l'exemple.
    mention_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    connection: Mapped["MediaConnection"] = relationship(back_populates="rules")  # noqa: F821

    __table_args__ = (
        Index("ix_medialink_rule_connection", "connection_id"),
        Index("ix_medialink_rule_connection_event", "connection_id", "event_type"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "connection_id": self.connection_id,
            "event_type": self.event_type,
            "channel_id": self.channel_id,
            "template_id": self.template_id,
            "mention_role_id": self.mention_role_id,
            "enabled": self.enabled,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"<MediaRule id={self.id} connection_id={self.connection_id} "
            f"event_type={self.event_type!r} enabled={self.enabled}>"
        )
