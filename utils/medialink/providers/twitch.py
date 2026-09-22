"""
utils/medialink/providers/twitch.py — Provider MEDIALINK pour Twitch.

Implémentation contre le contrat de base.py (async, ProviderAccount,
ProviderCapabilities) — cf. la note de tête de fichier du squelette
d'origine pour le contexte complet (API Helix, choix polling vs
EventSub, etc.). Auth par App Access Token (OAuth2 "client
credentials"), via settings.twitch_client_id / settings.twitch_client_secret.

── Portée V1 ────────────────────────────────────────────────────────
LIVE_STATUS uniquement ("twitch.live_started") — pas de VOD ni de Clips
en V1 (décision d'équipe, cf. squelette). `ProviderCapabilities` étant
un Flag, ajouter NEW_POST (VOD) et/ou une future capability CLIPS plus
tard n'impacte ni le Core ni les connexions déjà créées.

Détection par POLLING (pas EventSub) — cf. squelette : plus simple pour
cette V1, migration vers EventSub envisageable dans une itération
suivante une fois le pipeline de bout en bout validé.

── Où l'ID Twitch est résolu ────────────────────────────────────────
IMPORTANT (différent de YouTubeProvider.connect(), qui résout un
@handle EN INTERNE) : ici, `connect(external_id)` reçoit l'ID Twitch
NUMÉRIQUE déjà résolu — c'est `get_account()` qui fait la résolution
pseudo → ID au moment de la configuration (vue), avant toute création
de MediaConnection. `connect()` ne fait donc plus de résolution, il ne
fait qu'initialiser le token.

── Détection du live : PAS d'état en mémoire ─────────────────────────
scheduler.py instancie un Provider NEUF à chaque passage
(`provider = provider_cls()`) — un `_was_live` en attribut d'instance
serait donc réinitialisé à chaque poll, inutile. À la place,
fetch_events() renvoie l'événement du stream en cours à CHAQUE appel
tant qu'il est live, avec external_id = stream["id"] (stable tant que
c'est la même session) — c'est l'anti-doublon DB de event_manager
(contrainte unique connection_id + external_event_id, §9.1) qui filtre
les répétitions, exactement comme YouTubeProvider.fetch_events() qui
renvoie les mêmes vidéos à chaque appel sans se soucier de ce qui a déjà
été vu. Le seul cas à gérer séparément est un live DÉJÀ en cours au
moment de la connexion (pour ne pas notifier rétroactivement) — cf.
seed_baseline_events() côté appelant (vue de configuration), même
mécanisme que pour le backlog de vidéos YouTube.

── Anti-doublon (et pourquoi PAS d'état "_was_live" en mémoire) ──────
external_id d'un MediaEvent "twitch.live_started" = le champ `id` de
l'objet stream renvoyé par Get Streams (l'ID de LA SESSION de live),
JAMAIS user_id (qui ne change jamais et ferait prendre tout live
suivant du même streamer pour un doublon du premier).

Le Scheduler (utils/medialink/scheduler.py) instancie un Provider
JETABLE à chaque passage (`provider_cls()` → connect() → fetch_events()
→ disconnect()) — aucun état en mémoire ne survit d'un poll à l'autre.
fetch_events() émet donc un MediaEvent à CHAQUE poll où le compte est
en live, sans essayer de détecter la transition off→on lui-même :
l'external_id (stable tant que CE live dure) suffit à l'anti-doublon
DB (UniqueConstraint sur media_events) pour ne laisser passer que le
tout premier événement de ce live — exactement le même principe que
YouTubeProvider, qui ne fait aucun suivi d'état interne non plus.

── Exceptions ────────────────────────────────────────────────────────
Même remarque que youtube.py : ProviderAuthError / ProviderNotFoundError
définies ICI en attendant la décision Core sur un errors.py partagé.
"""
from __future__ import annotations

import time
from datetime import datetime

import httpx

