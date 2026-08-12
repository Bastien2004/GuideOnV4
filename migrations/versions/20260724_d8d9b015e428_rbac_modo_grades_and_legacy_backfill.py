"""rbac modo grades and legacy backfill

Revision ID: d8d9b015e428
Revises: fe411fd65824
Create Date: 2026-07-24 16:00:00.000000

Phase 3 de la refonte multi-serveurs (PROMPT_REFONTE_MULTISERVER.md §12/§13).

Deux choses dans cette révision :

1. Ajout des grades 'modo_plus' et 'modo' à la catégorie 'staff_alpha',
   absents du seed initial (§12 phase 2) mais nécessaires pour reprendre
   fidèlement la hiérarchie historique de utils/perm_alpha.py :
       is_op_alpha    (le plus haut : DEV/CREATOR/OP_ALPHA)
       is_modo_plus   = is_op_alpha OR membre direct MODO_PLUS_ALPHA
       is_modo        = is_modo_plus OR membre direct MODO_ALPHA
   Traduit en inclusions RBAC ("parent inclut child" = membres de child
   comptent aussi comme parent) :
       modo_plus inclut op       (tout OP est aussi considéré modo_plus)
       modo      inclut modo_plus (tout modo_plus, donc tout OP, est aussi modo)
   Sans ces deux grades, les commandes events (cogs/alpha/event_list.py,
   event_start.py, event_regle.py), gardées par MODO_PLUS_ALPHA/MODO_ALPHA,
   n'auraient plus de grade RBAC équivalent après la migration legacy.

2. Backfill permission_entries -> permission_grade_members pour les 6
   valeurs de PermissionRole (utils/db/models/permission.py) :
       DEV             -> equipe_guideon.dev
       STAFF_GUIDEON   -> equipe_guideon.staff
       ADMIN           -> equipe_guideon.admin   (valeur absente de l'enum
                                                    actuel ; conservé pour
                                                    coller au document, no-op
                                                    tant qu'aucune ligne n'a
                                                    ce role)
       OP_ALPHA        -> staff_alpha.op
       MODO_PLUS_ALPHA -> staff_alpha.modo_plus
       MODO_ALPHA      -> staff_alpha.modo

ATTENTION (cf §14 du prompt) : permission_entries n'est PAS supprimée ici.
Plan de rollback = la table reste disponible pendant toute la période de
transition. Suppression uniquement en phase de nettoyage finale, après
validation prod complète des deux systèmes en parallèle.

Note sur le downgrade : la suppression du backfill est une best-effort
(DELETE ciblé, symétrique de l'INSERT...SELECT ci-dessous) plutôt qu'une
garantie stricte — si des memberships ont été ajoutés manuellement entre
l'upgrade et le downgrade sur les grades concernés, ils seront perdus.
Comportement documenté, cohérent avec le principe "chaque révision
reversible" du prompt tout en restant honnête sur les limites d'un rollback
de données (par opposition à un rollback de schéma, toujours exact ici).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'd8d9b015e428'
down_revision: Union[str, None] = 'fe411fd65824'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Mapping role legacy -> (category_slug, grade_slug), pour référence — le
# mapping réel exécuté est en SQL ci-dessous (miroir manuel, vérifié par
# relecture ; couvert côté Python testable par
# utils.managers.legacy_permission_migration.LEGACY_ROLE_TO_GRADE, voir
# tests/test_legacy_permission_migration.py).
LEGACY_ROLE_TO_GRADE = {
    "DEV": ("equipe_guideon", "dev"),
    "STAFF_GUIDEON": ("equipe_guideon", "staff"),
    "ADMIN": ("equipe_guideon", "admin"),
    "OP_ALPHA": ("staff_alpha", "op"),
    "MODO_PLUS_ALPHA": ("staff_alpha", "modo_plus"),
    "MODO_ALPHA": ("staff_alpha", "modo"),
}


def upgrade() -> None:
    # ── 1. Nouveaux grades staff_alpha ──────────────────────────────────
    op.execute("""
        INSERT INTO permission_grades (category_id, slug, display_name, position, created_at, updated_at)
        SELECT c.id, v.slug, v.display_name, v.position, now(), now()
        FROM permission_categories c CROSS JOIN (VALUES
            ('modo_plus', 'Modérateur+', 4),
            ('modo',      'Modérateur',  5)
        ) AS v(slug, display_name, position)
        WHERE c.slug = 'staff_alpha'
    """)

    # modo_plus inclut op ; modo inclut modo_plus
    op.execute("""
        INSERT INTO permission_grade_includes (parent_grade_id, child_grade_id, created_at, updated_at)
        SELECT p.id, c.id, now(), now()
        FROM permission_grades p, permission_grades c, permission_categories cat
        WHERE p.category_id = cat.id AND cat.slug = 'staff_alpha'
          AND c.category_id = cat.id
          AND p.slug = 'modo_plus' AND c.slug = 'op'
    """)
    op.execute("""
        INSERT INTO permission_grade_includes (parent_grade_id, child_grade_id, created_at, updated_at)
        SELECT p.id, c.id, now(), now()
        FROM permission_grades p, permission_grades c, permission_categories cat
        WHERE p.category_id = cat.id AND cat.slug = 'staff_alpha'
          AND c.category_id = cat.id
          AND p.slug = 'modo' AND c.slug = 'modo_plus'
    """)

    # ── 2. Backfill des membres legacy ──────────────────────────────────
    for role, (category_slug, grade_slug) in LEGACY_ROLE_TO_GRADE.items():
        op.execute(
            sa.text("""
                INSERT INTO permission_grade_members (grade_id, discord_id, created_at, updated_at)
                SELECT g.id, CAST(pe.discord_id AS BIGINT), now(), now()
                FROM permission_entries pe
                JOIN permission_grades g ON g.slug = :grade_slug
                JOIN permission_categories cat
                    ON cat.id = g.category_id AND cat.slug = :category_slug
                WHERE pe.role = :role
                ON CONFLICT (grade_id, discord_id) DO NOTHING
            """).bindparams(role=role, category_slug=category_slug, grade_slug=grade_slug)
        )


def downgrade() -> None:
    for role, (category_slug, grade_slug) in LEGACY_ROLE_TO_GRADE.items():
        op.execute(
            sa.text("""
                DELETE FROM permission_grade_members
                WHERE (grade_id, discord_id) IN (
                    SELECT g.id, CAST(pe.discord_id AS BIGINT)
                    FROM permission_entries pe
                    JOIN permission_grades g ON g.slug = :grade_slug
                    JOIN permission_categories cat
                        ON cat.id = g.category_id AND cat.slug = :category_slug
                    WHERE pe.role = :role
                )
            """).bindparams(role=role, category_slug=category_slug, grade_slug=grade_slug)
        )

    op.execute("""
        DELETE FROM permission_grade_includes
        WHERE parent_grade_id IN (
            SELECT g.id FROM permission_grades g
            JOIN permission_categories c ON c.id = g.category_id
            WHERE c.slug = 'staff_alpha' AND g.slug IN ('modo_plus', 'modo')
        )
        OR child_grade_id IN (
            SELECT g.id FROM permission_grades g
            JOIN permission_categories c ON c.id = g.category_id
            WHERE c.slug = 'staff_alpha' AND g.slug IN ('modo_plus', 'modo')
        )
    """)
    op.execute("""
        DELETE FROM permission_grades
        WHERE category_id = (SELECT id FROM permission_categories WHERE slug = 'staff_alpha')
        AND slug IN ('modo_plus', 'modo')
    """)
