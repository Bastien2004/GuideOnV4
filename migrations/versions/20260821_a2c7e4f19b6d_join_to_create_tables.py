"""Join to Create: config + generated channels tracking tables

Revision ID: a2c7e4f19b6d
Revises: f6b0c8e4d2a9
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'a2c7e4f19b6d'
down_revision: Union[str, None] = 'f6b0c8e4d2a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('join_to_create_configs',
    sa.Column('guild_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('trigger_channel_id', sa.BigInteger(), nullable=True),
    sa.Column('trigger_channel_name', sa.String(length=100), nullable=True),
    sa.Column('category_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('guild_id'),
    )

    op.create_table('join_to_create_channels',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=False),
    sa.Column('owner_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('channel_id', name='uq_join_to_create_channel_id'),
    )
    op.create_index('ix_join_to_create_channel_guild', 'join_to_create_channels', ['guild_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_join_to_create_channel_guild', table_name='join_to_create_channels')
    op.drop_table('join_to_create_channels')
    op.drop_table('join_to_create_configs')