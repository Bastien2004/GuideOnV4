"""
Point d'entrée GuideON V4.

Lancement: python bot.py
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

import discord
from discord.ext import commands

from utils.settings import settings
from utils.logging_config import setup_logging
from cogs.api.api_app import run_api_server

from utils.managers.boutique_manager import refresh_cache, cache_refresher_loop
from utils.managers.permission_manager import refresh_cache as refresh_perms, cache_refresher_loop as perms_refresher_loop

from utils.groupes import groupeDEV, groupeCONFIG, groupeNG, groupeTICKET, groupeINV, groupeBIRTHDAY, groupeGIVE, groupeALPHA


log = logging.getLogger(__name__)


def _mask_db_url(url: str) -> str:
    """Masque le mot de passe dans une URL de DB avant de la logger."""

    return re.sub(r"(://[^:/?#]+:)([^@]+)(@)", r"\1***\3", url)


def build_intents() -> discord.Intents:
    """Gestion des intents."""

    intents = discord.Intents.none()
    intents.guilds = True
    intents.members = True
    intents.messages = True
    intents.message_content = True
    intents.reactions = True
    intents.voice_states = True
    intents.invites = True
    intents.emojis_and_stickers = True
    return intents


class GuideONBot(commands.Bot):
    """Classe principale du bot."""

    def __init__(self) -> None:
        super().__init__(
            command_prefix="$",
            intents=build_intents(),
            help_command=None,
        )

    async def setup_hook(self) -> None:
        setup_logging()
        log.info("Démarrage du bot GuideOn")

        # ── DB ──
        from utils.db.engine import init_db
        try:
            await init_db()
        except Exception:
            log.critical(
                "Impossible de se connecter à la base de données.\n"
                "  → Vérifie que PostgreSQL est démarré et que DATABASE_URL est correct.\n"
                "  → DATABASE_URL actuel pointe vers : %s\n"
                "  → Pour un Postgres local : docker run --name guideon-pg "
                "-e POSTGRES_PASSWORD=guideon -e POSTGRES_USER=guideon "
                "-e POSTGRES_DB=guideon -p 5432:5432 -d postgres:16\n"
                "  → Ou bascule sur SQLite dans .env : "
                "DATABASE_URL=sqlite+aiosqlite:///./guideon_dev.db",
                _mask_db_url(settings.database_url),
            )
            raise

        # ── Boutique ──
        await refresh_cache()
        asyncio.create_task(cache_refresher_loop())

        # ── Permissions internes ──
        await refresh_perms()
        asyncio.create_task(perms_refresher_loop())

        # ── Chargement commandes simples  ──
        await self._load_cogs_from_directory("cogs")

        # ── Chargement commandes groupes ──
        await self._register_command_groups()

        # ── Réenregistrement des vues persistantes tickets ──
        from views.ticket.persistence import register_persistent_views
        await register_persistent_views(self)

        await self._sync_commands()

        # ── API FastAPI ──
        run_api_server()

        log.info("setup_hook terminé")

    # ------------------------------------------------------------------
    # 👥 Groupes de commandes
    # ------------------------------------------------------------------
    async def _register_command_groups(self) -> None:
        """Assemble les groupes de commandes."""

        ### IMPORT DES COMMANDES DE GROUPES ###

        # ── IMPORT CONFIG ──
        from cogs.config.bienvenue import bienvenue
        from cogs.config.autorole import autorole
        from cogs.config.role_all import role_all
        from cogs.config.role_react import role_reaction

        # ── IMPORT TICKET ──
        from cogs.ticket.ticket_panel_create import ticket_panel_create
        from cogs.ticket.ticket_panel_edit import ticket_panel_edit
        from cogs.ticket.ticket_panel_delete import ticket_panel_delete
        from cogs.ticket.ticket_panel_list import ticket_panel_list

        from cogs.ticket.ticket_add import ticket_add
        from cogs.ticket.ticket_ban import ticket_ban
        from cogs.ticket.ticket_close import ticket_close
        from cogs.ticket.ticket_delete import ticket_delete
        from cogs.ticket.ticket_remove import ticket_remove
        from cogs.ticket.ticket_rename import ticket_rename
        from cogs.ticket.ticket_unban import ticket_unban
        from cogs.ticket.ticket_wakeup import ticket_wakeup

        # ── IMPORT DEV ──
        from cogs.dev.maintenance import maintenance
        from cogs.dev.permission import permissions
        from cogs.dev.delete_message import delete_message
        from cogs.dev.kick import kick
        from cogs.dev.stat_server import stat_server
        from cogs.dev.stat_cmd import stat_cmd
        from cogs.dev.join_serv import join_serv

        # ── IMPORT NG ──
        from cogs.ng.autel import autel
        from cogs.ng.claim import claim
        from cogs.ng.classement import ng_classement
        from cogs.ng.convert import convert
        from cogs.ng.country import country
        from cogs.ng.dynmaps import dynmaps
        from cogs.ng.info import ng_info
        from cogs.ng.lvl import lvl
        from cogs.ng.mmr import mmr
        from cogs.ng.ngprofil import ngprofil
        from cogs.ng.ngversion import version
        from cogs.ng.onu import onu
        from cogs.ng.pillage import pillage
        from cogs.ng.rd import rd
        from cogs.ng.sanction import sanction
        from cogs.ng.serveur_stat import serveur_stat
        from cogs.ng.skin import skin

        # ── IMPORT INVITE ──
        from cogs.invite.invite_config import invite_config
        from cogs.invite.invite_classement import invite_classement
        from cogs.invite.invite_gestion import invite_gestion
        from cogs.invite.invite_user import invite_user

        # ── IMPORT BIRTHDAY ──
        from cogs.birthday.birthday_config import birthday_config
        from cogs.birthday.birthday_next import birthday_next
        from cogs.birthday.birthday_list import birthday_list
        from cogs.birthday.birthday_add import birthday_add

        # ── IMPORT GIVEAWAY ──
        from cogs.giveaway.giveaway_blacklist import giveaway_blacklist
        from cogs.giveaway.giveaway_create import giveaway_create
        from cogs.giveaway.giveaway_list import giveaway_list
        from cogs.giveaway.giveaway_manage import giveaway_manage
                
        # ── IMPORT MOD ──
        # from cogs.mod.exemple import ...
        
        # ── IMPORT EXP ──
        # from cogs.exp.exemple import ...
        
        # ── IMPORT ALPHA ──
        from cogs.alpha.test import test_alpha
        from cogs.alpha.regle_interne import regle_interne
        from cogs.alpha.nous_rejoindre import nous_rejoindre
        from cogs.alpha.index import index
        from cogs.alpha.stafflist import stafflist
        from cogs.alpha.rank import rank
        from cogs.alpha.derank import alpha_derank
        from cogs.alpha.event_list import event_list
        from cogs.alpha.event_regle import event_regle
        from cogs.alpha.event_start import event_start
        from cogs.alpha.config_alpha import config_alpha
        from cogs.alpha.edit_stafflist import alpha_edit_stafflist
        from cogs.alpha.nota_force import nota_force
        from cogs.alpha.nota_debug import nota_debug

        ### ASSEMBLAGE DES GROUPES DE COMMANDES ###

         # 🔩 ── CONFIG ──
        groupCONFIG = groupeCONFIG()
        for cmd in [bienvenue, autorole, role_all, role_reaction]:
            groupCONFIG.add_command(cmd)

        
         # 🎟️ ── TICKET ──
        groupTICKET = groupeTICKET()
        for cmd in [ticket_panel_create, ticket_panel_edit, ticket_panel_delete, ticket_panel_list, ticket_add, ticket_ban,
                    ticket_close, ticket_delete, ticket_remove, ticket_rename, ticket_unban, ticket_wakeup]:
            groupTICKET.add_command(cmd)


        # 🎁 ── BIRTHDAY ──
        groupBIRTHDAY = groupeBIRTHDAY()
        for cmd in [birthday_config, birthday_next, birthday_list, birthday_add]:
            groupBIRTHDAY.add_command(cmd)


        # 💻 ── DEV ──
        self._groupDEV = groupeDEV()
        for cmd in [maintenance, permissions, delete_message, kick, stat_server, stat_cmd, join_serv]:
            self._groupDEV.add_command(cmd)

        
        # 🌐 ── NG ──
        groupNG = groupeNG()
        for cmd in [autel, claim, ng_classement, convert, country, dynmaps, ng_info, lvl, mmr, ngprofil, version, onu, pillage, rd,
                    sanction, serveur_stat, skin]:
            groupNG.add_command(cmd)


        # 📧 ── INVITE ──
        groupINV = groupeINV()
        for cmd in [invite_config, invite_classement, invite_gestion, invite_user]:
            groupINV.add_command(cmd)

        # 🎁 ── GIVEAWAY ──
        groupGIVE = groupeGIVE()
        for cmd in [giveaway_blacklist, giveaway_create, giveaway_list, giveaway_manage]:
            groupGIVE.add_command(cmd)

        '''
        # 🛡️ ── MOD ──
        groupMOD = groupeMOD()
        for cmd in []:
            groupMOD.add_command(cmd)

        # 🧩 ── EXP ──
        groupEXP = groupeEXP()
        for cmd in []:
            groupEXP.add_command(cmd)
        '''

        # 💋 ── ALPHA ──
        self._groupALPHA = groupeALPHA()
        for cmd in [test_alpha, regle_interne, nous_rejoindre, index,
                    stafflist, rank, alpha_derank, event_start, event_regle, event_list, config_alpha,
                    alpha_edit_stafflist, nota_debug, nota_force]:
            
            self._groupALPHA.add_command(cmd)

        for group in [groupCONFIG, groupNG, groupTICKET, groupINV, groupBIRTHDAY, groupGIVE]:
            self.tree.add_command(group)

        log.info("✅ Groupes de commandes enregistrés.")


    async def _sync_commands(self):

        # -----------------------------
        # SYNC GLOBALE
        # -----------------------------
        try:
            synced = await self.tree.sync()
            log.info(f"🌍 {len(synced)} commandes globales synchronisées.")
        except Exception as e:
            log.error(f"❌ Erreur sync globale : {e}")

        # -----------------------------
        # ALPHA
        # -----------------------------
        ALPHA_GUILDS = [
            751903718135431188,
            1411296579528294402,
        ]

        for gid in ALPHA_GUILDS:
            guild = discord.Object(id=gid)

            try:
                try:
                    self.tree.add_command(self._groupALPHA, guild=guild)
                except discord.app_commands.CommandAlreadyRegistered:
                    pass

                synced = await self.tree.sync(guild=guild)

                log.info(
                    f"💋 Commandes ALPHA synchronisées sur {gid} ({len(synced)} cmd)"
                )

            except Exception as e:
                log.error(f"❌ Erreur ALPHA {gid}: {e}")

        # -----------------------------
        # DEV
        # -----------------------------
        DEV_GUILDS = [
            1400451664946794618,
            1411296579528294402,
        ]

        for gid in DEV_GUILDS:
            guild = discord.Object(id=gid)

            try:
                try:
                    self.tree.add_command(self._groupDEV, guild=guild)
                except discord.app_commands.CommandAlreadyRegistered:
                    pass

                synced = await self.tree.sync(guild=guild)

                log.info(
                    f"💻 Commandes DEV synchronisées sur {gid} ({len(synced)} cmd)"
                )

            except Exception as e:
                log.error(f"❌ Erreur DEV {gid}: {e}")

        # -----------------------------
        # SUPPORT
        # -----------------------------
        SUPPORT_GUILDS = [
            1184114738813227059,
        ]

        for gid in SUPPORT_GUILDS:
            guild = discord.Object(id=gid)

            try:
                synced = await self.tree.sync(guild=guild)

                log.info(
                    f"🛠️ Commandes SUPPORT synchronisées sur {gid} ({len(synced)} cmd)"
                )

            except Exception as e:
                log.error(f"❌ Erreur SUPPORT {gid}: {e}")



    async def on_ready(self) -> None:
        if not hasattr(self, "_ready_done"):
            self._ready_done = True

            await self._set_guild_avatars()

        log.info("Connecté en tant que %s (%s)", self.user, self.user.id if self.user else "?")
        log.info("%d serveurs connectés", len(self.guilds))

        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="GuideON V4"),
        )



    ### GUILD AVATARS ###
    async def _set_guild_avatars(self):
        GUILD_AVATARS = {
            751903718135431188 : "source/GuideON Staff.webp",
        }

        for guild_id, avatar_path in GUILD_AVATARS.items():
            guild = self.get_guild(guild_id)
            if not guild:
                log.warning(f"⚠️ [GUILD AVATAR] Serveur {guild_id} introuvable.")
                continue
            try:
                with open(avatar_path, "rb") as f:
                    image_data = f.read()
                await guild.me.edit(avatar=image_data)
                log.info(f"🖼️ [GUILD AVATAR] Avatar défini pour {guild.name} ({guild_id})")
            except FileNotFoundError:
                log.error(f"❌ [GUILD AVATAR] Fichier introuvable : {avatar_path}")
            except Exception as e:
                log.error(f"❌ [GUILD AVATAR] Erreur pour {guild_id} : {e}")


    async def _load_cogs_from_directory(self, base: str) -> None:
        """
        Parcourt récursivement le dossier cogs/ et charge tous les fichiers .py
        (sauf __init__.py et les fichiers commençant par _).

        Skip silencieusement les fichiers vides ou sans fonction setup() :
        ils ne sont pas encore implémentés, ce n'est pas une erreur.
        """
        base_path = Path(base)
        loaded = 0
        skipped = 0
        failed = 0

        for path in sorted(base_path.rglob("*.py")):
            if path.name.startswith("_") or path.name == "__init__.py":
                continue

            # Skip silencieusement les fichiers vides (= pas encore implémentés)
            try:
                if path.stat().st_size == 0:
                    skipped += 1
                    continue
            except OSError:
                continue

            module = ".".join(path.with_suffix("").parts)
            try:
                await self.load_extension(module)
                log.info("  OK %s", module)
                loaded += 1
            except commands.NoEntryPointError:
                # Fichier non vide mais sans setup() → considéré comme stub aussi
                log.debug("  SKIP %s (pas encore de setup())", module)
                skipped += 1
            except Exception as e:
                log.error("  FAIL %s — %s", module, e, exc_info=True)
                failed += 1

        log.info(
            "Cogs chargés: %d  |  Stubs ignorés: %d  |  Échecs: %d",
            loaded, skipped, failed,
        )


async def main() -> None:
    async with GuideONBot() as bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass