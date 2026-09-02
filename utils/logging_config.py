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
import os
import sys
from logging.handlers import TimedRotatingFileHandler

from utils.settings import settings

LOG_DIR = "/app/data/logs"


def setup_logging() -> None:
    level = getattr(logging, settings.log_level)
    fmt = (
        "%(asctime)s [%(levelname)-7s] %(name)-30s | %(message)s"
        if settings.log_format == "console"
        else '{"ts":"%(asctime)s","lvl":"%(levelname)s","mod":"%(name)s","msg":"%(message)s"}'
    )
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    # Handler stdout (inchangé, alimente toujours `docker logs`)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    # Handler fichier avec rotation quotidienne, rétention 30 jours.
    # /app/data est bind-mounté vers ./data sur l'hôte -> survit aux
    # `docker compose down && up --build` des déploiements.
    os.makedirs(LOG_DIR, exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR, "bot.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=True,
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(stream_handler)
    root.addHandler(file_handler)

    # Réduire le bruit des libs
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.database_echo else logging.WARNING
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
