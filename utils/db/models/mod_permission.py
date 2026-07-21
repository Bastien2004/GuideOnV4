"""
utils/db/models/mod_permission.py — Permissions granulaires du systeme /mod.

Une ligne = (guild_id, permission_key, role_id) : le role Discord `role_id`
est autorise a utiliser la commande/le panneau identifie par `permission_key`
sur le serveur `guild_id`. Plusieurs roles peuvent etre assignes a une meme
cle (meme principe que TicketPanelStaffRole).

Deny-by-default : tant qu'aucune ligne n'existe pour une (guild_id, key)
donnee, seul un Administrateur Discord peut utiliser la commande/le panneau
correspondant (verifie cote utils.perm_mod, pas ici).
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class ModPermissionRole(Base, TimestampMixin):
    """Role Discord autorise a utiliser une cle de permission /mod donnee."""

    __tablename__ = "mod_permission_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    permission_key: Mapped[str] = mapped_column(String(64), nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("guild_id", "permission_key", "role_id", name="uq_mod_permission_role"),
        Index("ix_mod_permission_guild_key", "guild_id", "permission_key"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"<ModPermissionRole guild_id={self.guild_id} "
            f"key={self.permission_key!r} role_id={self.role_id}>"
        )
