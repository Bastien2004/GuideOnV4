"""
utils/db/models/ng_onu_config.py — Modèles du système ONU multi-serveurs.

NGONUConfig     : configuration principale (une ligne par serveur NG, PK=server)
NGONUPingMember : membres à ping en MP avant l'ONU (unique par server+discord_id)

Refonte multi-serveurs phase 8 : remplace AlphaONUConfig/AlphaONUPingMember
(clés guild_id) par un modèle clé par `NGServer.name` (server), cohérent avec
NGStaffMember/NGRankConfig (phases 6-7). `server` référence `ng_servers.name`
(pas de ForeignKey stricte pour rester cohérent avec NGStaffMember/NGRankConfig,
la résolution se fait applicativement via ng_server_manager).
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin

JOURS_LABELS = [
    "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"
]


class NGONUConfig(Base, TimestampMixin):
    """
    Configuration du système ONU, une ligne par serveur NG.

    Champs identiques à AlphaONUConfig (voir utils/db/models/alpha_onu_config.py),
    seule la clé change : `server` (nom NGServer) au lieu de `guild_id`.
    """

    __tablename__ = "ng_onu_configs"

    server: Mapped[str] = mapped_column(String(50), primary_key=True)

    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    jour_onu: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-6

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
            "server":     self.server,
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
        return f"<NGONUConfig server={self.server!r} enabled={self.enabled}>"


class NGONUPingMember(Base, TimestampMixin):
    """Membres à ping en MP avant chaque ONU, par serveur."""

    __tablename__ = "ng_onu_ping_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    server: Mapped[str] = mapped_column(String(50), nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("server", "discord_id", name="uq_ng_onu_ping_member"),
        Index("ix_ng_onu_ping_server", "server"),
    )

    def __repr__(self) -> str:
        return f"<NGONUPingMember server={self.server!r} user={self.discord_id}>"
