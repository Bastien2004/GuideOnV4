"""
Configuration unique du logging pour tout le projet.

À appeler UNE seule fois, depuis bot.py setup_hook().

Usage dans n'importe quel module :
    import logging
    log = logging.getLogger(__name__)
    log.info("...")

JAMAIS de print() (problème CODE-002 de l'audit V3).
"""
import logging
import sys

from utils.settings import settings


def setup_logging() -> None:
    level = getattr(logging, settings.log_level)

    fmt = (
        "%(asctime)s [%(levelname)-7s] %(name)-30s | %(message)s"
        if settings.log_format == "console"
        else '{"ts":"%(asctime)s","lvl":"%(levelname)s","mod":"%(name)s","msg":"%(message)s"}'
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Réduire le bruit des libs
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.database_echo else logging.WARNING
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
