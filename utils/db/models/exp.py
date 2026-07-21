"""
utils/db/models/exp.py — Modeles du systeme d'experience (EXP).

Remplace l'ancien stockage JSON V3 (config_exp_<guild>.json + exp_data_<guild>.json).

Deux tables :

- ExpConfig : 1 ligne par serveur (PK = guild_id). Config du systeme :
  active/desactive, gain par message, gain par minute de vocal, role
  boost et pourcentage de bonus. Equivalent de invite_configs.

- ExpUser : 1 ligne par (serveur, membre). Total d'EXP cumule du membre.
  Le niveau n'est jamais stocke : il est recalcule a la volee depuis
  total_exp via utils.managers.exp_manager (evite toute incoherence
  entre l'EXP stockee et le niveau affiche si la formule evolue).

Tous les IDs Discord (snowflakes) sont en BigInteger.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin

# Valeurs par defaut de la config (reprises de la V3).
DEFAULT_EXP_PER_MESSAGE = 10
DEFAULT_EXP_PER_VOICE_MINUTE = 2


class ExpConfig(Base, TimestampMixin):
    """Configuration du systeme d'experience pour un serveur."""

    __tablename__ = "exp_configs"

    # guild_id en PK : une seule config par serveur.
    guild_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )

    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    exp_per_message: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_EXP_PER_MESSAGE, nullable=False
    )
    exp_per_voice_minute: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_EXP_PER_VOICE_MINUTE, nullable=False
    )

    # Role donnant un bonus de gain d'EXP en pourcentage.
    boost_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    boost_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def to_dict(self) -> dict:
        """Representation dict de la config (cles stables pour la view/manager)."""
        return {
            "enabled": self.enabled,
            "exp_per_message": self.exp_per_message,
            "exp_per_voice_minute": self.exp_per_voice_minute,
            "boost_role_id": self.boost_role_id,
            "boost_percent": self.boost_percent,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"<ExpConfig guild_id={self.guild_id} enabled={self.enabled} "
            f"per_message={self.exp_per_message} per_voice_min={self.exp_per_voice_minute} "
            f"boost_role_id={self.boost_role_id} boost_percent={self.boost_percent}>"
        )


class ExpUser(Base, TimestampMixin):
    """EXP cumulee d'un membre sur un serveur."""

    __tablename__ = "exp_users"

    # PK composite (guild_id, user_id) : une ligne par membre et par serveur.
    guild_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )

    total_exp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        # Classement : tri des membres d'un serveur par EXP.
        Index("ix_exp_users_guild", "guild_id"),
    )

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "user_id": self.user_id,
            "total_exp": self.total_exp,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"<ExpUser guild_id={self.guild_id} user_id={self.user_id} "
            f"total_exp={self.total_exp}>"
        )
