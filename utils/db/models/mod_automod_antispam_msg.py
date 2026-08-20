"""
utils/db/models/mod_automod_antispam_msg.py — Système Anti Spam Message.

Détecte le spam par répétition de message identique, y compris à travers
plusieurs salons (le copier-coller d'un même message dans plusieurs salons
est le vecteur de spam le plus courant — d'où le comptage "tous salons
confondus" plutôt que par salon). Deux paramètres :
  - window_seconds : fenêtre glissante d'observation, en secondes
  - max_messages   : nombre de messages identiques (dans la fenêtre) à
                     partir duquel l'infraction est déclenchée

Le comptage réel (buffer en mémoire par utilisateur) vit dans
utils.automod.antispam_msg_buffer — ce fichier ne contient QUE le schéma.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class ModAutomodAntispamMsgConfig(Base, TimestampMixin):
    """Configuration Anti Spam Message par serveur."""

    __tablename__ = "mod_automod_antispam_msg_config"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    window_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, server_default="10",
    )

    max_messages: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3",
    )

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "enabled": self.enabled,
            "window_seconds": self.window_seconds,
            "max_messages": self.max_messages,
        }