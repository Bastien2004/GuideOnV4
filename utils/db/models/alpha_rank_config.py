"""
utils/db/models/alpha_rank_config.py — Configuration du système rank/derank Alpha.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from cogs.api.base import Base, TimestampMixin


class AlphaRankConfig(Base, TimestampMixin):
    """Configuration du système rank/derank Alpha."""

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
    role_affilie_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_builder_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    role_equipe_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # ── Contenu Discord (messages permanents) ─────────────────
    content_nous_rejoindre_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_nous_rejoindre_ping_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_nous_rejoindre_emoji: Mapped[str | None] = mapped_column(String(100), nullable=True)

    content_index_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_index_emoji: Mapped[str | None] = mapped_column(String(100), nullable=True)

    content_regle_interne_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_regle_interne_emoji: Mapped[str | None] = mapped_column(String(100), nullable=True)

    content_stafflist_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # ── Emoji annonce (réaction sur les messages rank/derank) ─
    rank_emoji: Mapped[str | None] = mapped_column(String(100), nullable=True)

    def to_dict(self) -> dict:
        return {
            "guild_id":                    self.guild_id,
            "rank_channel_id":             self.rank_channel_id,
            "journaliste_channel_id":      self.journaliste_channel_id,
            "dev_channel_id":              self.dev_channel_id,
            "journaliste_ping_id":         self.journaliste_ping_id,
            "dev_ping_id":                 self.dev_ping_id,
            "role_journaliste_id":         self.role_journaliste_id,
            "role_guide_id":               self.role_guide_id,
            "role_moderateur_test_id":     self.role_moderateur_test_id,
            "role_moderateur_confirme_id": self.role_moderateur_confirme_id,
            "role_moderateur_plus_id":     self.role_moderateur_plus_id,
            "role_super_moderateur_id":    self.role_super_moderateur_id,
            "role_administrateur_id":      self.role_administrateur_id,
            "role_affilie_id":             self.role_affilie_id,
            "role_builder_id":             self.role_builder_id,
            "role_equipe_id":              self.role_equipe_id,
            # Contenu
            "content_nous_rejoindre_channel_id": self.content_nous_rejoindre_channel_id,
            "content_nous_rejoindre_ping_id":    self.content_nous_rejoindre_ping_id,
            "content_nous_rejoindre_emoji":      self.content_nous_rejoindre_emoji,
            "content_index_channel_id":          self.content_index_channel_id,
            "content_index_emoji":               self.content_index_emoji,
            "content_regle_interne_channel_id":  self.content_regle_interne_channel_id,
            "content_regle_interne_emoji":       self.content_regle_interne_emoji,
            "content_stafflist_channel_id":      self.content_stafflist_channel_id,
            "rank_emoji":                           self.rank_emoji,
        }

    def __repr__(self) -> str:
        return f"<AlphaRankConfig guild={self.guild_id}>"