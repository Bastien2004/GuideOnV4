"""
utils/db/models/medialink_connection.py — MEDIALINK : comptes/chaînes connectés.

Une ligne = un compte suivi sur une plateforme, pour un serveur (guild_id).
Une même plateforme peut avoir plusieurs connexions (ex: 2 chaînes YouTube
suivies sur le même serveur) — cf. cahier des charges §3 "Objectifs
fonctionnels" : "Associer plusieurs comptes/chaînes à une même plateforme."

Ne contient AUCUNE logique spécifique à une plateforme (§8.1 "Le Core ne
doit pas contenir de logique spécifique à YouTube, Twitch, TikTok ou
Reddit") : juste l'état d'une connexion, peu importe qui la fournit.
"""
from __future__ import annotations

import enum

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db.base import Base, TimestampMixin


class MediaPlatform(str, enum.Enum):
    """Plateformes prévues par le cahier des charges (§2). Volontairement une
    simple liste de valeurs (pas de contrainte DB stricte de type ENUM) pour
    ne pas avoir à écrire une migration à chaque nouvelle plateforme — cf.
    §3 "Préparer l'architecture à l'ajout futur d'autres plateformes"."""

    YOUTUBE = "youtube"
    TWITCH = "twitch"
    TIKTOK = "tiktok"
    REDDIT = "reddit"


class ConnectionStatus(str, enum.Enum):
    """Cf. §6.3 "États d'une connexion"."""

    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    ERROR = "error"
    DISABLED = "disabled"


class MediaConnection(Base, TimestampMixin):
    """Un compte/chaîne suivi sur une plateforme, pour un serveur."""

    __tablename__ = "media_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    platform: Mapped[str] = mapped_column(String(16), nullable=False)

    # Identifiants côté plateforme — external_id est stable (utilisé pour la
    # clé anti-doublon avec media_events.external_event_id, cf. §9.1),
    # external_username/avatar/url sont ré-affichables mais peuvent changer.
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    external_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(16), default=ConnectionStatus.OPERATIONAL.value,
        server_default=ConnectionStatus.OPERATIONAL.value, nullable=False,
    )

    # NOTE (ajout hors tableau §13.1) : le dashboard (§6.2) affiche "Dernier
    # check" et "Dernier event" — nécessite ces deux horodatages, absents du
    # tableau du cahier des charges mais indispensables à l'écran décrit.
    last_checked_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rules: Mapped[list["MediaRule"]] = relationship(  # noqa: F821
        back_populates="connection", cascade="all, delete-orphan",
        passive_deletes=True, lazy="selectin",
    )

    __table_args__ = (
        # Une même plateforme+compte n'est connectée qu'une fois par serveur.
        UniqueConstraint("guild_id", "platform", "external_id", name="uq_medialink_conn_guild_platform_external"),
        Index("ix_medialink_conn_guild_platform", "guild_id", "platform"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "platform": self.platform,
            "external_id": self.external_id,
            "external_username": self.external_username,
            "external_url": self.external_url,
            "avatar_url": self.avatar_url,
            "status": self.status,
            "last_checked_at": self.last_checked_at,
            "last_event_at": self.last_event_at,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"<MediaConnection id={self.id} platform={self.platform!r} "
            f"external_id={self.external_id!r} status={self.status!r}>"
        )
