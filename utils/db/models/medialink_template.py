"""
utils/db/models/medialink_template.py — MEDIALINK : modèles d'annonce
(Announcement Template, 4e concept de §13 "Platform → Connection →
Event Configuration → Announcement Template").

Un template définit COMMENT un événement est mis en forme dans Discord
(texte libre + configuration d'embed + boutons), avec des placeholders
(§7 : "{titre}", "{auteur}", "{url}"...) résolus par
utils/medialink/builders/placeholders.py au moment de l'envoi — jamais
stockés résolus ici.

NOTE (choix technique) : embed_config et buttons sont stockés en JSON
(type générique SQLAlchemy `JSON`, portable Postgres/SQLite). C'est la
PREMIÈRE colonne JSON de la base GuideOn — jusqu'ici toute config
structurée passait par des tables dédiées (cf. mod_automod_banword,
ticket...). Ici la forme d'un embed (champs, couleur, thumbnail on/off...)
est ouverte et amenée à évoluer avec les Announcement Builders (§7) sans
migration à chaque champ ajouté — c'est un choix à valider avec Paul,
pas une simple copie d'un pattern déjà en place dans le code.
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

    # Texte libre au-dessus/à la place de l'embed, avec placeholders non
    # résolus (ex: "🎬 Nouvelle vidéo de {auteur} !"). Cf. §7 "Rappel : ne
    # jamais afficher une valeur nulle — si un placeholder n'est pas
    # disponible pour l'événement, il doit être filtré, pas affiché vide."
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Configuration de l'embed (titre, description, couleur, thumbnail,
    # champs, footer...) — structure ouverte, cf. note de module.
    embed_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Boutons additionnels (ex: "Voir la vidéo") — liste de {label, url,
    # style, emoji}, également en JSON pour la même raison.
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
            "embed_config": self.embed_config,
            "buttons": self.buttons,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<MediaTemplate id={self.id} guild_id={self.guild_id} name={self.name!r}>"
