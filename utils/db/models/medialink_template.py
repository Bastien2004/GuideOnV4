"""
utils/db/models/medialink_template.py — Gestion des modèles d'annonces.

    {
        "accent_color": int | None,   # couleur de la barre du Container
        "title": str | None,          # rendu "# {title}" (TextDisplay)
        "description": str | None,    # texte sous le titre
        "thumbnail_enabled": bool,    # afficher event.thumbnail ("vignette")
    }
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class MediaTemplate(Base, TimestampMixin):
    """Un modèle d'annonce réutilisable par une ou plusieurs règles."""

    __tablename__ = "media_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    container_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    buttons: Mapped[list | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_medialink_template_guild", "guild_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "name": self.name,
            "content": self.content,
            "container_config": self.container_config,
            "buttons": self.buttons,
        }

    def __repr__(self) -> str:
        return f"<MediaTemplate id={self.id} guild_id={self.guild_id} name={self.name!r}>"