"""command_stats_daily : ajout guild_id (par serveur)

La table command_stats_daily agrégeait les stats de commandes tous
serveurs confondus. Le modèle a été mis à jour pour ajouter guild_id
(BigInteger, not null) afin de permettre des stats par serveur, avec
une nouvelle contrainte unique (command_name, guild_id, stat_date) et
un nouvel index sur guild_id.

Pas d'attribution par serveur possible sur les données historiques
existantes (l'ancienne table ne stockait pas guild_id) : sur décision
produit, on repart d'une table vide plutôt que de tenter un backfill.
On DROP puis on recrée la table avec le nouveau schéma.

Revision ID: 5f8e2a91c4d7
Revises: a1c4f7e9b2d6
Create Date: 2026-09-23 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '5f8e2a91c4d7'
down_revision: Union[str, None] = 'a1c4f7e9b2d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Historique non attribuable par serveur -> on repart de zéro
    # (décision produit, pas de backfill possible).
    op.drop_index('ix_command_stats_daily_date', table_name='command_stats_daily')
    op.drop_index('ix_command_stats_daily_command', table_name='command_stats_daily')
    op.drop_table('command_stats_daily')

    op.create_table('command_stats_daily',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('command_name', sa.String(length=64), nullable=False),
    sa.Column('guild_id', sa.BigInteger(), nullable=False),
    sa.Column('stat_date', sa.Date(), nullable=False),
    sa.Column('count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('command_name', 'guild_id', 'stat_date', name='uq_command_stats_daily_cmd_guild_date')
    )
    op.create_index('ix_command_stats_daily_command', 'command_stats_daily', ['command_name'], unique=False)
    op.create_index('ix_command_stats_daily_date', 'command_stats_daily', ['stat_date'], unique=False)
    op.create_index('ix_command_stats_daily_guild', 'command_stats_daily', ['guild_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_command_stats_daily_guild', table_name='command_stats_daily')
    op.drop_index('ix_command_stats_daily_date', table_name='command_stats_daily')
    op.drop_index('ix_command_stats_daily_command', table_name='command_stats_daily')
    op.drop_table('command_stats_daily')

    # Retour à l'ancien schéma (sans guild_id) - historique post-downgrade
    # perdu également, cohérent avec le fait que l'upgrade avait déjà
    # vidé la table.
    op.create_table('command_stats_daily',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('command_name', sa.String(length=64), nullable=False),
    sa.Column('stat_date', sa.Date(), nullable=False),
    sa.Column('count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('command_name', 'stat_date', name='uq_command_stats_daily_cmd_date')
    )
    op.create_index('ix_command_stats_daily_command', 'command_stats_daily', ['command_name'], unique=False)
    op.create_index('ix_command_stats_daily_date', 'command_stats_daily', ['stat_date'], unique=False)