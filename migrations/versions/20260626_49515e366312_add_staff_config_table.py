"""Add staff_config table

Revision ID: 49515e366312
Revises: bff7dab940c8
Create Date: 2026-06-26 13:43:29.820388

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '49515e366312'
down_revision: Union[str, None] = 'bff7dab940c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'staff_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('channel_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('update_interval_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('grades_order', postgresql.JSON(), nullable=False, server_default='[]'),
        sa.Column('staff', postgresql.JSON(), nullable=False, server_default='[]'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('staff_config')