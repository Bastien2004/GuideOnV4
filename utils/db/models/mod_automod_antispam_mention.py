"""
utils/db/models/mod_automod_antispam_mention.py — Système Anti Spam Mention.

Détecte les messages contenant un nombre excessif de mentions. Compte
toutes les mentions confondues : @users, @roles, @everyone, @here — un
seul seuil global pour rester simple. Si un besoin plus fin apparaît
plus tard (distinguer @everyone), ajouter une colonne dédiée.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class ModAutomodAntispamMentionConfig(Base, TimestampMixin):
    """Configuration Anti Spam Mention par serveur."""

    __tablename__ = "mod_automod_antispam_mention_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    max_mentions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5",
    )

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "enabled": self.enabled,
            "max_mentions": self.max_mentions,
        }