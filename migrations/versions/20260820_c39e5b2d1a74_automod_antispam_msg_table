"""Automod Anti Spam Message: config table

Revision ID: c39e5b2d1a74
Revises: b28d4f1a0c63
Create Date: 2026-08-20 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'c39e5b2d1a74'
down_revision: Union[str, None] = 'b28d4f1a0c63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('mod_automod_antispam_msg_config',
    sa.Column('guild_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('window_seconds', sa.Integer(), server_default='10', nullable=False),
    sa.Column('max_messages', sa.Integer(), server_default='3', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('guild_id')
    )


def downgrade() -> None:
    op.drop_table('mod_automod_antispam_msg_config')