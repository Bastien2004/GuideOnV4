"""
utils/db/models/ng_staff.py — Membres du staff, multi-serveurs (refonte
multi-serveurs, phase 6, ex-AlphaStaffMember).

Table `ng_staff`, seule source de vérité pour les membres du staff sur tous
les serveurs NG. La migration décrite ici à l'origine (double-écriture avec
l'ancienne table AlphaStaffMember, le temps de migrer cogs/alpha/rank.py,
derank.py, stafflist.py, edit_stafflist.py, config_alpha.py) est terminée :
ces fichiers n'existent plus, tout passe par `utils.managers.ng_staff_manager`
(nomenclature nettoyée, Paul, 2026-08-22). Voir PHASE_6.md/PHASE_7.md pour
l'historique de cette décision.

Les constantes de hiérarchie (GRADES_ORDER, GRADE_LABELS, GRADE_EMOJIS,
GRADE_PREFIXES, GRADE_TO_ROLE_ATTR, STAFF_GENERAL_GRADES,
STATUT_INCOMPATIBLE_GRADES) restent définies UNE SEULE FOIS dans
utils.db.models.staff_grades (ex-alpha_staff.py) et sont ré-exportées ici
— "Hiérarchie des grades staff [...] inchangée en code" (§2 du prompt).
Ne pas dupliquer ces constantes.
"""
from __future__ import annotations

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin
from utils.db.models.staff_grades import (  # noqa: F401 — ré-export intentionnel
    GRADE_EMOJIS,
    GRADE_LABELS,
    GRADE_PREFIXES,
    GRADE_TO_ROLE_ATTR,
    GRADES_ORDER,
    STAFF_GENERAL_GRADES,
    STATUT_INCOMPATIBLE_GRADES,
)


class NGStaffMember(Base, TimestampMixin):
    """Membre du staff d'un serveur NG. PK composite (server, discord_id)."""

    __tablename__ = "ng_staff"

    server: Mapped[str] = mapped_column(
        String(32), ForeignKey("ng_servers.name"), primary_key=True
    )
    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

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
        Index("ix_ng_staff_server_grade", "server", "grade"),
    )

    def to_dict(self) -> dict:
        return {
            "server":             self.server,
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
            f"<NGStaffMember server={self.server!r} discord_id={self.discord_id} "
            f"pseudo={self.pseudo_jeu!r} grade={self.grade!r}>"
        )
