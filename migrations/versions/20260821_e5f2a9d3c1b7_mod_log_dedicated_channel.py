"""Mod lock: role exemption tracking table

Revision ID: e5f2a9d3c1b7
Revises: d4a1f6c8b0e2
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'e5f2a9d3c1b7'
down_revision: Union[str, None] = 'd4a1f6c8b0e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('mod_channel_lock_exemptions',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=False),
    sa.Column('role_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('channel_id', 'role_id', name='uq_lock_exemption_channel_role'),
    )
    op.create_index('ix_lock_exemption_channel', 'mod_channel_lock_exemptions', ['channel_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_lock_exemption_channel', table_name='mod_channel_lock_exemptions')
    op.drop_table('mod_channel_lock_exemptions')