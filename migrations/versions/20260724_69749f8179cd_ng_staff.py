"""ng staff

Revision ID: 69749f8179cd
Revises: d8d9b015e428
Create Date: 2026-07-24 18:00:00.000000

Phase 6 de la refonte multi-serveurs (PROMPT_REFONTE_MULTISERVER.md §12/§13).

ÉCART ASSUMÉ PAR RAPPORT AU DOCUMENT : le §12 (phases 4-10) décrit un
`rename_table('alpha_staff', 'ng_staff')` + ajout de colonne `server` +
bascule de PK, exécuté en une seule révision. Je ne fais PAS ça ici.

Pourquoi : `alpha_staff` est lue/écrite en direct par plusieurs commandes en
production (cogs/alpha/rank.py, derank.py, stafflist.py, edit_stafflist.py,
config_alpha.py, event_*.py, utils/managers/alpha_nota_manager.py). Un
rename_table cassé ces commandes immédiatement au moment où cette révision
est appliquée, puisqu'elles continuent d'interroger la table sous son
ancien nom via `utils.db.models.alpha_staff.AlphaStaffMember` — leur
migration vers `ng_staff` est explicitement la phase SUIVANTE (§13, phase 7 :
"Migration AlphaRankConfig + rank/derank + adaptation apply_staff_roles").
Renommer la table avant que ces call-sites soient prêts violerait le
principe directeur du prompt : "Ne rien casser en migrant" (§1).

À la place : `ng_staff` est créée VIDE, en parallèle. `alpha_staff` n'est ni
renommée ni modifiée. Le peuplement se fait à la demande via
`utils.managers.ng_staff_manager.resync_server_from_alpha_staff()`
(idempotent, ré-exécutable) plutôt que par un INSERT...SELECT figé dans
cette révision — un backfill fait maintenant serait déjà périmé au moment
du cutover réel en phase 7 (alpha_staff continue de changer entre-temps).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '69749f8179cd'
down_revision: Union[str, None] = 'd8d9b015e428'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ng_staff',
        sa.Column('server', sa.String(length=32), nullable=False),
        sa.Column('discord_id', sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column('pseudo_jeu', sa.String(length=64), nullable=False),
        sa.Column('grade', sa.String(length=32), nullable=True),
        sa.Column('skin_head_emoji', sa.String(length=128), nullable=False, server_default=''),
        sa.Column('is_journaliste', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_affilie', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_builder', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('pseudo_jeu_builder', sa.String(length=64), nullable=True),
        sa.Column('blames', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['server'], ['ng_servers.name'], name='fk_ng_staff_server'),
        sa.PrimaryKeyConstraint('server', 'discord_id', name='pk_ng_staff'),
    )
    op.create_index('ix_ng_staff_server_grade', 'ng_staff', ['server', 'grade'])


def downgrade() -> None:
    op.drop_index('ix_ng_staff_server_grade', table_name='ng_staff')
    op.drop_table('ng_staff')