from utils.medialink.event import MediaEvent
from utils.medialink.providers.base import (
    BaseMediaProvider,
    ProviderAccount,
    ProviderCapabilities,
)
from utils.settings import settings

_AUTH_URL = "https://id.twitch.tv/oauth2/token"
_VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
_API_BASE_URL = "https://api.twitch.tv/helix"

# Marge de sécurité avant expiration réelle du token pour déclencher un
# refresh proactif (cf. _ensure_token()) plutôt que de risquer un 401 en
# plein milieu d'un passage du scheduler.
_TOKEN_REFRESH_MARGIN = 300  # secondes


class ProviderAuthError(Exception):
    """Auth invalide/refusée par la plateforme (client_id/secret mauvais,
    token refusé) — TEMPORAIRE ici, cf. note en tête de fichier."""


class ProviderNotFoundError(Exception):
    """Le compte externe (login Twitch) n'existe pas ou plus côté
    plateforme — TEMPORAIRE ici, cf. note en tête de fichier."""


def _strip_at(value: str) -> str:
    """Normalise un login Twitch : Get Users veut un login sans "@", mais
    un utilisateur peut très bien taper "@pseudo" dans la vue de
    configuration (même souci que le @handle YouTube)."""
    value = value.strip()
    return value[1:] if value.startswith("@") else value


