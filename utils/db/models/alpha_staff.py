"""
utils/db/models/alpha_staff.py — Modèle des membres du staff Alpha.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


GRADES_ORDER: list[str] = [
    "administrateur",
    "super_moderateur",
    "moderateur_plus",
    "moderateur_confirme",
    "moderateur_test",
    "guide",
]

GRADE_LABELS: dict[str, str] = {
    "administrateur":      "Administrateur",
    "super_moderateur":    "Super Modérateur",
    "moderateur_plus":     "Modérateur+",
    "moderateur_confirme": "Modérateur Confirmé",
    "moderateur_test":     "Modérateur (Test)",
    "guide":               "Guide",
}

GRADE_EMOJIS: dict[str, str] = {
    "administrateur":      "<:Administrateur:1493513024919568514>",
    "super_moderateur":    "<:SuperModerateur:1493513047778791446>",
    "moderateur_plus":     "<:Moderateur:1493513069039714335>",
    "moderateur_confirme": "<:Moderateur:1493513069039714335>",
    "moderateur_test":     "<:Moderateur:1493513069039714335>",
    "guide":               "<:Guide:1493513088610209822>",
}

GRADE_PREFIXES: dict[str, str] = {
    "administrateur":      "Admin",
    "super_moderateur":    "SM",
    "moderateur_plus":     "Modo+",
    "moderateur_confirme": "Modo",
    "moderateur_test":     "Modo",
    "guide":               "Guide",
}

GRADE_TO_ROLE_ATTR: dict[str, str] = {
    "administrateur":      "role_administrateur_id",
    "super_moderateur":    "role_super_moderateur_id",
    "moderateur_plus":     "role_moderateur_plus_id",
    "moderateur_confirme": "role_moderateur_confirme_id",
    "moderateur_test":     "role_moderateur_test_id",
    "guide":               "role_guide_id",
}

STAFF_GENERAL_GRADES: set[str] = set(GRADES_ORDER)

STATUTS_SECONDAIRES_ORDER: list[str] = ["journaliste", "affilie", "builder"]

STATUT_INCOMPATIBLE_GRADES: set[str] = {"administrateur", "super_moderateur"}

SECONDARY_STATUSES: dict[str, dict] = {
    "journaliste": {
        "label": "Journaliste",
        "badge": "📰",
        "role_attr": "role_journaliste_id",
        "has_second_pseudo": False,
    },
    "affilie": {
        "label": "Affilié",
        "badge": "🎥",
        "role_attr": "role_affilie_id",
        "has_second_pseudo": False,
    },
    "builder": {
        "label": "Builder",
        "badge": None,
        "role_attr": "role_builder_id",
        "has_second_pseudo": True,
    },
}


class AlphaStaffMember(Base, TimestampMixin):
    """Gestion d'un membre du staff."""

    __tablename__ = "alpha_staff"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    pseudo_jeu: Mapped[str] = mapped_column(String(64), nullable=False)
    grade: Mapped[str | None] = mapped_column(String(32), nullable=True)
    skin_head_emoji: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    is_journaliste: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_affilie: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_builder: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    pseudo_jeu_builder: Mapped[str | None] = mapped_column(String(64), nullable=True)

    blames: Mapped[list] = mapped_column(JSON, nullable=True, default=list)

    __table_args__ = (
        Index("ix_alpha_staff_grade", "grade"),
    )

    def to_dict(self) -> dict:
        return {
            "discord_id":         self.discord_id,
            "pseudo_jeu":         self.pseudo_jeu,
            "grade":              self.grade,
            "skin_head_emoji":    self.skin_head_emoji,
            "is_journaliste":     self.is_journaliste,
            "is_affilie":         self.is_affilie,
            "is_builder":         self.is_builder,
            "pseudo_jeu_builder": self.pseudo_jeu_builder,
            "blames":             self.blames or [],
        }

    def __repr__(self) -> str:
        return (
            f"<AlphaStaffMember id={self.id} pseudo={self.pseudo_jeu!r} "
            f"grade={self.grade!r} journaliste={self.is_journaliste} "
            f"affilie={self.is_affilie} builder={self.is_builder}>"
        )