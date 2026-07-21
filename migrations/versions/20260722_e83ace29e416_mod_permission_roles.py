"""mod permission roles

Revision ID: e83ace29e416
Revises: 6c6147d13b5a
Create Date: 2026-07-22 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'e83ace29e416'
down_revision: Union[str, None] = '6c6147d13b5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mod_permission_roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('permission_key', sa.String(length=64), nullable=False),
        sa.Column('role_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guild_id', 'permission_key', 'role_id', name='uq_mod_permission_role'),
    )
    op.create_index(
        'ix_mod_permission_guild_key', 'mod_permission_roles', ['guild_id', 'permission_key'], unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_mod_permission_guild_key', table_name='mod_permission_roles')
    op.drop_table('mod_permission_roles')
