"""ng_nota_tables

Refonte multi-serveurs phase 9 : crée ng_nota_configs / ng_nota_week_states /
ng_nota_availabilities / ng_nota_history (tables vides). Miroir des 4 tables
alpha_nota_* mais clées par `server` (nom NGServer) au lieu de `guild_id`.
Le backfill des données existantes se fait dans la révision suivante
(cutover_nota_backfill).

Revision ID: 2b7f6e9d1a44
Revises: 5a8e3c1f9b02
Create Date: 2026-07-24 19:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '2b7f6e9d1a44'
down_revision: Union[str, None] = '5a8e3c1f9b02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ng_nota_availabilities',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('server', sa.String(length=50), nullable=False),
    sa.Column('discord_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('server', 'discord_id', name='uq_ng_nota_availability')
    )
    op.create_index('ix_ng_nota_avail_server', 'ng_nota_availabilities', ['server'], unique=False)
    op.create_table('ng_nota_configs',
    sa.Column('server', sa.String(length=50), nullable=False),
    sa.Column('channel_staff_id', sa.BigInteger(), nullable=True),
    sa.Column('channel_public_id', sa.BigInteger(), nullable=True),
    sa.Column('channel_logs_id', sa.BigInteger(), nullable=True),
    sa.Column('role_id', sa.BigInteger(), nullable=True),
    sa.Column('countries_count', sa.Integer(), server_default='238', nullable=False),
    sa.Column('send_presence_weekday', sa.Integer(), nullable=True),
    sa.Column('send_presence_hour', sa.Integer(), nullable=True),
    sa.Column('send_presence_minute', sa.Integer(), nullable=True),
    sa.Column('deadline_weekday', sa.Integer(), nullable=True),
    sa.Column('deadline_hour', sa.Integer(), nullable=True),
    sa.Column('deadline_minute', sa.Integer(), nullable=True),
    sa.Column('send_public_weekday', sa.Integer(), nullable=True),
    sa.Column('send_public_hour', sa.Integer(), nullable=True),
    sa.Column('send_public_minute', sa.Integer(), nullable=True),
    sa.Column('url_country_lookup', sa.String(length=300), nullable=True),
    sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('server')
    )
    op.create_table('ng_nota_history',
    sa.Column('server', sa.String(length=50), nullable=False),
    sa.Column('discord_id', sa.BigInteger(), nullable=False),
    sa.Column('last_range_start', sa.Integer(), nullable=True),
    sa.Column('last_range_end', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('server', 'discord_id')
    )
    op.create_table('ng_nota_week_states',
    sa.Column('server', sa.String(length=50), nullable=False),
    sa.Column('availability_message_id', sa.BigInteger(), nullable=True),
    sa.Column('public_message_id', sa.BigInteger(), nullable=True),
    sa.Column('reminder_sent', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('assigned_ranges', sa.Text(), server_default='[]', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('server')
    )


def downgrade() -> None:
    op.drop_table('ng_nota_week_states')
    op.drop_table('ng_nota_history')
    op.drop_table('ng_nota_configs')
    op.drop_index('ix_ng_nota_avail_server', table_name='ng_nota_availabilities')
    op.drop_table('ng_nota_availabilities')
