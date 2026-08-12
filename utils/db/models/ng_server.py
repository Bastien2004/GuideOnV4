"""
utils/db/models/ng_server.py — Table maitre des serveurs NationsGlory.

Alimentee par le site (interface web). Le bot ne fait que la LIRE :
aucune ecriture bot ne doit cibler cette table en dehors de /dev setng
et /dev unsetng (mode simulation, DB dev uniquement — voir utils.perm_check
et la commande dev associee, phase 5 de la refonte multi-serveurs).
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class NGServer(Base, TimestampMixin):
    """Un serveur Minecraft NationsGlory et son Discord associe (relation 1:1)."""

    __tablename__ = "ng_servers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    edition: Mapped[str] = mapped_column(String(16), nullable=False)
    discord_guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    def __repr__(self) -> str:
        return (
            f"<NGServer id={self.id} name={self.name!r} "
            f"guild_id={self.discord_guild_id} active={self.active}>"
        )