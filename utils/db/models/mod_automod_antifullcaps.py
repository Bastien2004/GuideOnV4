"""
utils/db/models/mod_automod_antifullcaps.py — Système Anti Full Maj.

Détecte les messages écrits (majoritairement) en majuscules — un mode
d'expression agressif qui perturbe la lecture. Deux paramètres :
  - min_length     : longueur minimale d'un message pour être analysé
                     (protège les acronymes courts type "OK", "LOL")
  - ratio_threshold: proportion minimale de lettres MAJUSCULES à partir
                     de laquelle le message est refusé (0.0 → 1.0)

Le ratio est calculé sur les seules LETTRES du message (les chiffres,
espaces, ponctuation, emojis sont ignorés) pour éviter les faux positifs
avec des chiffres/symboles.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class ModAutomodAntifullcapsConfig(Base, TimestampMixin):
    """Configuration Anti Full Maj par serveur."""

    __tablename__ = "mod_automod_antifullcaps_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    min_length: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, server_default="10",
    )

    ratio_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.7, server_default="0.7",
    )

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "enabled": self.enabled,
            "min_length": self.min_length,
            "ratio_threshold": self.ratio_threshold,
        }