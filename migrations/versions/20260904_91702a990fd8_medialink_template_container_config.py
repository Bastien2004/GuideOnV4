"""MEDIALINK: rename media_templates.embed_config to container_config

Revision ID: 91702a990fd8
Revises: 3557ccbcee08
Create Date: 2026-09-04 00:00:00.000000

Le bot n'utilise plus discord.Embed pour les annonces MEDIALINK mais les
Components V2 (Container/Section/Thumbnail/TextDisplay), cf. utils/
medialink/builders/announcement.py et views/medialink/
medialink_announcement_view.py. La colonne s'appelait "embed_config"
depuis le squelette initial (structure volontairement laissée ouverte,
"à valider avec Paul" — cf. docstring d'origine de
utils/db/models/medialink_template.py) ; on la renomme maintenant que la
structure réelle (accent_color/title/description/thumbnail_enabled, un
Container Components V2, pas un embed) est fixée, pour ne pas garder un
nom de colonne qui décrirait la mauvaise chose.

Simple renommage de colonne, aucune donnée perdue — le JSON existant
(actuellement toujours NULL en pratique, aucun template n'a encore de
mise en forme structurée) est conservé tel quel sous le nouveau nom.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers
revision: str = '91702a990fd8'
down_revision: Union[str, None] = '3557ccbcee08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('media_templates', 'embed_config', new_column_name='container_config')


def downgrade() -> None:
    op.alter_column('media_templates', 'container_config', new_column_name='embed_config')