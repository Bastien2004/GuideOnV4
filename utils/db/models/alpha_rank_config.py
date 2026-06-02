"""
utils/db/models/alpha_rank_config.py — Configuration du système rank/derank Alpha.

Une seule ligne par serveur (guild_id = PK).
Stocke les IDs Discord de salons, pings et rôles par grade.
"""
from __future__ import annotations

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class AlphaRankConfig(Base, TimestampMixin):
    """
    Configuration du système rank/derank Alpha.

    Salons :
        rank_channel_id       — annonces rank et derank
        journaliste_channel_id — message aux journalistes pour l'affiche
        dev_channel_id         — message aux devs pour l'emoji skin

    Pings (rôles à @mention) :
        journaliste_ping_id   — @rôle journaliste dans le message affiche
        dev_ping_id           — @rôle dev dans le message emoji skin

    Rôles Discord attribués par grade :
        role_journaliste_id, role_guide_id,
        role_moderateur_test_id, role_moderateur_confirme_id,
        role_moderateur_plus_id, role_super_moderateur_id, role_administrateur_id
    """

    __tablename__ = "alpha_rank_configs"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # ── Salons ────────────────────────────────────────────────
    rank_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    journaliste_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    dev_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # ── Pings (rôle à @mention) ───────────────────────────────
    journaliste_ping_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    dev_ping_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # ── Rôles Discord par grade ───────────────────────────────
    role_journaliste_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_guide_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_moderateur_test_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_moderateur_confirme_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_moderateur_plus_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_super_moderateur_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_administrateur_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    def to_dict(self) -> dict:
        return {
            "guild_id":                   self.guild_id,
            "rank_channel_id":            self.rank_channel_id,
            "journaliste_channel_id":     self.journaliste_channel_id,
            "dev_channel_id":             self.dev_channel_id,
            "journaliste_ping_id":        self.journaliste_ping_id,
            "dev_ping_id":                self.dev_ping_id,
            "role_journaliste_id":        self.role_journaliste_id,
            "role_guide_id":              self.role_guide_id,
            "role_moderateur_test_id":    self.role_moderateur_test_id,
            "role_moderateur_confirme_id": self.role_moderateur_confirme_id,
            "role_moderateur_plus_id":    self.role_moderateur_plus_id,
            "role_super_moderateur_id":   self.role_super_moderateur_id,
            "role_administrateur_id":     self.role_administrateur_id,
        }

    def __repr__(self) -> str:
        return f"<AlphaRankConfig guild={self.guild_id}>"