"""Automod v3: staff_role_id + notification_window + active_alerts

Revision ID: 4d023031c69d
Revises: 2ab4ed329129
Create Date: 2026-08-17 20:33:35.705263

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '4d023031c69d'
down_revision: Union[str, None] = '2ab4ed329129'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('mod_automod_active_alerts',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=False),
    sa.Column('system_key', sa.String(length=32), nullable=False),
    sa.Column('alert_channel_id', sa.BigInteger(), nullable=False),
    sa.Column('alert_message_id', sa.BigInteger(), nullable=False),
    sa.Column('matched_term', sa.String(length=200), nullable=True),
    sa.Column('message_excerpt', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('taken_by_user_id', sa.BigInteger(), nullable=True),
    sa.Column('taken_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_automod_alert_guild_user', 'mod_automod_active_alerts', ['guild_id', 'user_id'], unique=False)
    op.create_index('ix_automod_alert_message', 'mod_automod_active_alerts', ['alert_message_id'], unique=False)
    op.add_column('mod_automod_general', sa.Column('staff_role_id', sa.BigInteger(), nullable=True))
    op.add_column('mod_automod_general', sa.Column('notification_window_seconds', sa.Integer(), server_default='60', nullable=False))
    # NOTE: drop_table sur notation_config, notation_operator, onu_config,
    # onu_ping retirés volontairement - tables legacy encore présentes en
    # base, à traiter séparément après vérification de leur usage réel.


def downgrade() -> None:
    op.drop_column('mod_automod_general', 'notification_window_seconds')
    op.drop_column('mod_automod_general', 'staff_role_id')
    op.drop_index('ix_automod_alert_message', table_name='mod_automod_active_alerts')
    op.drop_index('ix_automod_alert_guild_user', table_name='mod_automod_active_alerts')
    op.drop_table('mod_automod_active_alerts')
