"""Add automod tables (antifullcaps, antispam_mention, antispam_emoji)

Revision ID: 40955668fced
Revises: 9b3e7c1f4a20
Create Date: 2026-08-17
"""
from alembic import op
import sqlalchemy as sa

revision = '40955668fced'
down_revision = '9b3e7c1f4a20'
branch_labels = None
depends_on = None


def upgrade():
    # No-op: ces tables ont déjà été créées par cette révision
    # avant que le fichier ne soit perdu (conteneur recréé sans
    # que ce fichier ait été commit). On comble juste le trou
    # dans l'historique alembic pour ne pas casser la chaîne.
    pass


def downgrade():
    pass
