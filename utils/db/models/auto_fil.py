"""
utils/db/models/auto_fil.py — Configuration du système "Auto-fil"
(/config auto_fil, Paul, 2026-10-15).

Crée automatiquement un fil (thread) sous chaque message posté dans un
salon configuré. Même patron que Join to Create
(utils/db/models/join_to_create.py) : plusieurs lignes par serveur, une
par salon configuré — PAS un salon unique en PK, pour permettre le palier
Gold+ (jusqu'à 3 salons, cf. utils/managers/auto_fil_manager.py).

Contrairement à Join to Create, le salon est choisi parmi les salons
EXISTANTS (pas créé par le bot) : pas besoin de conserver son nom en
cache, il est résolu en direct via guild.get_channel() pour l'affichage
(même logique que views/invite/config_view.py::_channel_label — "Salon
supprimé" si introuvable).
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class AutoFilConfig(Base, TimestampMixin):
    """Un salon sur lequel le système auto-fil est actif."""

    __tablename__ = "auto_fil_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        # Un même salon ne peut être configuré qu'une seule fois.
        UniqueConstraint("channel_id", name="uq_auto_fil_channel_id"),
        # Liste des salons d'un serveur (panneau de config, listener on_message).
        Index("ix_auto_fil_guild", "guild_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<AutoFilConfig id={self.id} guild_id={self.guild_id} channel_id={self.channel_id}>"
