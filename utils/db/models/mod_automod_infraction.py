"""
utils/db/models/mod_automod_infraction.py — Log des infractions d'auto-modération.

Une ligne par déclenchement d'un système d'automod. Table centrale pour :
  - historique d'un membre (consulté par le staff dans /mod historique)
  - statistiques par système et par serveur (futur panel côté site)
  - top mots bloqués (via matched_term)

Volontairement pas de FK vers les utilisateurs Discord (snowflake stocké nu :
un membre peut quitter le serveur sans qu'on perde son historique) ni vers
mod_sanctions (une infraction automod n'est pas une sanction : c'est le staff
qui décide s'il escalade en /mod warn / mute / ban en regardant l'historique).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base


class ModAutomodInfraction(Base):
    """Une infraction déclenchée par un système d'auto-modération."""

    __tablename__ = "mod_automod_infractions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Clé identifiant le sous-système déclencheur : "banword", "nolink",
    # "antilink", "antispam_msg", "antispam_mention", "antiflood",
    # "antifullcaps", "antispam_emoji".
    system_key: Mapped[str] = mapped_column(String(32), nullable=False)

    # Terme précis qui a matché (utile pour banword et anti-link — le mot ou
    # le TLD). None pour les systèmes structurels (anti-fullcaps, anti-flood).
    matched_term: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Petit extrait du message pour donner du contexte au staff. Tronqué à
    # 500 chars pour éviter les payloads massifs sur les copier-coller.
    message_excerpt: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_automod_infr_guild_user", "guild_id", "user_id"),
        Index("ix_automod_infr_guild_system", "guild_id", "system_key"),
        Index("ix_automod_infr_guild_created", "guild_id", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "system_key": self.system_key,
            "matched_term": self.matched_term,
            "message_excerpt": self.message_excerpt,
            "created_at": self.created_at,
        }