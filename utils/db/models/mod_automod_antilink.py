"""
utils/db/models/mod_automod_antilink.py — Système Anti Link.

Deux tables, même schéma que le ban word / no link :
  - mod_automod_antilink_config     : une ligne par guild, indique si le
    système est activé
  - mod_automod_antilink_extensions : la liste des extensions de fichier
    bloquées (relation N-1 vers guild via guild_id, pas de FK vers config —
    permet d'ajouter des extensions avant activation)

La logique de détection (scan liens + pièces jointes) vit dans
utils.automod.detectors.antilink — ce fichier ne contient QUE le schéma.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class ModAutomodAntilinkConfig(Base, TimestampMixin):
    """Activation du système Anti Link, par serveur."""

    __tablename__ = "mod_automod_antilink_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    def to_dict(self) -> dict:
        return {"guild_id": self.guild_id, "enabled": self.enabled}


class ModAutomodAntilinkExtension(Base, TimestampMixin):
    """Une extension de fichier bloquée (unique par (guild_id, extension))."""

    __tablename__ = "mod_automod_antilink_extensions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    extension: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        UniqueConstraint("guild_id", "extension", name="uq_antilink_guild_extension"),
        Index("ix_antilink_guild", "guild_id"),
    )

    def to_dict(self) -> dict:
        return {"id": self.id, "guild_id": self.guild_id, "extension": self.extension}