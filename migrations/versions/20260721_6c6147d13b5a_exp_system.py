"""exp system

Revision ID: 6c6147d13b5a
Revises: bf2fb26d2c20
Create Date: 2026-07-21 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '6c6147d13b5a'
down_revision: Union[str, None] = 'bf2fb26d2c20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'exp_configs',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('exp_per_message', sa.Integer(), nullable=False),
        sa.Column('exp_per_voice_minute', sa.Integer(), nullable=False),
        sa.Column('boost_role_id', sa.BigInteger(), nullable=True),
        sa.Column('boost_percent', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('guild_id'),
    )

    op.create_table(
        'exp_users',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('total_exp', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('guild_id', 'user_id'),
    )
    op.create_index('ix_exp_users_guild', 'exp_users', ['guild_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_exp_users_guild', table_name='exp_users')
    op.drop_table('exp_users')
    op.drop_table('exp_configs')
