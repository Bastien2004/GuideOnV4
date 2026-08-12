"""ng rank configs

Revision ID: 01b6d63bd279
Revises: 69749f8179cd
Create Date: 2026-07-24 19:00:00.000000

Phase 7 de la refonte multi-serveurs (PROMPT_REFONTE_MULTISERVER.md §12/§13).

Cree la table ng_rank_configs (schema seul, vide) — meme approche que
ng_staff en phase 6 : table neuve en parallele de alpha_rank_configs,
PK `server` (au lieu de `guild_id`), memes champs (voir docstring de
utils/db/models/ng_rank_config.py pour la note sur les champs content_*).

Contrairement a ng_staff en phase 6, CETTE FOIS le backfill + bascule des
consommateurs (rank.py, derank.py, stafflist.py, config_alpha, staff_api,
...) sont faits dans la MEME série de révisions (voir la révision suivante
qui fait le backfill) — la phase 7 est un cutover complet, pas une
préparation. alpha_staff et alpha_rank_configs restent en base après coup
(non supprimées, non renommées) comme filet de sécurité, mais plus aucun
code applicatif ne les lit ou les écrit après cette phase.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '01b6d63bd279'
down_revision: Union[str, None] = '69749f8179cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ng_rank_configs',
        sa.Column('server', sa.String(length=32), nullable=False),
        sa.Column('rank_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('journaliste_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('dev_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('journaliste_ping_id', sa.BigInteger(), nullable=True),
        sa.Column('dev_ping_id', sa.BigInteger(), nullable=True),
        sa.Column('role_journaliste_id', sa.BigInteger(), nullable=True),
        sa.Column('role_guide_id', sa.BigInteger(), nullable=True),
        sa.Column('role_moderateur_test_id', sa.BigInteger(), nullable=True),
        sa.Column('role_moderateur_confirme_id', sa.BigInteger(), nullable=True),
        sa.Column('role_moderateur_plus_id', sa.BigInteger(), nullable=True),
        sa.Column('role_super_moderateur_id', sa.BigInteger(), nullable=True),
        sa.Column('role_administrateur_id', sa.BigInteger(), nullable=True),
        sa.Column('role_affilie_id', sa.BigInteger(), nullable=True),
        sa.Column('role_builder_id', sa.BigInteger(), nullable=True),
        sa.Column('role_equipe_id', sa.BigInteger(), nullable=True),
        sa.Column('content_nous_rejoindre_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('content_nous_rejoindre_ping_id', sa.BigInteger(), nullable=True),
        sa.Column('content_nous_rejoindre_emoji', sa.String(length=100), nullable=True),
        sa.Column('content_index_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('content_index_emoji', sa.String(length=100), nullable=True),
        sa.Column('content_regle_interne_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('content_regle_interne_emoji', sa.String(length=100), nullable=True),
        sa.Column('content_stafflist_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('rank_emoji', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['server'], ['ng_servers.name'], name='fk_ng_rank_configs_server'),
        sa.PrimaryKeyConstraint('server', name='pk_ng_rank_configs'),
    )


def downgrade() -> None:
    op.drop_table('ng_rank_configs')
