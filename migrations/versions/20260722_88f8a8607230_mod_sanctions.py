"""mod sanctions

Revision ID: 88f8a8607230
Revises: e83ace29e416
Create Date: 2026-07-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '88f8a8607230'
down_revision: Union[str, None] = 'e83ace29e416'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mod_sanctions',
        sa.Column('id', sa.String(length=6), nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('moderator_id', sa.BigInteger(), nullable=False),
        sa.Column('type', sa.String(length=16), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by', sa.BigInteger(), nullable=True),
        sa.Column('revoked_reason', sa.Text(), nullable=True),
        sa.Column('dm_sent', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mod_sanctions_guild_user', 'mod_sanctions', ['guild_id', 'user_id'], unique=False)
    op.create_index('ix_mod_sanctions_guild_active', 'mod_sanctions', ['guild_id', 'active'], unique=False)

    op.create_table(
        'mod_sanction_configs',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('softban_purge_seconds', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('guild_id'),
    )


def downgrade() -> None:
    op.drop_table('mod_sanction_configs')
    op.drop_index('ix_mod_sanctions_guild_active', table_name='mod_sanctions')
    op.drop_index('ix_mod_sanctions_guild_user', table_name='mod_sanctions')
    op.drop_table('mod_sanctions')
