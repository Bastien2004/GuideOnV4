"""QR codes : table d'historique manquante (utils/db/models/qr_code.py)

Revision ID: a1c4f7e9b2d6
Revises: b91c4a7e2f5d
Create Date: 2026-09-22 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'a1c4f7e9b2d6'
down_revision: Union[str, None] = 'b91c4a7e2f5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('qr_codes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('contenu', sa.String(length=2000), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_qr_codes_user_id'), 'qr_codes', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_qr_codes_user_id'), table_name='qr_codes')
    op.drop_table('qr_codes')