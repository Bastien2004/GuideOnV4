"""
utils/db/models/alpha_staff.py — Modèle des membres du staff Alpha.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


GRADES_ORDER: list[str] = [
    "administrateur",
    "super_moderateur",
    "moderateur_plus",
    "moderateur_confirme",
    "moderateur_test",
    "guide",
    "journaliste",
]

GRADE_LABELS: dict[str, str] = {
    "administrateur":      "Administrateur",
    "super_moderateur":    "Super Modérateur",
    "moderateur_plus":     "Modérateur+",
    "moderateur_confirme": "Modérateur Confirmé",
    "moderateur_test":     "Modérateur (Test)",
    "guide":               "Guide",
    "journaliste":         "Journaliste",
}

GRADE_EMOJIS: dict[str, str] = {
    "administrateur":      "<:Administrateur:1493513024919568514>",
    "super_moderateur":    "<:SuperModerateur:1493513047778791446>",
    "moderateur_plus":     "<:Moderateur:1493513069039714335>",
    "moderateur_confirme": "<:Moderateur:1493513069039714335>",
    "moderateur_test":     "<:Moderateur:1493513069039714335>",
    "guide":               "<:Guide:1493513088610209822>",
    "journaliste":         "📰",
}

GRADE_PREFIXES: dict[str, str] = {
    "administrateur":      "Admin",
    "super_moderateur":    "SM",
    "moderateur_plus":     "Modo+",
    "moderateur_confirme": "Modo",
    "moderateur_test":     "Modo",
    "guide":               "Guide",
    "journaliste":         "Journaliste",
}

GRADE_TO_ROLE_ATTR: dict[str, str] = {
    "administrateur":      "role_administrateur_id",
    "super_moderateur":    "role_super_moderateur_id",
    "moderateur_plus":     "role_moderateur_plus_id",
    "moderateur_confirme": "role_moderateur_confirme_id",
    "moderateur_test":     "role_moderateur_test_id",
    "guide":               "role_guide_id",
    "journaliste":         "role_journaliste_id",
}

# Grades incompatibles avec le statut journaliste (trop élevés dans la hiérarchie)
JOURNALISTE_INCOMPATIBLE_GRADES: set[str] = {"super_moderateur", "administrateur"}


class AlphaStaffMember(Base, TimestampMixin):
    """Un membre du staff Alpha. Clé unique : discord_id."""

    __tablename__ = "alpha_staff"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    pseudo_jeu: Mapped[str] = mapped_column(String(64), nullable=False)
    grade: Mapped[str] = mapped_column(String(32), nullable=False)
    skin_head_emoji: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    # Statut journaliste cumulable (indépendant du grade de modération)
    # True si le membre a aussi le rôle Journaliste (impossible pour SM/Admin)
    is_journaliste: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    __table_args__ = (
        Index("ix_alpha_staff_grade", "grade"),
    )

    def to_dict(self) -> dict:
        return {
            "discord_id":      self.discord_id,
            "pseudo_jeu":      self.pseudo_jeu,
            "grade":           self.grade,
            "skin_head_emoji": self.skin_head_emoji,
            "is_journaliste":  self.is_journaliste,
        }

    def __repr__(self) -> str:
        return (
            f"<AlphaStaffMember id={self.id} pseudo={self.pseudo_jeu!r} "
            f"grade={self.grade!r} journaliste={self.is_journaliste}>"
        )