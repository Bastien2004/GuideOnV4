"""Mod logs: dedicated moderation-actions-only channel column

Revision ID: f6b0c8e4d2a9
Revises: e5f2a9d3c1b7
Create Date: 2026-08-21 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'f6b0c8e4d2a9'
down_revision: Union[str, None] = 'e5f2a9d3c1b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'mod_log_configs',
        sa.Column('mod_action_channel_id', sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('mod_log_configs', 'mod_action_channel_id')