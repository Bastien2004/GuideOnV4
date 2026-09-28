"""
utils/medialink/providers/base.py — Gestion des providers (YouTube, Twitch, Reddit...).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Flag, auto

from utils.medialink.event import MediaEvent


class ProviderCapabilities(Flag):
    """Détection du provider."""

    NONE = 0
    NEW_POST = auto()
    LIVE_STATUS = auto()
    SHORT_FORM = auto()
    COMMENTS = auto()
    CLIPS = auto()


@dataclass(slots=True)
class ProviderAccount:
    """Représentation normalisée d'un compte externe."""

    external_id: str
    username: str | None = None
    url: str | None = None
    avatar_url: str | None = None
    raw: dict = field(default_factory=dict)


class BaseMediaProvider(ABC):
    """Base d'un provider."""

    name: str
    platform: str
    capabilities: ProviderCapabilities = ProviderCapabilities.NONE

    @abstractmethod
    async def connect(self, external_id: str, **credentials: object) -> None:
        """Initialise la connexion au compte externe."""
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        """Libère les ressources (sessions HTTP, websockets...)."""
        raise NotImplementedError

    @abstractmethod
    async def validate_account(self, external_id: str) -> bool:
        """Vérifie qu'un identifiant de compte existe bien côté plateforme."""
        raise NotImplementedError

    @abstractmethod
    async def get_account(self, external_id: str) -> ProviderAccount:
        """Récupère les métadonnées affichables d'un compte."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_events(self) -> list[MediaEvent]:
        """Récupère les événements nouveaux depuis le dernier appel."""
        raise NotImplementedError

    @abstractmethod
    async def check_status(self) -> bool:
        """Renvoie True si la connexion est opérationnelle."""
        raise NotImplementedError