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
from utils.error_handler import register_error_handlers

log = logging.getLogger(__name__)


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

        # DB : init (à coder avec le collègue dev)
        # from utils.db.engine import init_db
        # await init_db()

        # Handler global d'erreurs
        register_error_handlers(self)

        # Chargement des cogs
        await self._load_cogs_from_directory("cogs")

        log.info("setup_hook terminé")

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
        (sauf __init__.py).

        Format attendu : chaque fichier expose une fonction async setup(bot).
        """
        base_path = Path(base)
        for path in sorted(base_path.rglob("*.py")):
            if path.name.startswith("_") or path.name == "__init__.py":
                continue

            module = ".".join(path.with_suffix("").parts)
            try:
                await self.load_extension(module)
                log.info("  OK %s", module)
            except Exception as e:
                log.error("  FAIL %s — %s", module, e, exc_info=True)


async def main() -> None:
    bot = GuideONBot()

    # API FastAPI dans un thread daemon (à activer quand prêt)
    # from cogs.api.api_app import run_api_server
    # run_api_server(bot)

    await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())