"""
utils/db/models/alpha.py — Modèles du système Alpha.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class AlphaMessageConfig(Base, TimestampMixin):
    """
    Stocke le message_id d'un message persistant Alpha (index, nous_rejoindre…).

    clé : (guild_id, key) — `key` identifie le type de message (ex: 'index', 'nous_rejoindre').
    Permet de retrouver le message pour l'éditer plutôt que d'en créer un nouveau.
    """

    __tablename__ = "alpha_message_configs"

    # PK composite : un seul message par type par serveur
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Salon cible et message Discord
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AlphaMessageConfig guild={self.guild_id} key={self.key!r} "
            f"channel={self.channel_id} message={self.message_id}>"
        )