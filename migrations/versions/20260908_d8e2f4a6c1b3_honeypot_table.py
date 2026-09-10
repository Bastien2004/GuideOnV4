"""HoneyPot ("piège") : table de config

Revision ID: d8e2f4a6c1b3
Revises: c7c1c1b9b3e4
Create Date: 2026-09-08 00:00:00.000000

Chaînée sur c7c1c1b9b3e4 (Join to Create multi-déclencheurs, migration
livrée à Paul plus tôt dans cette même passe de correctifs/évolutions —
à appliquer avant celle-ci si les deux sont mergées ensemble).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'd8e2f4a6c1b3'
down_revision: Union[str, None] = 'c7c1c1b9b3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('honeypot_configs',
    sa.Column('guild_id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('channel_id', sa.BigInteger(), nullable=True),
    sa.Column('enabled', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('ignored_role_ids', sa.JSON(), server_default='[]', nullable=False),
    sa.Column('ignored_member_ids', sa.JSON(), server_default='[]', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('guild_id'),
    )


def downgrade() -> None:
    op.drop_table('honeypot_configs')
