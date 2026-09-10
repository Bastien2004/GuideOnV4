"""exp levelup announce (permanent, salon configurable)

Revision ID: a4f1e9c3b7d2
Revises: d8e2f4a6c1b3
Create Date: 2026-09-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'a4f1e9c3b7d2'
down_revision: Union[str, None] = 'd8e2f4a6c1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'exp_configs',
        sa.Column('levelup_announce_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'exp_configs',
        sa.Column('levelup_channel_id', sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('exp_configs', 'levelup_channel_id')
    op.drop_column('exp_configs', 'levelup_announce_enabled')
