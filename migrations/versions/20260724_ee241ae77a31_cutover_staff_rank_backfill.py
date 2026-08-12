"""cutover staff rank backfill

Revision ID: ee241ae77a31
Revises: 01b6d63bd279
Create Date: 2026-07-24 19:05:00.000000

Phase 7 de la refonte multi-serveurs — backfill de cutover.

Copie l'état ACTUEL de alpha_staff -> ng_staff et alpha_rank_configs ->
ng_rank_configs, tous deux estampillés server='alpha'. Contrairement au
resync de la phase 6 (pensé comme répétable, pour préparer le terrain sans
casser l'existant), cette révision est le vrai backfill de cutover : après
son exécution, le code applicatif (rank.py, derank.py, stafflist.py,
edit_stafflist.py, config_alpha, staff_api, ...) lit et écrit exclusivement
ng_staff / ng_rank_configs. alpha_staff et alpha_rank_configs ne sont NI
renommées NI supprimées ici — elles deviennent des tables mortes (plus
aucune écriture applicative après cette révision), conservées comme filet
de sécurité jusqu'à la phase de nettoyage finale (§12 du prompt).

`ON CONFLICT DO NOTHING` : idempotent si un resync manuel (phase 6) a déjà
peuplé tout ou partie de ng_staff avant que cette révision tourne.

ATTENTION ORDRE D'EXÉCUTION : cette révision suppose que ng_servers
contient déjà une ligne 'alpha' (phase 1) — sinon la contrainte FK
`ng_staff.server -> ng_servers.name` / `ng_rank_configs.server ->
ng_servers.name` fait échouer les INSERT.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers
revision: str = 'ee241ae77a31'
down_revision: Union[str, None] = '01b6d63bd279'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO ng_staff (
            server, discord_id, pseudo_jeu, grade, skin_head_emoji,
            is_journaliste, is_affilie, is_builder, pseudo_jeu_builder, blames,
            created_at, updated_at
        )
        SELECT
            'alpha', discord_id, pseudo_jeu, grade, skin_head_emoji,
            is_journaliste, is_affilie, is_builder, pseudo_jeu_builder, blames,
            created_at, updated_at
        FROM alpha_staff
        ON CONFLICT (server, discord_id) DO NOTHING
    """)

    op.execute("""
        INSERT INTO ng_rank_configs (
            server, rank_channel_id, journaliste_channel_id, dev_channel_id,
            journaliste_ping_id, dev_ping_id,
            role_journaliste_id, role_guide_id, role_moderateur_test_id,
            role_moderateur_confirme_id, role_moderateur_plus_id,
            role_super_moderateur_id, role_administrateur_id,
            role_affilie_id, role_builder_id, role_equipe_id,
            content_nous_rejoindre_channel_id, content_nous_rejoindre_ping_id,
            content_nous_rejoindre_emoji, content_index_channel_id, content_index_emoji,
            content_regle_interne_channel_id, content_regle_interne_emoji,
            content_stafflist_channel_id, rank_emoji,
            created_at, updated_at
        )
        SELECT
            'alpha', rank_channel_id, journaliste_channel_id, dev_channel_id,
            journaliste_ping_id, dev_ping_id,
            role_journaliste_id, role_guide_id, role_moderateur_test_id,
            role_moderateur_confirme_id, role_moderateur_plus_id,
            role_super_moderateur_id, role_administrateur_id,
            role_affilie_id, role_builder_id, role_equipe_id,
            content_nous_rejoindre_channel_id, content_nous_rejoindre_ping_id,
            content_nous_rejoindre_emoji, content_index_channel_id, content_index_emoji,
            content_regle_interne_channel_id, content_regle_interne_emoji,
            content_stafflist_channel_id, rank_emoji,
            created_at, updated_at
        FROM alpha_rank_configs
        ON CONFLICT (server) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM ng_rank_configs WHERE server = 'alpha'")
    op.execute("DELETE FROM ng_staff WHERE server = 'alpha'")
