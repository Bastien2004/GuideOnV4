"""
utils/medialink/providers/base.py — Contrat commun à tous les Providers
MEDIALINK (YouTube, Twitch, TikTok, Reddit...).

C'EST LE FICHIER LE PLUS IMPORTANT POUR BASTIEN : c'est le contrat exact
que chaque intégration plateforme (partie "connexion API" du découpage)
doit respecter pour s'insérer dans le pipeline sans que le Core ait à
connaître la moindre spécificité d'une plateforme (§8.1 : "Le Core ne
doit pas contenir de logique spécifique à YouTube, Twitch, TikTok ou
Reddit").

Règle d'or (§8) : un Provider ne doit JAMAIS envoyer de message Discord.
Il produit des MediaEvent (utils/medialink/event.py) via fetch_events() ;
c'est tout. L'Event Manager, les Rules et le Notification Engine
décident ensuite quoi en faire.

Ce fichier fixe le contrat de la Phase 0 (P0.1/P0.2 de la roadmap) :
c'est volontairement la toute première pièce du module à livrer, avant
même que le reste du Core ou les vues ne soient finalisés, pour que le
travail d'intégration API puisse démarrer en parallèle du reste.

Chaque provider concret (youtube.py, twitch.py, tiktok.py, reddit.py)
viendra se ranger dans ce même dossier utils/medialink/providers/.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Flag, auto

from utils.medialink.event import MediaEvent


class ProviderCapabilities(Flag):
    """Ce qu'un Provider sait détecter, en plus du minimum attendu.

    Toutes les plateformes ne proposent pas les mêmes types d'événements
    (ex: une "Story" TikTok n'a pas d'équivalent YouTube) — un Provider
    déclare ce qu'il sait faire via `capabilities`, et le Core (ou les
    vues de configuration de règles) s'appuient dessus pour ne proposer
    QUE les event_type réellement supportés par la plateforme choisie,
    plutôt que de figer une liste d'event_type commune à toutes (§3 :
    "Préparer l'architecture à l'ajout futur d'autres plateformes").
    """

    NONE = 0
    NEW_POST = auto()
    LIVE_STATUS = auto()
    SHORT_FORM = auto()  # ex: YouTube Shorts, TikTok
    COMMENTS = auto()


@dataclass(slots=True)
class ProviderAccount:
    """Représentation normalisée d'un compte externe, telle que renvoyée
    par validate_account()/get_account() — indépendante du modèle DB
    MediaConnection : le Provider ne sait pas ce qu'est une guild ni une
    connexion GuideOn, seulement "un compte sur sa plateforme"."""

    external_id: str
    username: str | None = None
    url: str | None = None
    avatar_url: str | None = None
    raw: dict = field(default_factory=dict)


class BaseMediaProvider(ABC):
    """Contrat minimal qu'un Provider MEDIALINK doit implémenter.

    Un Provider est un objet SANS ÉTAT PARTAGÉ entre guildes/comptes :
    chaque instance correspond à UNE connexion (un compte suivi sur la
    plateforme), créée/détruite via connect()/disconnect(). C'est le
    Scheduler (utils/medialink/scheduler.py) qui orchestre le cycle de
    vie de plusieurs instances, une par MediaConnection active.
    """

    #: Identifiant technique court, ex: "youtube", "twitch" — DOIT
    #: correspondre à une valeur de utils.db.models.medialink_connection.MediaPlatform.
    name: str

    #: Alias de name pour l'instant (conservé séparé au cas où un jour un
    #: même `name` de Provider gère plusieurs `platform`, ex: un futur
    #: Provider générique RSS couvrant plusieurs plateformes).
    platform: str

    #: Ce que ce Provider sait détecter — cf. ProviderCapabilities.
    capabilities: ProviderCapabilities = ProviderCapabilities.NONE

    @abstractmethod
    async def connect(self, external_id: str, **credentials: object) -> None:
        """Initialise la connexion au compte externe (auth API, tokens...).

        Ne doit lever que des exceptions du domaine MEDIALINK (à définir
        dans utils/medialink/, ex: ProviderAuthError) — jamais laisser
        fuiter une exception brute d'un SDK tiers jusqu'au Core.
        """
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        """Libère les ressources (sessions HTTP, websockets...). Doit
        pouvoir être appelée même si connect() a échoué ou n'a jamais
        été appelée, sans lever d'exception (idempotent)."""
        raise NotImplementedError

    @abstractmethod
    async def validate_account(self, external_id: str) -> bool:
        """Vérifie qu'un identifiant de compte existe bien côté
        plateforme, AVANT de créer une MediaConnection en base — c'est
        ce qui permet à la vue de configuration (§6) de dire tout de
        suite "compte introuvable" plutôt que de créer une connexion
        qui échouera au premier check_status()."""
        raise NotImplementedError

    @abstractmethod
    async def get_account(self, external_id: str) -> ProviderAccount:
        """Récupère les métadonnées affichables d'un compte (nom, avatar,
        URL) — utilisé pour peupler MediaConnection.external_username /
        avatar_url / external_url au moment de la connexion, et pour les
        rafraîchir périodiquement."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_events(self) -> list[MediaEvent]:
        """Récupère les événements nouveaux depuis le dernier appel.

        Ne doit renvoyer QUE des MediaEvent — jamais envoyer de message
        Discord ni écrire en base directement (règle d'or, §8). C'est
        l'Event Manager qui applique l'anti-doublon (§9.1) sur le
        external_id renvoyé ici, donc un Provider peut renvoyer un même
        événement plusieurs fois sans risque (idempotence côté appelant).
        """
        raise NotImplementedError

    @abstractmethod
    async def check_status(self) -> bool:
        """Renvoie True si la connexion est opérationnelle (cf. §6.3
        états OPERATIONAL/DEGRADED/ERROR/DISABLED — c'est ce résultat,
        combiné à l'historique récent, que l'Event Manager traduit en
        ConnectionStatus et en met à jour MediaConnection.status /
        last_checked_at)."""
        raise NotImplementedError
