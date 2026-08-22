"""NG statut defs: add has_stafflist_category (dedicated section in /ngstaff stafflist)

Revision ID: f56e635fb974
Revises: b3f8a2e6c1d4
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'f56e635fb974'
down_revision: Union[str, None] = 'b3f8a2e6c1d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ng_statut_defs',
        sa.Column('has_stafflist_category', sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Backfill : les statuts qui exigeaient déjà un pseudo secondaire (ex:
    # Builder) affichaient déjà leur propre section dans la stafflist avant
    # ce changement — on active le nouveau flag pour eux afin de ne rien
    # faire disparaître (le code applicatif garde de toute façon un OR entre
    # les deux flags, mais on aligne la donnée pour que la case "Catégorie
    # stafflist" de l'UI reflète l'état réel affiché).
    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE ng_statut_defs SET has_stafflist_category = true WHERE requires_second_pseudo = true"
    ))


def downgrade() -> None:
    op.drop_column('ng_statut_defs', 'has_stafflist_category')
