"""qr_codes : ajout de guild_id (cloisonnement par serveur)

Avant ce correctif, l'historique des QR codes (table qr_codes) n'avait
aucune notion de serveur Discord — un historique 100% global, alors que
GuideOn tourne sur de nombreux serveurs indépendants. Conséquences :
  - /qr scan pouvait révéler qu'un membre d'un AUTRE serveur, totalement
    étranger, avait généré un contenu identique.
  - /qr list permettait de consulter l'historique complet (tous serveurs
    confondus) de n'importe quel utilisateur Discord.

`guild_id` est ajoutée en NULLABLE : les lignes existantes n'ont aucun
moyen fiable d'être rattachées à un serveur a posteriori. Elles restent en
base (aucune perte de données, pas de backfill au hasard) mais ne
remontent plus jamais dans les requêtes applicatives, désormais toutes
filtrées par le guild_id courant.

Revision ID: c7e1a3f9b4d2
Revises: f4bd94e3609d
Create Date: 2026-10-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'c7e1a3f9b4d2'
down_revision: Union[str, None] = 'f4bd94e3609d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('qr_codes', sa.Column('guild_id', sa.BigInteger(), nullable=True))
    op.create_index('ix_qr_codes_guild_user', 'qr_codes', ['guild_id', 'user_id'], unique=False)
    op.create_index('ix_qr_codes_guild_contenu', 'qr_codes', ['guild_id', 'contenu'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_qr_codes_guild_contenu', table_name='qr_codes')
    op.drop_index('ix_qr_codes_guild_user', table_name='qr_codes')
    op.drop_column('qr_codes', 'guild_id')
