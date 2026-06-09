"""
utils/db/models/alpha_onu_config.py — Modèles du système ONU Alpha.

AlphaONUConfig  : configuration principale (une ligne par guild)
AlphaONUPingMember : membres à ping en MP avant l'ONU
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin

JOURS_LABELS = [
    "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"
]


class AlphaONUConfig(Base, TimestampMixin):
    """
    Configuration du système ONU Alpha.

    Champs :
        channel_id          — salon où envoyer les annonces
        role_id             — rôle @mention dans les annonces
        jour_onu            — jour de l'ONU (0=lundi … 6=dimanche)
        pre_heure/minute    — heure de la pré-annonce
        ann_heure/minute    — heure de l'annonce
        timezone            — fuseau horaire (ex: "Europe/Paris")
        ping_mp             — activer le ping MP aux membres de la ping-list
        image_name          — nom du fichier image dans source/ (ex: onu_alpha_1.png)
        join_url            — URL du bouton "Rejoindre la conférence"
        enabled             — désactiver sans perdre la config
    """

    __tablename__ = "alpha_onu_configs"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    jour_onu: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0–6

    pre_heure: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pre_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ann_heure: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ann_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)

    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Europe/Paris", server_default="Europe/Paris"
    )
    ping_mp: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    image_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    join_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    def to_dict(self) -> dict:
        return {
            "guild_id":   self.guild_id,
            "channel_id": self.channel_id,
            "role_id":    self.role_id,
            "jour_onu":   self.jour_onu,
            "pre_heure":  self.pre_heure,
            "pre_minute": self.pre_minute,
            "ann_heure":  self.ann_heure,
            "ann_minute": self.ann_minute,
            "timezone":   self.timezone,
            "ping_mp":    self.ping_mp,
            "image_name": self.image_name,
            "join_url":   self.join_url,
            "enabled":    self.enabled,
        }

    def __repr__(self) -> str:
        return f"<AlphaONUConfig guild={self.guild_id} enabled={self.enabled}>"


class AlphaONUPingMember(Base, TimestampMixin):
    """Membres à ping en MP avant chaque ONU."""

    __tablename__ = "alpha_onu_ping_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("guild_id", "discord_id", name="uq_onu_ping_member"),
        Index("ix_onu_ping_guild", "guild_id"),
    )

    def __repr__(self) -> str:
        return f"<AlphaONUPingMember guild={self.guild_id} user={self.discord_id}>"