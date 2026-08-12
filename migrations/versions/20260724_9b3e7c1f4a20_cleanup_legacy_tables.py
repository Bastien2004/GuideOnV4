"""cleanup legacy tables

Revision ID: 9b3e7c1f4a20
Revises: c4e8f2a91b56
Create Date: 2026-07-24 21:00:00.000000

Phase 15 (finale) de la refonte multi-serveurs (PROMPT_REFONTE_MULTISERVER.md
§12/§13 : "Nettoyage legacy — Suppression alpha_* obsolètes, ancien
perm_alpha, PermissionRole enum").

*** NE PAS FUSIONNER NI APPLIQUER SANS Y AVOIR REFLECHI. ***

Cette révision est IRREVERSIBLE en pratique : le downgrade() ci-dessous
recrée le SCHEMA (colonnes, contraintes, index) tel qu'il existait au
moment de la suppression, mais AUCUNE DONNEE n'est restaurée. Une fois
upgrade() exécuté en prod, les données historiques de ces 11 tables sont
perdues sauf à restaurer depuis un backup complet de la base.

IMPORTANT — comportement Alembic : ce fichier est chaîné à la suite de la
révision actuellement en tête (c4e8f2a91b56). Une fois ce fichier présent
dans le dépôt, un simple `alembic upgrade head` l'exécutera AUTOMATIQUEMENT
avec toute autre révision en attente — il n'existe pas de mécanisme
"présent mais inerte" côté Alembic. Concrètement :
  - Ne PAS fusionner ce fichier dans la branche principale tant que tu
    n'es pas prêt à l'exécuter.
  - Le jour où tu es prêt : BACKUP COMPLET de `guideon` d'abord, puis
    `alembic upgrade head` (ou cible cette révision précisément :
    `alembic upgrade 9b3e7c1f4a20`).
  - Si tu veux le garder en réserve sans risque : laisse-le hors du
    dépôt principal (branche séparée, ou simplement ne pas copier ce
    fichier dans migrations/versions/ tout de suite) jusqu'au moment
    choisi.

Tables supprimées (11) — toutes gelées depuis leur bascule respective vers
un système `ng_*` ou RBAC, plus aucun code vivant ne les lit ni ne les
écrit (vérifié par grep exhaustif avant cette révision, voir PHASE_15.md) :

    alpha_staff                 (gelée phase 6 -> ng_staff)
    alpha_rank_configs          (gelée phase 7 -> ng_rank_configs)
    alpha_onu_configs           (gelée phase 8 -> ng_onu_configs)
    alpha_onu_ping_members      (gelée phase 8 -> ng_onu_configs/pings)
    alpha_nota_configs          (gelée phase 9 -> ng_nota_configs)
    alpha_nota_week_states      (gelée phase 9 -> ng_nota_week_states)
    alpha_nota_availabilities   (gelée phase 9 -> ng_nota_availabilities)
    alpha_nota_history          (gelée phase 9 -> ng_nota_history)
    alpha_role_react_configs    (gelée phase 10 -> ng_role_reactions)
    alpha_role_react_entries    (gelée phase 10 -> ng_role_reactions)
    permission_entries          (gelée phase 4 -> permission_grade_members,
                                  RBAC ; lue en dernier par utils/perm_alpha.py
                                  /perm_dev.py/perm_staff.py jusqu'à leur
                                  rewire RBAC dans cette même phase 15)

Tables volontairement NON incluses (toujours vivantes, ne pas supprimer) :
    alpha_message_configs  — persistance des messages index/regle_interne/
                              nous_rejoindre/stafflist, guild_id-keyed,
                              déjà multi-serveurs par nature (phase 13)
    alpha_event_configs    — config du système events, permanent
                              Alpha-only par design (phase 13)

Schéma de recréation (downgrade) reconstruit à partir des modèles ORM
finaux tels qu'ils existaient juste avant leur suppression dans cette
phase (utils/db/models/alpha_staff.py, alpha_rank_config.py,
alpha_onu_config.py, alpha_nota_config.py, alpha_role_react.py — retirés
du dépôt dans cette même révision de code, donc reconstruits ici de
mémoire/historique plutôt que ré-importés). Vérifié colonne par colonne
contre les migrations de création d'origine quand elles étaient
disponibles (alpha_rank_configs+alpha_staff : 8cd35551df76 ; alpha_onu_* :
341b2bf6608e ; alpha_nota_* : 9194c5a46fa7 ; alpha_role_react_* :
f7e3f444cd77 ; permission_entries : cbdc98acbeb3) — colonnes ajoutées
après création (is_journaliste/is_affilie/is_builder/pseudo_jeu_builder/
blames sur alpha_staff ; content_*/role_affilie_id/role_builder_id/
role_equipe_id/rank_emoji sur alpha_rank_configs) reprises depuis le
modèle final, PAS depuis la migration de création d'origine.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '9b3e7c1f4a20'
down_revision: Union[str, None] = 'c4e8f2a91b56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── permission_entries ──────────────────────────────────────────────
    op.drop_index('ix_permission_role_discord', table_name='permission_entries')
    op.drop_index('ix_permission_entries_role', table_name='permission_entries')
    op.drop_table('permission_entries')

    # ── alpha_role_react_* ───────────────────────────────────────────────
    op.drop_index('ix_role_react_guild', table_name='alpha_role_react_entries')
    op.drop_table('alpha_role_react_entries')
    op.drop_table('alpha_role_react_configs')

    # ── alpha_nota_* ─────────────────────────────────────────────────────
    op.drop_table('alpha_nota_week_states')
    op.drop_table('alpha_nota_history')
    op.drop_table('alpha_nota_configs')
    op.drop_index('ix_nota_avail_guild', table_name='alpha_nota_availabilities')
    op.drop_table('alpha_nota_availabilities')

    # ── alpha_onu_* ──────────────────────────────────────────────────────
    op.drop_index('ix_onu_ping_guild', table_name='alpha_onu_ping_members')
    op.drop_table('alpha_onu_ping_members')
    op.drop_table('alpha_onu_configs')

    # ── alpha_staff / alpha_rank_configs ────────────────────────────────
    op.drop_index('ix_alpha_staff_grade', table_name='alpha_staff')
    op.drop_table('alpha_staff')
    op.drop_table('alpha_rank_configs')


def downgrade() -> None:
    # ATTENTION : recrée le schéma uniquement. Aucune donnée n'est
    # restaurée — voir docstring de ce module. Un downgrade() après un
    # upgrade() déjà appliqué en prod donne des tables vides, pas l'état
    # d'avant.

    # ── alpha_rank_configs / alpha_staff (schéma final, post-ajouts) ────
    op.create_table('alpha_rank_configs',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('rank_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('journaliste_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('dev_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('journaliste_ping_id', sa.BigInteger(), nullable=True),
        sa.Column('dev_ping_id', sa.BigInteger(), nullable=True),
        sa.Column('role_journaliste_id', sa.BigInteger(), nullable=True),
        sa.Column('role_guide_id', sa.BigInteger(), nullable=True),
        sa.Column('role_moderateur_test_id', sa.BigInteger(), nullable=True),
        sa.Column('role_moderateur_confirme_id', sa.BigInteger(), nullable=True),
        sa.Column('role_moderateur_plus_id', sa.BigInteger(), nullable=True),
        sa.Column('role_super_moderateur_id', sa.BigInteger(), nullable=True),
        sa.Column('role_administrateur_id', sa.BigInteger(), nullable=True),
        sa.Column('role_affilie_id', sa.BigInteger(), nullable=True),
        sa.Column('role_builder_id', sa.BigInteger(), nullable=True),
        sa.Column('role_equipe_id', sa.BigInteger(), nullable=True),
        sa.Column('content_nous_rejoindre_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('content_nous_rejoindre_ping_id', sa.BigInteger(), nullable=True),
        sa.Column('content_nous_rejoindre_emoji', sa.String(length=100), nullable=True),
        sa.Column('content_index_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('content_index_emoji', sa.String(length=100), nullable=True),
        sa.Column('content_regle_interne_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('content_regle_interne_emoji', sa.String(length=100), nullable=True),
        sa.Column('content_stafflist_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('rank_emoji', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('guild_id'),
    )
    op.create_table('alpha_staff',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('discord_id', sa.BigInteger(), nullable=False),
        sa.Column('pseudo_jeu', sa.String(length=64), nullable=False),
        sa.Column('grade', sa.String(length=32), nullable=True),
        sa.Column('skin_head_emoji', sa.String(length=128), nullable=False, server_default=''),
        sa.Column('is_journaliste', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_affilie', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_builder', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('pseudo_jeu_builder', sa.String(length=64), nullable=True),
        sa.Column('blames', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('discord_id'),
    )
    op.create_index('ix_alpha_staff_grade', 'alpha_staff', ['grade'], unique=False)

    # ── alpha_onu_* ──────────────────────────────────────────────────────
    op.create_table('alpha_onu_configs',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('channel_id', sa.BigInteger(), nullable=True),
        sa.Column('role_id', sa.BigInteger(), nullable=True),
        sa.Column('jour_onu', sa.Integer(), nullable=True),
        sa.Column('pre_heure', sa.Integer(), nullable=True),
        sa.Column('pre_minute', sa.Integer(), nullable=True),
        sa.Column('ann_heure', sa.Integer(), nullable=True),
        sa.Column('ann_minute', sa.Integer(), nullable=True),
        sa.Column('timezone', sa.String(length=50), server_default='Europe/Paris', nullable=False),
        sa.Column('ping_mp', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('image_name', sa.String(length=100), nullable=True),
        sa.Column('join_url', sa.String(length=300), nullable=True),
        sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('guild_id'),
    )
    op.create_table('alpha_onu_ping_members',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('discord_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guild_id', 'discord_id', name='uq_onu_ping_member'),
    )
    op.create_index('ix_onu_ping_guild', 'alpha_onu_ping_members', ['guild_id'], unique=False)

    # ── alpha_nota_* ─────────────────────────────────────────────────────
    op.create_table('alpha_nota_availabilities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('discord_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guild_id', 'discord_id', name='uq_nota_availability'),
    )
    op.create_index('ix_nota_avail_guild', 'alpha_nota_availabilities', ['guild_id'], unique=False)
    op.create_table('alpha_nota_configs',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('channel_staff_id', sa.BigInteger(), nullable=True),
        sa.Column('channel_public_id', sa.BigInteger(), nullable=True),
        sa.Column('channel_logs_id', sa.BigInteger(), nullable=True),
        sa.Column('role_id', sa.BigInteger(), nullable=True),
        sa.Column('countries_count', sa.Integer(), server_default='238', nullable=False),
        sa.Column('send_presence_weekday', sa.Integer(), nullable=True),
        sa.Column('send_presence_hour', sa.Integer(), nullable=True),
        sa.Column('send_presence_minute', sa.Integer(), nullable=True),
        sa.Column('deadline_weekday', sa.Integer(), nullable=True),
        sa.Column('deadline_hour', sa.Integer(), nullable=True),
        sa.Column('deadline_minute', sa.Integer(), nullable=True),
        sa.Column('send_public_weekday', sa.Integer(), nullable=True),
        sa.Column('send_public_hour', sa.Integer(), nullable=True),
        sa.Column('send_public_minute', sa.Integer(), nullable=True),
        sa.Column('url_country_lookup', sa.String(length=300), nullable=True),
        sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('guild_id'),
    )
    op.create_table('alpha_nota_history',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('discord_id', sa.BigInteger(), nullable=False),
        sa.Column('last_range_start', sa.Integer(), nullable=True),
        sa.Column('last_range_end', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('guild_id', 'discord_id'),
    )
    op.create_table('alpha_nota_week_states',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('availability_message_id', sa.BigInteger(), nullable=True),
        sa.Column('public_message_id', sa.BigInteger(), nullable=True),
        sa.Column('reminder_sent', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('assigned_ranges', sa.Text(), server_default='[]', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('guild_id'),
    )

    # ── alpha_role_react_* ───────────────────────────────────────────────
    op.create_table('alpha_role_react_configs',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('channel_id', sa.BigInteger(), nullable=True),
        sa.Column('message_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('guild_id'),
    )
    op.create_table('alpha_role_react_entries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.BigInteger(), nullable=False),
        sa.Column('label', sa.String(length=80), nullable=False),
        sa.Column('emoji', sa.String(length=100), nullable=True),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guild_id', 'position', name='uq_role_react_pos'),
        sa.UniqueConstraint('guild_id', 'role_id', name='uq_role_react_role'),
    )
    op.create_index('ix_role_react_guild', 'alpha_role_react_entries', ['guild_id'], unique=False)

    # ── permission_entries ──────────────────────────────────────────────
    op.create_table('permission_entries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            'role',
            sa.Enum('DEV', 'STAFF_GUIDEON', 'OP_ALPHA', 'MODO_PLUS_ALPHA', 'MODO_ALPHA',
                    name='permission_role', native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column('discord_id', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role', 'discord_id', name='uq_permission_role_discord_id'),
    )
    op.create_index('ix_permission_entries_role', 'permission_entries', ['role'], unique=False)
    op.create_index('ix_permission_role_discord', 'permission_entries', ['role', 'discord_id'], unique=False)
