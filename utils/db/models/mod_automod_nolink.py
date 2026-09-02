"""
utils/db/models/mod_automod_nolink.py — Système No Link.

Deux tables :
  - mod_automod_nolink_config    : une ligne par guild, indique si le système
    est activé
  - mod_automod_nolink_whitelist : les salons où les liens restent autorisés
    malgré le système actif (relation N-1 vers guild via guild_id, pas de FK
    explicite vers config — comme pour le ban word — pour permettre à un
    admin de whitelister des salons avant d'activer le système)

La logique de détection (regex URLs / invites Discord) vit dans
utils.automod.detectors.nolink — ce fichier ne contient QUE le schéma.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class ModAutomodNolinkConfig(Base, TimestampMixin):
    """Activation du système No Link, par serveur."""

    __tablename__ = "mod_automod_nolink_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    bypass_gif: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    def to_dict(self) -> dict:
        return {"guild_id": self.guild_id, "enabled": self.enabled, "bypass_gif": self.bypass_gif}


class ModAutomodNolinkWhitelist(Base, TimestampMixin):
    """Un salon où les liens sont autorisés (unique par (guild_id, channel_id))."""

    __tablename__ = "mod_automod_nolink_whitelist"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("guild_id", "channel_id", name="uq_nolink_guild_channel"),
        Index("ix_nolink_guild", "guild_id"),
    )

    def to_dict(self) -> dict:
        return {"id": self.id, "guild_id": self.guild_id, "channel_id": self.channel_id}