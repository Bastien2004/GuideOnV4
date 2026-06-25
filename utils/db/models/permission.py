"""
utils/db/models/permission.py — Modèle des permissions..
"""
from __future__ import annotations

import enum

from sqlalchemy import Enum, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from cogs.api.base import Base, TimestampMixin


class PermissionRole(str, enum.Enum):
    """Rôles internes."""

    DEV = "DEV"
    STAFF_GUIDEON = "STAFF_GUIDEON"
    OP_ALPHA = "OP_ALPHA"
    MODO_PLUS_ALPHA = "MODO_PLUS_ALPHA"
    MODO_ALPHA = "MODO_ALPHA"


class PermissionEntry(Base, TimestampMixin):
    """
    Une entrée = (role, discord_id).
    """

    __tablename__ = "permission_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    role: Mapped[PermissionRole] = mapped_column(
        Enum(PermissionRole, name="permission_role", native_enum=False, length=32),
        nullable=False,
        index=True,
    )

    discord_id: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint("role", "discord_id", name="uq_permission_role_discord_id"),
        Index("ix_permission_role_discord", "role", "discord_id"),
    )

    def __repr__(self) -> str:
        return f"<PermissionEntry role={self.role.value!r} discord_id={self.discord_id!r}>"