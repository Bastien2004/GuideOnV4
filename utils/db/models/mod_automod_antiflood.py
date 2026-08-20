"""
utils/db/models/mod_automod_antiflood.py — Système Anti Flood.

Détecte le "mashkeyboard" (texte tapé au hasard sur le clavier, ex:
"kjshdfkjqshdfkjh") via le ratio de voyelles parmi les lettres du message —
un texte écrit dans une vraie langue a toujours une proportion significative
de voyelles, contrairement à une suite aléatoire de touches. Deux
paramètres :
  - min_length      : nombre minimum de LETTRES (hors chiffres/ponctuation/
                       espaces/emojis) pour que le message soit analysé
                       (protège les messages courts, trop peu fiables
                       statistiquement)
  - min_vowel_ratio : proportion minimale de voyelles parmi les lettres,
                       en-dessous de laquelle le message est considéré
                       comme du flood (0.0 → 1.0)
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class ModAutomodAntifloodConfig(Base, TimestampMixin):
    """Configuration Anti Flood par serveur."""

    __tablename__ = "mod_automod_antiflood_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    min_length: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20, server_default="20",
    )

    min_vowel_ratio: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.2, server_default="0.2",
    )

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "enabled": self.enabled,
            "min_length": self.min_length,
            "min_vowel_ratio": self.min_vowel_ratio,
        }