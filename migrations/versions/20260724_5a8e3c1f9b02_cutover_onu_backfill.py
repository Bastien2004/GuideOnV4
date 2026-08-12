"""cutover onu backfill

Revision ID: 5a8e3c1f9b02
Revises: c19a274bb2e0
Create Date: 2026-07-24 19:10:00.000000

Phase 8 de la refonte multi-serveurs — backfill de cutover ONU.

Copie l'état ACTUEL de alpha_onu_configs -> ng_onu_configs et
alpha_onu_ping_members -> ng_onu_ping_members, tous deux estampillés
server='alpha'. Après son exécution, le code applicatif (cogs/events/
onu_alpha.py, views/alpha/config_onu_view.py, cogs/api/api_app.py) lit et
écrit exclusivement ng_onu_configs / ng_onu_ping_members. Les tables
alpha_onu_configs / alpha_onu_ping_members ne sont NI renommées NI
supprimées ici — elles deviennent des tables mortes, conservées comme
filet de sécurité jusqu'à la phase de nettoyage finale (§12 du prompt).

`ON CONFLICT DO NOTHING` : idempotent en cas de rejeu.

ATTENTION ORDRE D'EXÉCUTION : cette révision suppose que ng_servers
contient déjà une ligne 'alpha' (phase 1).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers
revision: str = '5a8e3c1f9b02'
down_revision: Union[str, None] = 'c19a274bb2e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO ng_onu_configs (
            server, channel_id, role_id, jour_onu,
            pre_heure, pre_minute, ann_heure, ann_minute,
            timezone, ping_mp, image_name, join_url, enabled,
            created_at, updated_at
        )
        SELECT
            'alpha', channel_id, role_id, jour_onu,
            pre_heure, pre_minute, ann_heure, ann_minute,
            timezone, ping_mp, image_name, join_url, enabled,
            created_at, updated_at
        FROM alpha_onu_configs
        ON CONFLICT (server) DO NOTHING
    """)

    op.execute("""
        INSERT INTO ng_onu_ping_members (server, discord_id, created_at, updated_at)
        SELECT 'alpha', discord_id, created_at, updated_at
        FROM alpha_onu_ping_members
        ON CONFLICT (server, discord_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM ng_onu_ping_members WHERE server = 'alpha'")
    op.execute("DELETE FROM ng_onu_configs WHERE server = 'alpha'")
