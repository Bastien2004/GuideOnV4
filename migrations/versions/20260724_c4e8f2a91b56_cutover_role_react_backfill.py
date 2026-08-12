"""cutover role react backfill

Revision ID: c4e8f2a91b56
Revises: 9f3a1c6e5d70
Create Date: 2026-07-24 19:50:00.000000

Phase 10 de la refonte multi-serveurs — backfill de cutover Rôle Réaction.

Copie l'état ACTUEL de alpha_role_react_configs -> ng_role_reactions et
alpha_role_react_entries -> ng_role_react_couples, tous deux estampillés
server='alpha'. Après son exécution, le code applicatif
(cogs/events/role_react_alpha.py, views/alpha/config_role_react_view.py)
lit et écrit exclusivement ng_role_reactions / ng_role_react_couples. Les
tables alpha_role_react_* ne sont NI renommées NI supprimées ici — elles
deviennent des tables mortes, conservées comme filet de sécurité jusqu'à
la phase de nettoyage finale (§12 du prompt).

ATTENTION FK CASCADE : contrairement aux backfills des phases 6-9,
ng_role_react_couples.server porte une vraie FK vers ng_role_reactions.server
(ON DELETE CASCADE). L'original alpha_role_react_entries n'avait AUCUNE
contrainte équivalente : une entrée pouvait exister sans ligne de config
correspondante (ex: un rôle ajouté avant qu'un salon soit configuré). Pour
ne perdre aucune donnée existante dans ce cas de figure, on garantit
d'abord qu'une ligne ng_role_reactions('alpha', NULL, NULL) existe dès lors
qu'au moins une entrée est à backfiller, AVANT d'insérer les couples.

`ON CONFLICT DO NOTHING` : idempotent en cas de rejeu.

ATTENTION ORDRE D'EXÉCUTION : cette révision suppose que ng_servers
contient déjà une ligne 'alpha' (phase 1).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers
revision: str = 'c4e8f2a91b56'
down_revision: Union[str, None] = '9f3a1c6e5d70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Config existante -> ng_role_reactions.
    op.execute("""
        INSERT INTO ng_role_reactions (server, channel_id, message_id, created_at, updated_at)
        SELECT 'alpha', channel_id, message_id, created_at, updated_at
        FROM alpha_role_react_configs
        ON CONFLICT (server) DO NOTHING
    """)

    # 2. Filet de sécurité : garantit la ligne parente si des entrées
    #    existent sans config correspondante (l'original n'avait pas de FK).
    op.execute("""
        INSERT INTO ng_role_reactions (server, channel_id, message_id)
        SELECT 'alpha', NULL, NULL
        WHERE EXISTS (SELECT 1 FROM alpha_role_react_entries)
        ON CONFLICT (server) DO NOTHING
    """)

    # 3. Entrées -> ng_role_react_couples (après coup, la FK est satisfaite).
    op.execute("""
        INSERT INTO ng_role_react_couples (
            server, position, role_id, label, emoji, description, created_at, updated_at
        )
        SELECT 'alpha', position, role_id, label, emoji, description, created_at, updated_at
        FROM alpha_role_react_entries
        ON CONFLICT (server, role_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM ng_role_react_couples WHERE server = 'alpha'")
    op.execute("DELETE FROM ng_role_reactions WHERE server = 'alpha'")
