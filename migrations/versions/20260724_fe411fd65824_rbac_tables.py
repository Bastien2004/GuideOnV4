"""rbac tables

Revision ID: fe411fd65824
Revises: f8653a67f007
Create Date: 2026-07-24 15:05:00.000000

Phase 2 de la refonte multi-serveurs (PROMPT_REFONTE_MULTISERVER.md §12).

Cree les 4 tables RBAC (permission_categories, permission_grades,
permission_grade_members, permission_grade_includes) et seed :
- categorie 'equipe_guideon' (libre, ng_server_id NULL) avec grades
  dev / staff / admin
- categorie 'staff_alpha' (liee a ng_servers.alpha) avec grades
  admin / sm / op, ou op inclut admin et sm

Ne touche PAS a permission_entries (ancien systeme) : la migration des
membres legacy vers permission_grade_members est une revision separee
(phase 3 du prompt de refonte), volontairement non incluse ici pour garder
cette revision reversible et isolee.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'fe411fd65824'
down_revision: Union[str, None] = 'f8653a67f007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'permission_categories',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('display_name', sa.String(length=128), nullable=False),
        sa.Column('ng_server_id', sa.Integer(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['ng_server_id'], ['ng_servers.id'], name='fk_permission_categories_ng_server'),
        sa.UniqueConstraint('slug', name='uq_permission_categories_slug'),
    )

    op.create_table(
        'permission_grades',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('display_name', sa.String(length=128), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['permission_categories.id'], name='fk_permission_grades_category'),
        sa.UniqueConstraint('category_id', 'slug', name='uq_grade_category_slug'),
    )

    op.create_table(
        'permission_grade_members',
        sa.Column('grade_id', sa.Integer(), nullable=False),
        sa.Column('discord_id', sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['grade_id'], ['permission_grades.id'], name='fk_permission_grade_members_grade'),
        sa.PrimaryKeyConstraint('grade_id', 'discord_id'),
    )

    op.create_table(
        'permission_grade_includes',
        sa.Column('parent_grade_id', sa.Integer(), nullable=False),
        sa.Column('child_grade_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['parent_grade_id'], ['permission_grades.id'], name='fk_pgi_parent'),
        sa.ForeignKeyConstraint(['child_grade_id'], ['permission_grades.id'], name='fk_pgi_child'),
        sa.PrimaryKeyConstraint('parent_grade_id', 'child_grade_id'),
        sa.CheckConstraint('parent_grade_id != child_grade_id', name='ck_no_self_include'),
    )

    # ── Seed : catégorie "Équipe GuideOn" (libre) ──────────────────────
    op.execute("""
        INSERT INTO permission_categories (slug, display_name, ng_server_id, position, created_at, updated_at)
        VALUES ('equipe_guideon', 'Équipe GuideOn', NULL, 1, now(), now())
    """)

    op.execute("""
        INSERT INTO permission_grades (category_id, slug, display_name, position, created_at, updated_at)
        SELECT c.id, v.slug, v.display_name, v.position, now(), now()
        FROM permission_categories c CROSS JOIN (VALUES
            ('dev',    'Développeur',    1),
            ('staff',  'Staff GuideOn',  2),
            ('admin',  'Administrateur', 3)
        ) AS v(slug, display_name, position)
        WHERE c.slug = 'equipe_guideon'
    """)

    # ── Seed : catégorie "Staff Alpha" (liée à ng_servers.alpha) ───────
    op.execute("""
        INSERT INTO permission_categories (slug, display_name, ng_server_id, position, created_at, updated_at)
        SELECT 'staff_alpha', 'Staff Alpha', s.id, 2, now(), now()
        FROM ng_servers s WHERE s.name = 'alpha'
    """)

    op.execute("""
        INSERT INTO permission_grades (category_id, slug, display_name, position, created_at, updated_at)
        SELECT c.id, v.slug, v.display_name, v.position, now(), now()
        FROM permission_categories c CROSS JOIN (VALUES
            ('admin', 'Administrateur',   1),
            ('sm',    'Super Modérateur', 2),
            ('op',    'Opérateur',        3)
        ) AS v(slug, display_name, position)
        WHERE c.slug = 'staff_alpha'
    """)

    # Inclusion : staff_alpha.op inclut staff_alpha.admin et staff_alpha.sm
    op.execute("""
        INSERT INTO permission_grade_includes (parent_grade_id, child_grade_id, created_at, updated_at)
        SELECT p.id, c.id, now(), now()
        FROM permission_grades p, permission_grades c, permission_categories cat
        WHERE p.category_id = cat.id AND cat.slug = 'staff_alpha'
          AND c.category_id = cat.id
          AND p.slug = 'op' AND c.slug IN ('admin', 'sm')
    """)


def downgrade() -> None:
    op.drop_table('permission_grade_includes')
    op.drop_table('permission_grade_members')
    op.drop_table('permission_grades')
    op.drop_table('permission_categories')
