"""
utils/db/models/permission_rbac.py — Systeme de permissions RBAC (grades).

Remplace integralement PermissionRole (enum) + PermissionEntry
(utils.db.models.permission, retire en phase 15 : nettoyage legacy, voir
PHASE_15.md). La table permission_entries elle-meme reste geleee en base
jusqu'a l'execution de la migration DROP TABLE preparee dans cette phase.

Modele :
    PermissionCategory  — groupement logique de grades (ex: "Staff Alpha")
    PermissionGrade      — un grade concret, identifie par {category.slug}.{grade.slug}
    PermissionGradeMember  — membres directs d'un grade (discord_id)
    PermissionGradeInclude — inclusion recursive : parent inclut child (union
                              a la resolution, voir utils.managers.permission_rbac_manager)

Cycles d'inclusion interdits — check applicatif obligatoire avant tout INSERT
dans PermissionGradeInclude (voir permission_rbac_manager.add_include). Le
CheckConstraint ci-dessous ne bloque que l'auto-inclusion directe (A inclut A),
pas les cycles indirects (A->B->A), qui doivent etre detectes cote manager.
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from utils.db.base import Base, TimestampMixin


class PermissionCategory(Base, TimestampMixin):
    """Groupement logique de grades. Ex: "Équipe GuideOn", "Staff Alpha"."""

    __tablename__ = "permission_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    ng_server_id: Mapped[int | None] = mapped_column(
        ForeignKey("ng_servers.id"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    def __repr__(self) -> str:
        return f"<PermissionCategory id={self.id} slug={self.slug!r}>"


class PermissionGrade(Base, TimestampMixin):
    """Un grade concret. Identifie completement par {category.slug}.{slug}."""

    __tablename__ = "permission_grades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("permission_categories.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        UniqueConstraint("category_id", "slug", name="uq_grade_category_slug"),
    )

    def __repr__(self) -> str:
        return f"<PermissionGrade id={self.id} category_id={self.category_id} slug={self.slug!r}>"


class PermissionGradeMember(Base, TimestampMixin):
    """Membres directs d'un grade. Un user peut appartenir a plusieurs grades."""

    __tablename__ = "permission_grade_members"

    grade_id: Mapped[int] = mapped_column(
        ForeignKey("permission_grades.id"), primary_key=True
    )
    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    def __repr__(self) -> str:
        return f"<PermissionGradeMember grade_id={self.grade_id} discord_id={self.discord_id}>"


class PermissionGradeInclude(Base, TimestampMixin):
    """
    Inclusion : parent_grade_id inclut child_grade_id.

    Ex: parent="staff_alpha.op", child="staff_alpha.admin" => tout admin
    est aussi considere op a la resolution (has_grade recursive).

    Cycles interdits — check applicatif obligatoire a l'INSERT (voir
    permission_rbac_manager.add_include), le CheckConstraint ne couvre que
    l'auto-inclusion triviale (parent == child).
    """

    __tablename__ = "permission_grade_includes"

    parent_grade_id: Mapped[int] = mapped_column(
        ForeignKey("permission_grades.id"), primary_key=True
    )
    child_grade_id: Mapped[int] = mapped_column(
        ForeignKey("permission_grades.id"), primary_key=True
    )

    __table_args__ = (
        CheckConstraint("parent_grade_id != child_grade_id", name="ck_no_self_include"),
    )

    def __repr__(self) -> str:
        return (
            f"<PermissionGradeInclude parent={self.parent_grade_id} "
            f"child={self.child_grade_id}>"
        )
