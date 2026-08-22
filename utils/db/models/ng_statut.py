"""
utils/db/models/ng_statut.py — Statuts secondaires (non hiérarchiques),
définis librement par chaque serveur NG (ex: builder, journaliste, avocat,
équipe com...), remplace le dict figé à 3 entrées (SECONDARY_STATUSES,
utils/db/models/alpha_staff.py) qui ne permettait ni d'ajouter, ni de
renommer, ni de retirer un statut sans toucher au code (Paul, 2026-08-22).

Deux tables :
  - NGStatutDef   : la définition d'un statut pour un serveur donné (clé,
                    libellé, emoji, rôle Discord, "pseudo secondaire requis"
                    ou non — généralisation du besoin spécifique à Builder
                    aujourd'hui —, position d'affichage, et désormais
                    "catégorie dédiée dans la stafflist" — has_stafflist_category,
                    ajouté Paul 2026-08-22 : n'importe quel statut (builder,
                    com, affilié, journaliste, avocat...) peut avoir sa
                    propre section dans /ngstaff stafflist, indépendamment
                    de requires_second_pseudo — voir views/ngstaff/stafflist_view.py).
  - NGStaffStatut : qui détient quel statut (table de liaison), remplace les
                    colonnes is_journaliste/is_affilie/is_builder de
                    NGStaffMember. Ces colonnes legacy sont CONSERVÉES en DB
                    (non destructif) mais plus lues par le code applicatif
                    une fois la bascule faite — voir la migration
                    migrations/versions/*_ng_statuts_tables.py qui backfill
                    les statuts existants (journaliste/affilié/builder) dans
                    ces nouvelles tables sans perte de donnée.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class NGStatutDef(Base, TimestampMixin):
    """Définition d'un statut secondaire pour un serveur NG (ex: 'builder', 'avocat')."""

    __tablename__ = "ng_statut_defs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server: Mapped[str] = mapped_column(String(32), ForeignKey("ng_servers.name"), nullable=False)
    key: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    requires_second_pseudo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    has_stafflist_category: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        UniqueConstraint("server", "key", name="uq_ng_statut_def_server_key"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "server": self.server,
            "key": self.key,
            "label": self.label,
            "emoji": self.emoji,
            "role_id": self.role_id,
            "requires_second_pseudo": self.requires_second_pseudo,
            "has_stafflist_category": self.has_stafflist_category,
            "position": self.position,
        }

    def __repr__(self) -> str:
        return f"<NGStatutDef server={self.server!r} key={self.key!r} label={self.label!r}>"


class NGStaffStatut(Base, TimestampMixin):
    """Attribution d'un statut à un membre du staff (table de liaison)."""

    __tablename__ = "ng_staff_statuts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server: Mapped[str] = mapped_column(String(32), ForeignKey("ng_servers.name"), nullable=False)
    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    statut_def_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ng_statut_defs.id", ondelete="CASCADE"), nullable=False
    )
    second_pseudo: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("discord_id", "statut_def_id", name="uq_ng_staff_statut_member_def"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "server": self.server,
            "discord_id": self.discord_id,
            "statut_def_id": self.statut_def_id,
            "second_pseudo": self.second_pseudo,
        }

    def __repr__(self) -> str:
        return (
            f"<NGStaffStatut server={self.server!r} discord_id={self.discord_id} "
            f"statut_def_id={self.statut_def_id}>"
        )