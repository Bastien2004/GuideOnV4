"""bot_guild_events : table manquante (utils/db/models/bot_guild_event.py)

La table bot_guild_events (historique des ajouts/retraits du bot sur des
serveurs Discord, utilisée par utils/managers/guild_growth_manager.py et
cogs/events/guild_growth_listener.py) a été introduite avec le modèle
mais sans migration correspondante. Sans cette table, on_guild_join et
on_guild_remove lèvent une exception non interceptée à chaque événement.

Revision ID: e3b7f1a9d5c2
Revises: 5f8e2a91c4d7
Create Date: 2026-09-23 00:00:01.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'e3b7f1a9d5c2'
down_revision: Union[str, None] = '5f8e2a91c4d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('bot_guild_events',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('event_type', sa.String(length=10), nullable=False),
    sa.Column('guild_name', sa.String(length=100), nullable=True),
    sa.Column('member_count', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bot_guild_events_guild_date', 'bot_guild_events', ['guild_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_bot_guild_events_guild_date', table_name='bot_guild_events')
    op.drop_table('bot_guild_events')