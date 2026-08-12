"""cutover nota backfill

Revision ID: 7d4c8f3e2b91
Revises: 2b7f6e9d1a44
Create Date: 2026-07-24 19:25:00.000000

Phase 9 de la refonte multi-serveurs — backfill de cutover Notations.

Copie l'état ACTUEL des 4 tables alpha_nota_* -> ng_nota_*, toutes
estampillées server='alpha'. Après son exécution, le code applicatif
(cogs/events/notations_alpha.py, cogs/alpha/nota_debug.py,
cogs/alpha/nota_force.py, views/alpha/config_nota_view.py,
cogs/api/notation_api_app.py) lit et écrit exclusivement ng_nota_*. Les
tables alpha_nota_* ne sont NI renommées NI supprimées ici — elles
deviennent des tables mortes, conservées comme filet de sécurité jusqu'à
la phase de nettoyage finale (§12 du prompt).

`ON CONFLICT DO NOTHING` : idempotent en cas de rejeu.

ATTENTION ORDRE D'EXÉCUTION : cette révision suppose que ng_servers
contient déjà une ligne 'alpha' (phase 1).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers
revision: str = '7d4c8f3e2b91'
down_revision: Union[str, None] = '2b7f6e9d1a44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO ng_nota_configs (
            server, channel_staff_id, channel_public_id, channel_logs_id, role_id,
            countries_count,
            send_presence_weekday, send_presence_hour, send_presence_minute,
            deadline_weekday, deadline_hour, deadline_minute,
            send_public_weekday, send_public_hour, send_public_minute,
            url_country_lookup, enabled,
            created_at, updated_at
        )
        SELECT
            'alpha', channel_staff_id, channel_public_id, channel_logs_id, role_id,
            countries_count,
            send_presence_weekday, send_presence_hour, send_presence_minute,
            deadline_weekday, deadline_hour, deadline_minute,
            send_public_weekday, send_public_hour, send_public_minute,
            url_country_lookup, enabled,
            created_at, updated_at
        FROM alpha_nota_configs
        ON CONFLICT (server) DO NOTHING
    """)

    op.execute("""
        INSERT INTO ng_nota_week_states (
            server, availability_message_id, public_message_id,
            reminder_sent, assigned_ranges, created_at, updated_at
        )
        SELECT
            'alpha', availability_message_id, public_message_id,
            reminder_sent, assigned_ranges, created_at, updated_at
        FROM alpha_nota_week_states
        ON CONFLICT (server) DO NOTHING
    """)

    op.execute("""
        INSERT INTO ng_nota_availabilities (server, discord_id, created_at, updated_at)
        SELECT 'alpha', discord_id, created_at, updated_at
        FROM alpha_nota_availabilities
        ON CONFLICT (server, discord_id) DO NOTHING
    """)

    op.execute("""
        INSERT INTO ng_nota_history (
            server, discord_id, last_range_start, last_range_end, created_at, updated_at
        )
        SELECT 'alpha', discord_id, last_range_start, last_range_end, created_at, updated_at
        FROM alpha_nota_history
        ON CONFLICT (server, discord_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM ng_nota_history WHERE server = 'alpha'")
    op.execute("DELETE FROM ng_nota_availabilities WHERE server = 'alpha'")
    op.execute("DELETE FROM ng_nota_week_states WHERE server = 'alpha'")
    op.execute("DELETE FROM ng_nota_configs WHERE server = 'alpha'")
