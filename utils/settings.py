"""
utils/settings.py — Gestion des paramètres de configuration.

Usage :
    from utils.settings import settings
    settings.discord_token
"""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Discord
    discord_token: str
    guild_alpha_id: int = 1496765275670839306
    guild_dev_id: int = 1400451664946794618
    guild_support_id: int = 1184114738813227059
    guild_anniv_id: int = 1411296579528294402

    report_channel_id: int = 1488233511277297976

    # Environnement — distingue prod (DB `guideon`) de dev (DB `guideon_dev`).
    # Défaut "prod" volontaire (fail-safe) : un déploiement existant sans
    # variable ENV dans son .env doit rester bloqué sur les commandes
    # réservées au dev (/dev setng, /dev unsetng — cf refonte multi-serveurs
    # phase 5) plutôt que de les autoriser par accident.
    env: Literal["dev", "prod"] = "prod"

    @field_validator("env", mode="before")
    @classmethod
    def _normalize_env(cls, value: object) -> object:
        """Tolère ENV=DEV / Dev / dev etc. dans le .env (insensible à la casse)."""
        if isinstance(value, str):
            return value.strip().lower()
        return value

    # Database
    database_url: str = "postgresql+asyncpg://guideon:guideon@localhost:5432/guideon"
    database_echo: bool = False

    # API FastAPI
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_token: str = "QeUn6HmvEDaKL8f3fs0JEAED0IHEWf4dNv4JO4EM"

    # NationsGlory
    ng_api_key: str = ""
    ng_api_base_url: str = "https://api.nationsglory.fr"

    # URLs externes
    website_url: str = "https://guideonbot.guideon.dev/"
    shop_url: str = "https://guideonbot.guideon.dev/"
    doc_url: str = "https://guideonbot.guideon.dev/aide"

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "console"

settings = Settings()
