"""
utils/db/models/mod_automod_antispam_emoji.py — Système Anti Spam Emoji.

Détecte les messages contenant trop d'emojis. Compte les emojis Unicode
+ les emojis custom Discord (<:name:id> et <a:name:id>) additionnés.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class ModAutomodAntispamEmojiConfig(Base, TimestampMixin):
    """Configuration Anti Spam Emoji par serveur."""

    __tablename__ = "mod_automod_antispam_emoji_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    max_emoji: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, server_default="10",
    )

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "enabled": self.enabled,
            "max_emoji": self.max_emoji,
        }