def _parse_iso_datetime(value: str) -> datetime | None:
    """Convertit un timestamp ISO 8601 Twitch (ex: started_at =
    "2021-03-25T01:37:42Z") en datetime aware — même logique défensive
    que YouTubeProvider._parse_iso_datetime (cf. son commentaire : les
    colonnes DB sont typées `datetime`, pas `str`). None si
    absent/invalide plutôt que de faire planter fetch_events() en entier."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class TwitchProvider(BaseMediaProvider):
    name = "twitch"
    platform = "twitch"
    capabilities = ProviderCapabilities.LIVE_STATUS

    def __init__(self) -> None:
        self._client_id = settings.twitch_client_id
        self._client_secret = settings.twitch_client_secret
        self._client: httpx.AsyncClient | None = None

        self._access_token: str | None = None
        self._token_expires_at: float = 0.0  # time.monotonic()

        # Fixé par connect() — l'ID Twitch numérique, déjà résolu en amont
        # (cf. docstring de module).
        self._user_id: str | None = None

    # -- helpers internes ---------------------------------------------------

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def _ensure_token(self, *, force: bool = False) -> str:
        """Renvoie un access_token valide, en le (re)demandant si absent,
        trop proche de l'expiration, ou si `force=True` (ex: après un 401
        constaté ailleurs, cf. check_status()/_get())."""
        if (
            not force
            and self._access_token is not None
            and time.monotonic() < self._token_expires_at
        ):
            return self._access_token

        client = self._ensure_client()
        response = await client.post(
            _AUTH_URL,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "client_credentials",
            },
        )
        if response.status_code in (400, 401, 403):
            raise ProviderAuthError(
                f"Twitch OAuth2 a refusé la demande de token "
                f"(status={response.status_code}): {response.text}"
            )
        response.raise_for_status()
        data = response.json()

        self._access_token = data["access_token"]
        self._token_expires_at = (
            time.monotonic() + data["expires_in"] - _TOKEN_REFRESH_MARGIN
        )
        return self._access_token

    async def _get(self, endpoint: str, params: dict) -> dict:
        client = self._ensure_client()
        token = await self._ensure_token()
        response = await client.get(
            f"{_API_BASE_URL}/{endpoint}",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "Client-Id": self._client_id,
            },
        )
        if response.status_code == 401:
            # Token révoqué/expiré entre deux appels : un seul retry
            # après refresh forcé, pas de boucle infinie (si le vrai
            # problème est client_secret invalide, _ensure_token() lève
            # ProviderAuthError avant même d'arriver ici).
            token = await self._ensure_token(force=True)
            response = await client.get(
                f"{_API_BASE_URL}/{endpoint}",
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Client-Id": self._client_id,
                },
            )
        if response.status_code in (401, 403):
            raise ProviderAuthError(
                f"Twitch API a refusé la requête sur {endpoint} "
                f"(status={response.status_code}): {response.text}"
            )
        response.raise_for_status()
        return response.json()

    async def _get_current_stream(self) -> dict | None:
        """Renvoie l'objet stream Helix si le compte est en live
        maintenant, sinon None. Factorisé car utilisé par fetch_events()
        et par connect() (pour initialiser _was_live)."""
        data = await self._get("streams", {"user_id": self._user_id})
        items = data.get("data", [])
        return items[0] if items else None

    # -- contrat BaseMediaProvider -------------------------------------------

    async def connect(self, external_id: str, **credentials: object) -> None:
        """external_id = l'ID Twitch NUMÉRIQUE, déjà résolu en amont par
        get_account() (cf. docstring de module — contrairement à
        YouTubeProvider.connect() qui résout un @handle lui-même)."""
        self._user_id = external_id
        await self._ensure_token()

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def validate_account(self, external_id: str) -> bool:
        login = _strip_at(external_id)
        data = await self._get("users", {"login": login})
        return bool(data.get("data"))

    async def get_account(self, external_id: str) -> ProviderAccount:
        """external_id ICI = le pseudo/login tapé par l'utilisateur dans
        la vue de configuration (pas encore de connexion créée à ce
        stade) — c'est cette méthode qui fait la résolution pseudo → ID
        numérique stable, dont le résultat (external_id du
        ProviderAccount renvoyé) sera persisté comme
        MediaConnection.external_id ET réutilisé plus tard comme
        argument de connect() (cf. docstring de module)."""
        login = _strip_at(external_id)
        data = await self._get("users", {"login": login})
        items = data.get("data", [])
        if not items:
            raise ProviderNotFoundError(
                f"Compte Twitch introuvable pour external_id={external_id!r}"
            )
        item = items[0]
        resolved_id = item["id"]
        resolved_login = item.get("login", login)
        return ProviderAccount(
            external_id=resolved_id,
            username=item.get("display_name", resolved_login),
            url=f"https://www.twitch.tv/{resolved_login}",
            avatar_url=item.get("profile_image_url"),
            raw=item,
        )

    async def fetch_events(self) -> list[MediaEvent]:
        if self._user_id is None:
            raise RuntimeError("fetch_events() appelé avant connect()")

        stream = await self._get_current_stream()
        if stream is None:
            return []

        # Renvoyé à CHAQUE appel tant que le live dure (même stream["id"])
        # — pas de logique de transition ici, cf. docstring de module :
        # c'est l'anti-doublon DB (connection_id, external_event_id) qui
        # filtre les répétitions, exactement comme YouTubeProvider.
        thumbnail = (
            stream.get("thumbnail_url", "")
            .replace("{width}", "1280")
            .replace("{height}", "720")
        )
        return [
            MediaEvent(
                platform=self.platform,
                event_type="twitch.live_started",
                # cf. note anti-doublon en tête de fichier : l'id de
                # SESSION, jamais self._user_id.
                external_id=stream["id"],
                title=stream.get("title", ""),
                url=f"https://www.twitch.tv/{stream.get('user_login', '')}",
                thumbnail=thumbnail,
                author=stream.get("user_name", ""),
                published_at=_parse_iso_datetime(stream.get("started_at", "")),
            )
        ]

    async def check_status(self) -> bool:
        if self._access_token is None:
            return False

        client = self._ensure_client()
        response = await client.get(
            _VALIDATE_URL,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        if response.status_code == 401:
            try:
                await self._ensure_token(force=True)
            except ProviderAuthError:
                return False
            response = await client.get(
                _VALIDATE_URL,
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        return response.status_code == 200