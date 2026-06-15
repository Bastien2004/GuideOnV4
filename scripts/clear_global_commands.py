"""
Script one-shot pour vider le cache global des slash commands Discord.

À lancer UNE FOIS quand on a des commandes fantômes (anciennes V3 ou autres
qui apparaissent toujours).

Discord met jusqu'à 1h pour propager le changement côté client.

Usage : python -m scripts.clear_global_commands
"""
import asyncio
import logging

import discord
from discord.ext import commands

from utils.logging_config import setup_logging
from utils.settings import settings

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    setup_logging()

    intents = discord.Intents.none()
    intents.guilds = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        print(f"Connecté en tant que {bot.user}")
        print("Suppression de toutes les commandes globales...")
        bot.tree.clear_commands(guild=None)
        synced = await bot.tree.sync()
        print(f"Sync global terminé. {len(synced)} commandes restantes.")
        print("⚠ Le cache Discord peut prendre jusqu'à 1h à se propager.")
        await bot.close()

    await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())