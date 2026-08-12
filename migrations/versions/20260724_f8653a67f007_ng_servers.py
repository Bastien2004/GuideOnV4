"""ng_servers

Revision ID: f8653a67f007
Revises: a4f5c9d21e08
Create Date: 2026-07-24 15:00:00.000000

Phase 1 de la refonte multi-serveurs (PROMPT_REFONTE_MULTISERVER.md §12).

Cree la table maitre ng_servers et seed la ligne 'alpha' avec le
guild_id Discord connu (settings.guild_alpha_id). La ligne 'delta' n'est
PAS seedee ici : son discord_guild_id reel n'est pas encore connu a la
redaction de cette revision, et discord_guild_id est UNIQUE — inserer un
placeholder serait dangereux (collision possible avec un futur ID reel).
Delta doit etre ajoute via l'interface site (source de verite sur cette
table, cf §11 du prompt) ou par une revision Alembic de suivi une fois
l'ID Discord de Delta connu.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'f8653a67f007'
down_revision: Union[str, None] = 'a4f5c9d21e08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Guild Discord Alpha — cf utils/settings.py Settings.guild_alpha_id
ALPHA_DISCORD_GUILD_ID = 1496765275670839306


def upgrade() -> None:
    op.create_table(
        'ng_servers',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=32), nullable=False),
        sa.Column('display_name', sa.String(length=64), nullable=False),
        sa.Column('edition', sa.String(length=16), nullable=False),
        sa.Column('discord_guild_id', sa.BigInteger(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('name', name='uq_ng_servers_name'),
        sa.UniqueConstraint('discord_guild_id', name='uq_ng_servers_discord_guild_id'),
    )

    op.execute(
        sa.text(
            "INSERT INTO ng_servers "
            "(name, display_name, edition, discord_guild_id, active, created_at, updated_at) "
            "VALUES ('alpha', 'Alpha', 'bedrock', :guild_id, true, now(), now())"
        ).bindparams(guild_id=ALPHA_DISCORD_GUILD_ID)
    )


def downgrade() -> None:
    op.drop_table('ng_servers')
