"""Automod No Link: config + whitelist tables

Revision ID: a17c3f0e9b52
Revises: 4d023031c69d
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'a17c3f0e9b52'
down_revision: Union[str, None] = '4d023031c69d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('mod_automod_nolink_config',
    sa.Column('guild_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('guild_id')
    )
    op.create_table('mod_automod_nolink_whitelist',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('guild_id', 'channel_id', name='uq_nolink_guild_channel'),
    )
    op.create_index('ix_nolink_guild', 'mod_automod_nolink_whitelist', ['guild_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_nolink_guild', table_name='mod_automod_nolink_whitelist')
    op.drop_table('mod_automod_nolink_whitelist')
    op.drop_table('mod_automod_nolink_config')