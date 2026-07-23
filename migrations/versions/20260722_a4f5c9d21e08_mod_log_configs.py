"""mod log configs

Revision ID: a4f5c9d21e08
Revises: 88f8a8607230
Create Date: 2026-07-22 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'a4f5c9d21e08'
down_revision: Union[str, None] = '88f8a8607230'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mod_log_configs',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('log_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('selected_pack', sa.String(length=16), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('guild_id'),
    )


def downgrade() -> None:
    op.drop_table('mod_log_configs')