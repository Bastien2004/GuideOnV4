"""
utils/db/models/mod_automod_banword.py — Système ban word.

Deux tables :
  - mod_automod_banword_config : une ligne par guild, indique si le système
    est activé
  - mod_automod_banword_words : la liste des mots bannis (relation N-1 vers
    guild via guild_id, pas de FK explicite vers config pour permettre à un
    admin d'ajouter des mots avant d'activer le système)

La logique de matching (normalisation NFD, leetspeak, compression) vit dans
utils.automod.detectors.banword — ce fichier ne contient QUE le schéma.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class ModAutomodBanwordConfig(Base, TimestampMixin):
    """Activation du système ban word, par serveur."""

    __tablename__ = "mod_automod_banword_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    def to_dict(self) -> dict:
        return {"guild_id": self.guild_id, "enabled": self.enabled}


class ModAutomodBanwordWord(Base, TimestampMixin):
    """Un mot banni sur un serveur (unique par (guild_id, word))."""

    __tablename__ = "mod_automod_banword_words"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    word: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("guild_id", "word", name="uq_banword_guild_word"),
        Index("ix_banword_guild", "guild_id"),
    )

    def to_dict(self) -> dict:
        return {"id": self.id, "guild_id": self.guild_id, "word": self.word}