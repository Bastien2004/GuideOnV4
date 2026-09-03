"""MEDIALINK: connections, templates, rules, events, logs tables

Revision ID: 3557ccbcee08
Revises: 9a3fd03e2d01
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '3557ccbcee08'
down_revision: Union[str, None] = '9a3fd03e2d01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── media_connections ────────────────────────────────────────
    # Comptes/chaînes suivis (utils/db/models/medialink_connection.py).
    op.create_table('media_connections',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('platform', sa.String(length=16), nullable=False),
    sa.Column('external_id', sa.String(length=128), nullable=False),
    sa.Column('external_username', sa.String(length=255), nullable=True),
    sa.Column('external_url', sa.Text(), nullable=True),
    sa.Column('avatar_url', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=16), server_default='operational', nullable=False),
    sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_event_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('guild_id', 'platform', 'external_id', name='uq_medialink_conn_guild_platform_external'),
    )
    op.create_index('ix_medialink_conn_guild_platform', 'media_connections', ['guild_id', 'platform'], unique=False)

    # ── media_templates ──────────────────────────────────────────
    # Modèles d'annonce (utils/db/models/medialink_template.py).
    op.create_table('media_templates',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('embed_config', sa.JSON(), nullable=True),
    sa.Column('buttons', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_medialink_template_guild', 'media_templates', ['guild_id'], unique=False)

    # ── media_rules ───────────────────────────────────────────────
    # Règles de diffusion (utils/db/models/medialink_rule.py) — dépend de
    # media_connections ET media_templates (template_id nullable).
    op.create_table('media_rules',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('connection_id', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.String(length=48), nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=False),
    sa.Column('template_id', sa.Integer(), nullable=True),
    sa.Column('mention_role_id', sa.BigInteger(), nullable=True),
    sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.ForeignKeyConstraint(['connection_id'], ['media_connections.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['template_id'], ['media_templates.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_medialink_rule_connection', 'media_rules', ['connection_id'], unique=False)
    op.create_index('ix_medialink_rule_connection_event', 'media_rules', ['connection_id', 'event_type'], unique=False)

    # ── media_events ─────────────────────────────────────────────
    # Journal des événements détectés (utils/db/models/medialink_event.py).
    # La UniqueConstraint(connection_id, external_event_id) EST
    # l'implémentation de la clé anti-doublon du §9.1.
    op.create_table('media_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('connection_id', sa.Integer(), nullable=False),
    sa.Column('external_event_id', sa.String(length=128), nullable=False),
    sa.Column('event_type', sa.String(length=48), nullable=False),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('url', sa.Text(), nullable=True),
    sa.Column('thumbnail', sa.Text(), nullable=True),
    sa.Column('author', sa.String(length=255), nullable=True),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=16), server_default='pending', nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('connection_id', 'external_event_id', name='uq_medialink_event_connection_external'),
    sa.ForeignKeyConstraint(['connection_id'], ['media_connections.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_medialink_event_connection', 'media_events', ['connection_id'], unique=False)
    op.create_index('ix_medialink_event_status', 'media_events', ['status'], unique=False)

    # ── media_logs ───────────────────────────────────────────────
    # Journal technique (utils/db/models/medialink_log.py) — append-only,
    # pas de updated_at (pas de TimestampMixin sur ce modèle).
    op.create_table('media_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('connection_id', sa.Integer(), nullable=True),
    sa.Column('level', sa.String(length=16), server_default='info', nullable=False),
    sa.Column('event_type', sa.String(length=48), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.ForeignKeyConstraint(['connection_id'], ['media_connections.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_medialink_log_guild_created', 'media_logs', ['guild_id', 'created_at'], unique=False)
    op.create_index('ix_medialink_log_connection', 'media_logs', ['connection_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_medialink_log_connection', table_name='media_logs')
    op.drop_index('ix_medialink_log_guild_created', table_name='media_logs')
    op.drop_table('media_logs')

    op.drop_index('ix_medialink_event_status', table_name='media_events')
    op.drop_index('ix_medialink_event_connection', table_name='media_events')
    op.drop_table('media_events')

    op.drop_index('ix_medialink_rule_connection_event', table_name='media_rules')
    op.drop_index('ix_medialink_rule_connection', table_name='media_rules')
    op.drop_table('media_rules')

    op.drop_index('ix_medialink_template_guild', table_name='media_templates')
    op.drop_table('media_templates')

    op.drop_index('ix_medialink_conn_guild_platform', table_name='media_connections')
    op.drop_table('media_connections')