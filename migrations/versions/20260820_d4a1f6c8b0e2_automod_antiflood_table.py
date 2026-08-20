"""Automod Anti Flood: config table

Revision ID: d4a1f6c8b0e2
Revises: c39e5b2d1a74
Create Date: 2026-08-20 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'd4a1f6c8b0e2'
down_revision: Union[str, None] = 'c39e5b2d1a74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('mod_automod_antiflood_config',
    sa.Column('guild_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('min_length', sa.Integer(), server_default='20', nullable=False),
    sa.Column('min_vowel_ratio', sa.Float(), server_default='0.2', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('guild_id')
    )


def downgrade() -> None:
    op.drop_table('mod_automod_antiflood_config')