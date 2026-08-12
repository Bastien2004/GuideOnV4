"""ng_onu_configs

Refonte multi-serveurs phase 8 : crée ng_onu_configs / ng_onu_ping_members
(tables vides). Miroir de alpha_onu_configs / alpha_onu_ping_members mais
clé par `server` (nom NGServer) au lieu de `guild_id`. Le backfill des
données existantes se fait dans la révision suivante (cutover_onu_backfill).

Revision ID: c19a274bb2e0
Revises: ee241ae77a31
Create Date: 2026-07-24 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'c19a274bb2e0'
down_revision: Union[str, None] = 'ee241ae77a31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ng_onu_configs',
    sa.Column('server', sa.String(length=50), nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=True),
    sa.Column('role_id', sa.BigInteger(), nullable=True),
    sa.Column('jour_onu', sa.Integer(), nullable=True),
    sa.Column('pre_heure', sa.Integer(), nullable=True),
    sa.Column('pre_minute', sa.Integer(), nullable=True),
    sa.Column('ann_heure', sa.Integer(), nullable=True),
    sa.Column('ann_minute', sa.Integer(), nullable=True),
    sa.Column('timezone', sa.String(length=50), server_default='Europe/Paris', nullable=False),
    sa.Column('ping_mp', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('image_name', sa.String(length=100), nullable=True),
    sa.Column('join_url', sa.String(length=300), nullable=True),
    sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('server')
    )
    op.create_table('ng_onu_ping_members',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('server', sa.String(length=50), nullable=False),
    sa.Column('discord_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('server', 'discord_id', name='uq_ng_onu_ping_member')
    )
    op.create_index('ix_ng_onu_ping_server', 'ng_onu_ping_members', ['server'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ng_onu_ping_server', table_name='ng_onu_ping_members')
    op.drop_table('ng_onu_ping_members')
    op.drop_table('ng_onu_configs')
