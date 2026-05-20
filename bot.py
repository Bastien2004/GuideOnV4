"""
Point d'entrée GuideON V4.

Lancement: python bot.py

Architecture inspirée de la V3 :
- Charge tous les cogs depuis cogs/<système>/
- Charge tous les events depuis cogs/events/
- Charge l'API FastAPI dans un thread daemon
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import discord
from discord.ext import commands

from utils.logging_config import setup_logging
from utils.settings import settings

log = logging.getLogger(__name__)


def _mask_db_url(url: str) -> str:
    """Masque le mot de passe dans une URL de DB avant de la logger."""
    # postgresql+asyncpg://user:PASSWORD@host:port/db  ->  ...://user:***@host...
    import re
    return re.sub(r"(://[^:/?#]+:)([^@]+)(@)", r"\1***\3", url)


def build_intents() -> discord.Intents:
    """
    Intents minimaux. PAS Intents.all() comme en V3 (problème PRF-001).

    On retire presences et typing qui ne sont pas utilisés et coûtent cher
    en bande passante quand on est sur 20+ serveurs.
    """
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
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=build_intents(),
            help_command=None,
        )

    async def setup_hook(self) -> None:
        setup_logging()
        log.info("Démarrage du bot GuideON V4")

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
            raise  # on stoppe net : un bot sans DB ne sert à rien

        # ── Boutique : préchargement bloquant + boucle de refresh ──
        # is_vip()/is_gold() renvoient False tant que le cache n'est pas prêt.
        # On précharge AVANT le sync pour éviter tout refus à tort au démarrage.
        from utils.managers.boutique_manager import refresh_cache, cache_refresher_loop
        await refresh_cache()
        self.loop.create_task(cache_refresher_loop())

        # ── Cogs auto (les commands.Cog avec setup(), ex. /ping, /info) ──
        await self._load_cogs_from_directory("cogs")

        # ── Groupes de commandes (fonctions libres, pattern V3) ──
        # Les fichiers de commandes groupées (cogs/config/bienvenue.py, etc.)
        # n'ont PAS de setup() : l'auto-loader les ignore (NoEntryPointError),
        # on les importe et on les assemble explicitement ici.
        self._register_command_groups()

        TEST_GUILD_ID = 1505970079500734695
        test_guild = discord.Object(id=TEST_GUILD_ID)

        self.tree.clear_commands(guild=test_guild)
        self.tree.copy_global_to(guild=test_guild)
        synced = await self.tree.sync(guild=test_guild)
        log.info("%d slash commands sync sur la guild de test", len(synced))

        # ── API FastAPI (thread daemon) — démarrée APRÈS que la DB soit OK ──
        # Ainsi l'API ne tourne jamais "dans le vide" si la connexion DB échoue.
        from cogs.api.api_app import run_api_server
        run_api_server()

        log.info("setup_hook terminé")

    # ------------------------------------------------------------------
    # 👥 Groupes de commandes (pattern V3 : fonctions libres)
    # ------------------------------------------------------------------
    def _register_command_groups(self) -> None:
        """
        Assemble les groupes de commandes à partir des fonctions libres.

        Même logique qu'en V3 : instancier le groupe, add_command() chaque
        fonction-commande, puis tree.add_command() — uniquement si le groupe
        contient au moins une sous-commande (Discord rejette les groupes vides).

        Au fur et à mesure que les systèmes sont portés en V4, décommente les
        imports et ajoute les commandes à la liste du groupe correspondant.
        """
        from utils.groupes import groupeCONFIG  # + groupeMOD, groupeNG, ... au besoin

        # ── CONFIG ──
        from cogs.config.bienvenue import bienvenue
        # from cogs.config.autorole import autorole       # quand porté
        # from cogs.config.exp import exp
        # from cogs.config.role_react import role_reaction

        groupCONFIG = groupeCONFIG()
        for cmd in [bienvenue]:                # ajoute autorole, exp... ici
            groupCONFIG.add_command(cmd)

        # ── MOD / NG / EXP / INVITE / GIVEAWAY / TICKET ──
        # Même schéma : groupMOD = groupeMOD(); groupMOD.add_command(clear); ...

        # ── Enregistrement dans l'arbre (groupes globaux non vides) ──
        for group in [groupCONFIG]:            # + groupMOD, groupNG, ... au besoin
            if group.commands:                 # ne jamais ajouter un groupe vide
                self.tree.add_command(group)
                log.info(
                    "Groupe /%s enregistré (%s)",
                    group.name,
                    ", ".join(c.name for c in group.commands),
                )

        # ── Groupes restreints par guild (dev/anniv/...) ──
        # self._groupDEV = groupeDEV()
        # for cmd in [...]: self._groupDEV.add_command(cmd)
        # → ajout + sync par guild à gérer ici ou dans une étape _sync dédiée.

    async def on_ready(self) -> None:
        log.info("Connecté en tant que %s (%s)", self.user, self.user.id if self.user else "?")
        log.info("%d serveurs connectés", len(self.guilds))

        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="GuideON V4"),
        )

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
    bot = GuideONBot()
    await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())