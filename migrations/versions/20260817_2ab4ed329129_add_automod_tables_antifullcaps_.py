"""Add automod tables (antifullcaps, antispam_mention, antispam_emoji)

Revision ID: 2ab4ed329129
Revises: 40955668fced
Create Date: 2026-08-17 18:30:31.347813

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '2ab4ed329129'
down_revision: Union[str, None] = '40955668fced'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('mod_automod_antifullcaps_config',
    sa.Column('guild_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('min_length', sa.Integer(), server_default='10', nullable=False),
    sa.Column('ratio_threshold', sa.Float(), server_default='0.7', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('guild_id')
    )
    op.create_table('mod_automod_antispam_emoji_config',
    sa.Column('guild_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('max_emoji', sa.Integer(), server_default='10', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('guild_id')
    )
    op.create_table('mod_automod_antispam_mention_config',
    sa.Column('guild_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('enabled', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('max_mentions', sa.Integer(), server_default='5', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('guild_id')
    )
    # NOTE: drop_table sur notation_config, notation_operator, onu_config,
    # onu_ping retirés volontairement - tables legacy encore présentes en
    # base, à traiter séparément après vérification de leur usage réel.


def downgrade() -> None:
    op.drop_table('mod_automod_antispam_mention_config')
    op.drop_table('mod_automod_antispam_emoji_config')
    op.drop_table('mod_automod_antifullcaps_config')
