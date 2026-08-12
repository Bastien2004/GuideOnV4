"""ng_role_react_tables

Refonte multi-serveurs phase 10 : crée ng_role_reactions / ng_role_react_couples
(tables vides). Miroir de alpha_role_react_configs / alpha_role_react_entries
mais clées par `server` (nom NGServer) au lieu de `guild_id`.

Différence avec l'original : ng_role_react_couples.server porte une vraie FK
vers ng_role_reactions.server avec ON DELETE CASCADE (exigence explicite du
§4.2 du prompt, ligne role-react du tableau de mapping — contrairement aux
autres tables enfants des phases 6-9 qui n'avaient pas de FK déclarée).
Le backfill des données existantes se fait dans la révision suivante
(cutover_role_react_backfill).

Revision ID: 9f3a1c6e5d70
Revises: 7d4c8f3e2b91
Create Date: 2026-07-24 19:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '9f3a1c6e5d70'
down_revision: Union[str, None] = '7d4c8f3e2b91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ng_role_reactions',
    sa.Column('server', sa.String(length=50), nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=True),
    sa.Column('message_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('server')
    )
    op.create_table('ng_role_react_couples',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('server', sa.String(length=50), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('role_id', sa.BigInteger(), nullable=False),
    sa.Column('label', sa.String(length=80), nullable=False),
    sa.Column('emoji', sa.String(length=100), nullable=True),
    sa.Column('description', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['server'], ['ng_role_reactions.server'], name='fk_ng_role_react_couples_server', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('server', 'position', name='uq_ng_role_react_pos'),
    sa.UniqueConstraint('server', 'role_id', name='uq_ng_role_react_role')
    )
    op.create_index('ix_ng_role_react_server', 'ng_role_react_couples', ['server'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ng_role_react_server', table_name='ng_role_react_couples')
    op.drop_table('ng_role_react_couples')
    op.drop_table('ng_role_reactions')
