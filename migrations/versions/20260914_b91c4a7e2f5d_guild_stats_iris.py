"""guild stats iris (arrivées/départs/vocal/messages)

Revision ID: b91c4a7e2f5d
Revises: a4f1e9c3b7d2
Create Date: 2026-09-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'b91c4a7e2f5d'
down_revision: Union[str, None] = 'a4f1e9c3b7d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'guild_activity_stats_daily',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('stat_date', sa.Date(), nullable=False),
        sa.Column('arrivals', sa.Integer(), server_default='0', nullable=False),
        sa.Column('departures', sa.Integer(), server_default='0', nullable=False),
        sa.Column('voice_minutes', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guild_id', 'stat_date', name='uq_guild_activity_stats_daily_guild_date'),
    )
    op.create_index(
        'ix_guild_activity_stats_daily_guild_date', 'guild_activity_stats_daily', ['guild_id', 'stat_date'], unique=False,
    )

    op.create_table(
        'guild_message_stats_daily',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('stat_date', sa.Date(), nullable=False),
        sa.Column('message_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guild_id', 'user_id', 'stat_date', name='uq_guild_message_stats_daily_guild_user_date'),
    )
    op.create_index(
        'ix_guild_message_stats_daily_guild_date', 'guild_message_stats_daily', ['guild_id', 'stat_date'], unique=False,
    )
    op.create_index(
        'ix_guild_message_stats_daily_guild_user', 'guild_message_stats_daily', ['guild_id', 'user_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_guild_message_stats_daily_guild_user', table_name='guild_message_stats_daily')
    op.drop_index('ix_guild_message_stats_daily_guild_date', table_name='guild_message_stats_daily')
    op.drop_table('guild_message_stats_daily')

    op.drop_index('ix_guild_activity_stats_daily_guild_date', table_name='guild_activity_stats_daily')
    op.drop_table('guild_activity_stats_daily')