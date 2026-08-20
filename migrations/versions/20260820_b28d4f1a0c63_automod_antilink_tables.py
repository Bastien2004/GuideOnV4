"""Automod Anti Link: config + extensions tables

Revision ID: b28d4f1a0c63
Revises: a17c3f0e9b52
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'b28d4f1a0c63'
down_revision: Union[str, None] = 'a17c3f0e9b52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('mod_automod_antilink_config',
    sa.Column('guild_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('guild_id')
    )
    op.create_table('mod_automod_antilink_extensions',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('extension', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('guild_id', 'extension', name='uq_antilink_guild_extension'),
    )
    op.create_index('ix_antilink_guild', 'mod_automod_antilink_extensions', ['guild_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_antilink_guild', table_name='mod_automod_antilink_extensions')
    op.drop_table('mod_automod_antilink_extensions')
    op.drop_table('mod_automod_antilink_config')