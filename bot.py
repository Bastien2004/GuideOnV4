"""
bot.py - Fichier principal du bot GuideOn.
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
from cogs.api.base import app as fastapi_app

from utils.managers.boutique_manager import refresh_cache, cache_refresher_loop
from utils.managers.ng_server_manager import list_active_servers as list_active_ng_servers
from utils.managers.ng_server_manager import reload_cache as reload_ng_servers
from utils.managers.permission_rbac_manager import refresh_cache as refresh_rbac


from utils.groupes import *

"""A laisser ! """
import cogs.api.notation_api_app
import cogs.api.staff_api
import cogs.api.stats_bot_api


# ============================================================
# 📁 Constantes & Paramètres
# ============================================================

log = logging.getLogger(__name__)


msg_error_bd = ("Impossible de se connecter à la base de données.\n"
                "  → Vérifie que PostgreSQL est démarré et que DATABASE_URL est correct.\n"
                "  → DATABASE_URL actuel pointe vers : %s\n"
                "  → Pour un Postgres local : docker run --name guideon-pg "
                "-e POSTGRES_PASSWORD=guideon -e POSTGRES_USER=guideon "
                "-e POSTGRES_DB=guideon -p 5432:5432 -d postgres:16\n"
                "  → Ou bascule sur SQLite dans .env : "
                "DATABASE_URL=sqlite+aiosqlite:///./guideon_dev.db")

# ============================================================
# 🔩 Fonctions utiles
# ============================================================

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


# ============================================================
# 🧩 Class principale du bot (démarrage)
# ============================================================

class GuideONBot(commands.Bot):
    """Gère le démarrage du bot."""

    def __init__(self) -> None:
        super().__init__(command_prefix="$", intents=build_intents(), help_command=None)

    async def setup_hook(self) -> None:
        setup_logging()
        log.info("[SETUP_HOOK]⏳ Démarrage du bot GuideOn")

        # ── DB ──
        from utils.db.engine import init_db
        try:
            await init_db()

        except Exception:
            log.critical(msg_error_bd, _mask_db_url(settings.database_url))
            raise

        # ── Boutique ──
        await refresh_cache()
        asyncio.create_task(cache_refresher_loop())

        # ── Permissions internes ──
        await reload_ng_servers()
        await refresh_rbac()

        # ── Chargement commandes simples  ──
        await self._load_cogs_from_directory("cogs")

        # ── Chargement commandes groupes ──
        await self._register_command_groups()

        # ── Chargement des views persistantes (tickets) ──
        from views.ticket.persistence import register_persistent_views
        await register_persistent_views(self)

        await self._sync_commands()

        # ── API FastAPI ──
        fastapi_app.state.bot = self
        run_api_server()

        log.info("[SETUP_HOOK] ✅ Démarrage terminé")


    # ============================================================
    # 🌐 Gestion des groupes de commandes
    # ============================================================

    async def _register_command_groups(self) -> None:
        """Assemble les groupes de commandes."""

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
        from cogs.dev.health import health
        from cogs.dev.guild_info import guild_info
        from cogs.dev.debug_cmd import debug_cmd
        from cogs.dev.botban import botban
        from cogs.dev.gold import gold
        from cogs.dev.vip import vip

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
        from cogs.mod.mod_permissions import mod_permissions
        from cogs.mod.mod_warn import mod_warn
        from cogs.mod.mod_unwarn import mod_unwarn
        from cogs.mod.mod_mute import mod_mute
        from cogs.mod.mod_unmute import mod_unmute
        from cogs.mod.mod_kick import mod_kick
        from cogs.mod.mod_ban import mod_ban
        from cogs.mod.mod_tempban import mod_tempban
        from cogs.mod.mod_unban import mod_unban
        from cogs.mod.mod_softban import mod_softban
        from cogs.mod.mod_historique import mod_historique
        from cogs.mod.mod_rename import mod_rename
        from cogs.mod.mod_logs import mod_logs
        from cogs.mod.mod_clear import mod_clear
        from cogs.mod.mod_lock import mod_lock
        from cogs.mod.mod_vocal import mod_vocal
        
        # ── IMPORT EXP ──
        from cogs.exp.exp_level import exp_level
        from cogs.exp.exp_leaderboard import exp_leaderboard
        from cogs.exp.exp_gestion import exp_gestion
        from cogs.exp.exp_config import exp_config
        
        # ── IMPORT ALPHA ──
        from cogs.alpha.test import test_alpha
        from cogs.alpha.regle_interne import regle_interne
        from cogs.alpha.nous_rejoindre import nous_rejoindre
        from cogs.alpha.index import index
        from cogs.alpha.event_list import event_list
        from cogs.alpha.event_regle import event_regle
        from cogs.alpha.event_start import event_start

        # ── IMPORT NGSTAFF ──
        from cogs.ngstaff.ngstaff_config import ngstaff_config
        from cogs.ngstaff.ngstaff_derank import ngstaff_derank
        from cogs.ngstaff.ngstaff_edit_stafflist import ngstaff_edit_stafflist
        from cogs.ngstaff.ngstaff_nota_debug import ngstaff_nota_debug
        from cogs.ngstaff.ngstaff_rank import ngstaff_rank
        from cogs.ngstaff.ngstaff_stafflist import ngstaff_stafflist

        # ── IMPORT QR ──
        # from cogs.qr.xxxx import xxxxx


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
        for cmd in [maintenance, permissions, delete_message, kick, stat_server, stat_cmd,
                    join_serv, health, guild_info, debug_cmd, botban, gold, vip]:
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


        # 🛡️ ── MOD ──
        groupMOD = groupeMOD()
        for cmd in [
            mod_permissions, mod_warn, mod_unwarn, mod_mute, mod_unmute,
            mod_kick, mod_ban, mod_tempban, mod_unban, mod_softban, mod_historique, mod_rename, mod_logs,
            mod_clear, mod_lock, mod_vocal]:
            groupMOD.add_command(cmd)


        # 🧩 ── EXP ──
        groupEXP = groupeEXP()
        for cmd in [exp_level, exp_leaderboard, exp_gestion, exp_config]:
            groupEXP.add_command(cmd)


        # 🪢 ── QR ──
            groupQR = groupeQR()
            for cmd in []: #Ajouter les commandes QR ici (scan, generate, list ...)
                groupQR.add_command(cmd)


        # 💋 ── ALPHA ──
        self._groupALPHA = groupeALPHA()
        for cmd in [test_alpha, regle_interne, nous_rejoindre, index, event_start, event_regle, event_list]:
            self._groupALPHA.add_command(cmd)


        # 🚨 ── NGSTAFF ──
        self._groupNGSTAFF = groupeNGSTAFF()
        for cmd in [
            ngstaff_config, ngstaff_rank, ngstaff_derank, ngstaff_stafflist,
            ngstaff_edit_stafflist, ngstaff_nota_debug]:
            self._groupNGSTAFF.add_command(cmd)


        for group in [groupCONFIG, groupNG, groupTICKET, groupINV, groupBIRTHDAY, groupGIVE, groupEXP, groupMOD, groupQR]:
            self.tree.add_command(group)

        log.info("[SETUP_HOOK] ✅ Groupes de commandes enregistrés.")


    async def _sync_commands(self):

        # ============================================================
        # 🌐 Synchronisation des commandes
        # ============================================================

        try:
            synced = await self.tree.sync()
            log.info(f"🌍 {len(synced)} commandes globales synchronisées.")
        except Exception as e:
            log.error(f"❌ Erreur sync globale : {e}")


        # Sync commande Alpha

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

                log.info(f"💋 Commandes ALPHA synchronisées sur {gid} ({len(synced)} cmd)")

            except Exception as e:
                log.error(f"❌ Erreur ALPHA {gid}: {e}")


        # Sync commande NGSTAFF

        for ng_server in list_active_ng_servers():
            guild = discord.Object(id=ng_server.discord_guild_id)

            try:
                try:
                    self.tree.add_command(self._groupNGSTAFF, guild=guild)
                except discord.app_commands.CommandAlreadyRegistered:
                    pass

                synced = await self.tree.sync(guild=guild)

                log.info(
                    f"🧑\u200d💼 Commandes NGSTAFF synchronisées sur {ng_server.name} "
                    f"({ng_server.discord_guild_id}, {len(synced)} cmd)"
                )

            except Exception as e:
                log.error(f"❌ Erreur NGSTAFF {ng_server.name} ({ng_server.discord_guild_id}): {e}")

        # Sync commande DEV

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

        # Sync commande support

        SUPPORT_GUILDS = [1184114738813227059]

        for gid in SUPPORT_GUILDS:
            guild = discord.Object(id=gid)

            try:
                synced = await self.tree.sync(guild=guild)

                log.info(f"🛠️ Commandes SUPPORT synchronisées sur {gid} ({len(synced)} cmd)")

            except Exception as e:
                log.error(f"❌ Erreur SUPPORT {gid}: {e}")



    async def on_ready(self) -> None:

        if not hasattr(self, "_ready_done"):
            self._ready_done = True

            await self._set_guild_avatars()

        log.info("[READY] Connecté en tant que %s (%s)", self.user, self.user.id if self.user else "?")
        log.info("[READY] %d serveurs connectés", len(self.guilds))


        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"👀 {len(self.users)} utilisateurs accompagnés"
            )
        )


    # ============================================================
    # 🖼️ Avatar personalisé par seveur
    # ============================================================

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
        """Charge tout les fichier .py du dossier cogs/."""

        base_path = Path(base)
        loaded = 0
        skipped = 0
        failed = 0

        for path in sorted(base_path.rglob("*.py")):
            if path.name.startswith("_") or path.name == "__init__.py":
                continue

            try:
                if path.stat().st_size == 0:
                    skipped += 1
                    continue
            except OSError:
                continue

            module = ".".join(path.with_suffix("").parts)
            try:
                await self.load_extension(module)
                log.info("[LOAD] %s", module)
                loaded += 1

            except commands.NoEntryPointError:
                skipped += 1

            except Exception as e:
                log.error("[ERROR LOAD] %s — %s", module, e, exc_info=True)
                failed += 1

        log.info("[LOAD] Cogs chargés: %d  |  Stubs ignorés: %d  |  Échecs: %d", loaded, skipped, failed)


# ============================================================
# 💻 Fonction main
# ============================================================

async def main() -> None:
    async with GuideONBot() as bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass