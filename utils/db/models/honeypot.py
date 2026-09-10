"""
utils/db/models/honeypot.py — Config du système HoneyPot / "Piège" (/mod piege).

Une seule ligne par serveur (guild_id en PK, comme ModAutomodGeneral) :
  - channel_id         : le salon-piège créé par le bot (None tant qu'il
                          n'a pas été créé via /mod piege)
  - enabled            : détection active ou en pause — indépendant de
                          channel_id pour permettre de suspendre la
                          détection SANS supprimer/recréer le salon
  - ignored_role_ids   : rôles exemptés (un membre qui en possède un ne
                          déclenche jamais le piège)
  - ignored_member_ids : membres exemptés individuellement, en plus des rôles

Contrairement à RaidProtect (dont s'inspire ce système, cf. Paul 2026-09),
aucune sanction/durée configurable : la réaction est FIXE — kick immédiat
+ purge des messages du membre dans le salon-piège + entrée dans
/mod historique (réutilise utils.managers.mod_sanction_manager.kick, qui
alimente déjà /mod historique sans plomberie supplémentaire) — décision
explicite de Paul pour rester simple.
"""
from __future__ import annotations

from sqlalchemy import JSON, BigInteger, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class HoneypotConfig(Base, TimestampMixin):
    """Config du salon-piège HoneyPot, par serveur."""

    __tablename__ = "honeypot_configs"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    ignored_role_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    ignored_member_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "enabled": self.enabled,
            "ignored_role_ids": list(self.ignored_role_ids or []),
            "ignored_member_ids": list(self.ignored_member_ids or []),
        }
