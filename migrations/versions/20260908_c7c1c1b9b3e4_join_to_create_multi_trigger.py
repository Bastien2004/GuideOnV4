"""Join to Create: plusieurs déclencheurs par serveur (1 gratuit / 3 Gold+)

Revision ID: c7c1c1b9b3e4
Revises: 91702a990fd8
Create Date: 2026-09-08 00:00:00.000000

Bascule join_to_create_configs de "1 ligne par guild (guild_id en PK)" à
"plusieurs lignes par guild (id auto-incrémenté en PK, guild_id indexé)" —
cf. utils/db/models/join_to_create.py pour le contexte métier (limite 1
salon déclencheur gratuit / 3 en Gold+, chacun dans une catégorie
différente, cf. is_gold() + utils/managers/join_to_create_manager.py).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'c7c1c1b9b3e4'
down_revision: Union[str, None] = '91702a990fd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "join_to_create_configs"
_SEQ = "join_to_create_configs_id_seq"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column('id', sa.BigInteger(), nullable=True))
    op.execute(f"CREATE SEQUENCE {_SEQ} OWNED BY {_TABLE}.id")
    op.execute(f"UPDATE {_TABLE} SET id = nextval('{_SEQ}')")
    op.execute(f"ALTER TABLE {_TABLE} ALTER COLUMN id SET DEFAULT nextval('{_SEQ}')")
    op.alter_column(_TABLE, 'id', nullable=False)

    op.drop_constraint(f"{_TABLE}_pkey", _TABLE, type_='primary')
    op.create_primary_key(f"{_TABLE}_pkey", _TABLE, ['id'])

    op.create_index(f"ix_{_TABLE}_guild_id", _TABLE, ['guild_id'], unique=False)

    op.create_unique_constraint(
        'uq_join_to_create_guild_category', _TABLE, ['guild_id', 'category_id'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_join_to_create_guild_category', _TABLE, type_='unique')
    op.drop_index(f"ix_{_TABLE}_guild_id", table_name=_TABLE)

    op.drop_constraint(f"{_TABLE}_pkey", _TABLE, type_='primary')
    op.execute(f"ALTER TABLE {_TABLE} ALTER COLUMN id DROP DEFAULT")
    op.execute(f"DROP SEQUENCE IF EXISTS {_SEQ}")

    op.create_primary_key(f"{_TABLE}_pkey", _TABLE, ['guild_id'])
    op.drop_column(_TABLE, 'id')