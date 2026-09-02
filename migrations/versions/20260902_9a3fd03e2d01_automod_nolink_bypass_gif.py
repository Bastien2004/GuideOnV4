"""Automod No Link: bypass_gif column

Revision ID: 9a3fd03e2d01
Revises: f56e635fb974
Create Date: 2026-09-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '9a3fd03e2d01'
down_revision: Union[str, None] = 'f56e635fb974'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'mod_automod_nolink_config',
        sa.Column('bypass_gif', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('mod_automod_nolink_config', 'bypass_gif')