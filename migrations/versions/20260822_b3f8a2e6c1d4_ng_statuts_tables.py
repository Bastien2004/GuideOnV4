"""NG statuts: per-server definable secondary statuses (replaces fixed journaliste/affilie/builder)

Revision ID: b3f8a2e6c1d4
Revises: a2c7e4f19b6d
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'b3f8a2e6c1d4'
down_revision: Union[str, None] = 'a2c7e4f19b6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (key, label, emoji, colonne rôle sur ng_rank_configs, pseudo secondaire requis)
_LEGACY_STATUTS = [
    ("journaliste", "Journaliste", "📰", "role_journaliste_id", False),
    ("affilie",     "Affilié",     "🎥", "role_affilie_id",     False),
    ("builder",     "Builder",     None, "role_builder_id",     True),
]


def upgrade() -> None:
    op.create_table(
        'ng_statut_defs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('server', sa.String(length=32), nullable=False),
        sa.Column('key', sa.String(length=32), nullable=False),
        sa.Column('label', sa.String(length=64), nullable=False),
        sa.Column('emoji', sa.String(length=100), nullable=True),
        sa.Column('role_id', sa.BigInteger(), nullable=True),
        sa.Column('requires_second_pseudo', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['server'], ['ng_servers.name']),
        sa.UniqueConstraint('server', 'key', name='uq_ng_statut_def_server_key'),
    )

    op.create_table(
        'ng_staff_statuts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('server', sa.String(length=32), nullable=False),
        sa.Column('discord_id', sa.BigInteger(), nullable=False),
        sa.Column('statut_def_id', sa.BigInteger(), nullable=False),
        sa.Column('second_pseudo', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['server'], ['ng_servers.name']),
        sa.ForeignKeyConstraint(['statut_def_id'], ['ng_statut_defs.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('discord_id', 'statut_def_id', name='uq_ng_staff_statut_member_def'),
    )

    conn = op.get_bind()

    rank_configs = conn.execute(sa.text(
        "SELECT server, role_journaliste_id, role_affilie_id, role_builder_id FROM ng_rank_configs"
    )).mappings().all()

    for cfg_row in rank_configs:
        server = cfg_row["server"]
        for position, (key, label, emoji, role_col, requires_pseudo) in enumerate(_LEGACY_STATUTS):
            role_id = cfg_row[role_col]

            has_members = conn.execute(sa.text(
                f"SELECT 1 FROM ng_staff WHERE server = :server AND is_{key} = true LIMIT 1"
            ), {"server": server}).first()

            # Rien à migrer pour ce statut sur ce serveur : ni rôle configuré,
            # ni membre l'ayant déjà — on ne pollue pas avec une définition vide.
            if role_id is None and not has_members:
                continue

            statut_def_id = conn.execute(sa.text(
                "INSERT INTO ng_statut_defs "
                "(server, key, label, emoji, role_id, requires_second_pseudo, position, created_at, updated_at) "
                "VALUES (:server, :key, :label, :emoji, :role_id, :requires_pseudo, :position, now(), now()) "
                "RETURNING id"
            ), {
                "server": server, "key": key, "label": label, "emoji": emoji,
                "role_id": role_id, "requires_pseudo": requires_pseudo, "position": position,
            }).scalar_one()

            members = conn.execute(sa.text(
                f"SELECT discord_id, pseudo_jeu_builder FROM ng_staff "
                f"WHERE server = :server AND is_{key} = true"
            ), {"server": server}).mappings().all()

            for m in members:
                second_pseudo = m["pseudo_jeu_builder"] if key == "builder" else None
                conn.execute(sa.text(
                    "INSERT INTO ng_staff_statuts "
                    "(server, discord_id, statut_def_id, second_pseudo, created_at, updated_at) "
                    "VALUES (:server, :discord_id, :statut_def_id, :second_pseudo, now(), now())"
                ), {
                    "server": server, "discord_id": m["discord_id"],
                    "statut_def_id": statut_def_id, "second_pseudo": second_pseudo,
                })


def downgrade() -> None:
    op.drop_table('ng_staff_statuts')
    op.drop_table('ng_statut_defs')