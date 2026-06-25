"""
utils/db/models/autorole.py — Configuration du système d'auto-rôle par serveur.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from cogs.api.base import Base, TimestampMixin


class AutoRoleConfig(Base, TimestampMixin):
    __tablename__ = "autorole_configs"

    guild_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False
    )

    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    role_id_1: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_id_2: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_id_3: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    def to_dict(self) -> dict:
        """Retourne le squelette de configuration auto-rôle. """

        return {
            "auto_role_active": self.active,
            "role_id_1": self.role_id_1,
            "role_id_2": self.role_id_2,
            "role_id_3": self.role_id_3,
        }

    def role_ids(self) -> list[int]:
        """Liste des IDs de rôles configurés."""

        return [r for r in (self.role_id_1, self.role_id_2, self.role_id_3) if r]

    def __repr__(self) -> str:
        return (
            f"<AutoRoleConfig guild_id={self.guild_id} active={self.active} "
            f"roles={self.role_ids()}>"
        )