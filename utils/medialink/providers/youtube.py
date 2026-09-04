"""
utils/medialink/providers/youtube.py — Provider MEDIALINK pour YouTube.

Implémentation contre le contrat de base.py (async, ProviderAccount,
ProviderCapabilities). Auth par clé API simple (settings.youtube_api_key).

── Exceptions ────────────────────────────────────────────────────────
Le squelette d'origine suggérait un utils/medialink/errors.py commun à
tous les providers (à discuter avec l'équipe Core). En attendant cette
décision, les deux exceptions nécessaires sont définies ICI, dans ce
même fichier, pour ne pas créer de fichier supplémentaire tant que ce
n'est pas validé avec Paul. À déplacer facilement plus tard si Core
tranche pour un errors.py partagé (aucun autre fichier n'a besoin d'y
toucher d'ici là, ces deux classes ne sont utilisées que par ce provider).
"""
from __future__ import annotations

import re
from datetime import datetime

import httpx

from utils.medialink.event import MediaEvent
from utils.medialink.providers.base import (
    BaseMediaProvider,
    ProviderAccount,
    ProviderCapabilities,
)
from utils.settings import settings

_API_BASE_URL = "https://www.googleapis.com/youtube/v3"

# Un Short se détecte par une durée courte (signal le plus robuste et
# documenté ; pas de ratio vertical fiable à 100% côté API, cf. plus bas).
_SHORT_MAX_SECONDS = 180

# ISO 8601 duration comme renvoyée par videos.list contentDetails.duration
# (ex: "PT1M30S", "PT45S", "PT2H"). Pas besoin de dépendance externe
# (isodate) pour ce sous-ensemble simple.
_DURATION_RE = re.compile(
    r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)


class ProviderAuthError(Exception):
    """Auth invalide/refusée par la plateforme (clé API mauvaise/révoquée,
    quota épuisé) — TEMPORAIRE ici, cf. note en tête de fichier."""


class ProviderNotFoundError(Exception):
    """Le compte externe (external_id) n'existe pas ou plus côté plateforme
    — TEMPORAIRE ici, cf. note en tête de fichier."""


def _parse_duration_seconds(duration: str) -> int:
    match = _DURATION_RE.match(duration or "")
    if not match:
        return 0
    parts = match.groupdict()
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)
    return hours * 3600 + minutes * 60 + seconds


def _chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _parse_iso_datetime(value: str) -> datetime | None:
    """Convertit un timestamp ISO 8601 tel que renvoyé par l'API YouTube
    (ex: "2022-06-06T10:05:43Z") en datetime aware.

    BUG CORRIGÉ (2026-09, trouvé en prod dès le premier vrai passage du
    scheduler) : cette valeur était passée telle quelle (une str) à
    MediaEvent.published_at / media_events.published_at, tous deux
    typés `datetime`, pas `str` — asyncpg refuse d'insérer une str dans
    une colonne TIMESTAMPTZ ("expected a datetime.date or
    datetime.datetime instance, got 'str'"), ce qui faisait planter
    event_manager._persist_if_new() sur CHAQUE événement.

    None si absent/invalide plutôt que de faire planter fetch_events()
    en entier pour une vidéo (même logique défensive que
    _parse_duration_seconds ci-dessus)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class YouTubeProvider(BaseMediaProvider):
    name = "youtube"
    platform = "youtube"
    capabilities = (
        ProviderCapabilities.NEW_POST
        | ProviderCapabilities.SHORT_FORM
        | ProviderCapabilities.LIVE_STATUS
    )

    def __init__(self) -> None:
        self._api_key = settings.youtube_api_key
        self._client: httpx.AsyncClient | None = None
        self._channel_id: str | None = None
        self._uploads_playlist_id: str | None = None
        self._channel_title: str = ""

    # -- helpers internes ---------------------------------------------------

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=_API_BASE_URL, timeout=10.0)
        return self._client

    async def _get(self, endpoint: str, params: dict) -> dict:
        client = self._ensure_client()
        query = {**params, "key": self._api_key}
        response = await client.get(f"/{endpoint}", params=query)
        if response.status_code in (401, 403):
            # 403 est aussi utilisé par Google pour "quotaExceeded", pas
            # seulement pour une clé invalide — on les traite pareil ici.
            raise ProviderAuthError(
                f"YouTube API a refusé la requête sur {endpoint} "
                f"(status={response.status_code}): {response.text}"
            )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _resolve_handle_or_id(external_id: str) -> dict:
        """Construit les params channels.list selon que external_id
        ressemble à un ID de chaîne (UC...) ou à un @handle."""
        external_id = external_id.strip()
        if external_id.startswith("UC"):
            return {"id": external_id}
        handle = external_id if external_id.startswith("@") else f"@{external_id}"
        return {"forHandle": handle}

    # -- contrat BaseMediaProvider -------------------------------------------

    async def connect(self, external_id: str, **credentials: object) -> None:
        """external_id = l'ID de chaîne YouTube ("UC...") ou un @handle.

        BUG CORRIGÉ (2026-09) : cette méthode appelait channels.list avec
        id=external_id sans passer par _resolve_handle_or_id() (contrairement
        à validate_account()/get_account() juste au-dessus) — un @handle
        stocké tel quel en base (ex: connexion créée avant que get_account()
        soit lui-même corrigé, cf. son commentaire) faisait échouer connect()
        à CHAQUE cycle du scheduler avec "Chaîne YouTube introuvable pour
        external_id=...". Alignée ici sur le même helper que le reste du
        Provider, par cohérence et défense en profondeur.
        """
        params = self._resolve_handle_or_id(external_id)

        data = await self._get(
            "channels",
            {"part": "contentDetails,snippet", **params},
        )
        items = data.get("items", [])
        if not items:
            raise ProviderNotFoundError(
                f"Chaîne YouTube introuvable pour external_id={external_id!r}"
            )

        item = items[0]
        # self._channel_id est fixé sur l'ID RÉSOLU par l'API (items[0]["id"]),
        # jamais sur l'external_id brut passé en argument : si un @handle a
        # été fourni, external_id n'est PAS un channel_id valide, et
        # check_status() (qui réutilise self._channel_id avec id=...)
        # échouerait exactement pareil sinon.
        self._channel_id = item["id"]
        self._uploads_playlist_id = (
            item["contentDetails"]["relatedPlaylists"]["uploads"]
        )
        self._channel_title = item.get("snippet", {}).get("title", "")

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def validate_account(self, external_id: str) -> bool:
        params = self._resolve_handle_or_id(external_id)
        data = await self._get("channels", {"part": "id", **params})
        return bool(data.get("items"))

    async def get_account(self, external_id: str) -> ProviderAccount:
        # BUG CORRIGÉ (2026-09, intégration vue) : cette méthode appelait
        # channels.list avec id=external_id sans passer par
        # _resolve_handle_or_id (contrairement à validate_account juste
        # au-dessus) — un @handle saisi par l'utilisateur ne renvoyait
        # donc jamais aucun résultat (le paramètre `id` de l'API veut un
        # vrai ID de chaîne "UC...", pas un handle ; seul `forHandle` le
        # résout). Alignée ici sur validate_account pour accepter les
        # deux formats, comme le fait déjà le reste du Provider.
        params = self._resolve_handle_or_id(external_id)
        data = await self._get("channels", {"part": "snippet", **params})
        items = data.get("items", [])
        if not items:
            raise ProviderNotFoundError(
                f"Chaîne YouTube introuvable pour external_id={external_id!r}"
            )
        # L'external_id persisté DOIT être l'ID de chaîne stable renvoyé
        # par l'API ("items[0]['id']"), jamais ce que l'utilisateur a
        # tapé : un @handle peut changer de propriétaire/être réutilisé,
        # alors que l'ID "UC..." est la clé anti-doublon stable (§9.1,
        # cf. docstring de module et ProviderAccount.external_id).
        resolved_id = items[0]["id"]
        snippet = items[0]["snippet"]
        return ProviderAccount(
            external_id=resolved_id,
            username=snippet.get("title"),
            url=f"https://www.youtube.com/channel/{resolved_id}",
            avatar_url=snippet.get("thumbnails", {}).get("default", {}).get("url"),
            raw=items[0],
        )

    async def fetch_events(self) -> list[MediaEvent]:
        if self._uploads_playlist_id is None:
            raise RuntimeError("fetch_events() appelé avant connect()")

        playlist_data = await self._get(
            "playlistItems",
            {
                "part": "snippet",
                "playlistId": self._uploads_playlist_id,
                "maxResults": 10,
            },
        )
        playlist_items = playlist_data.get("items", [])
        video_ids = [
            item["snippet"]["resourceId"]["videoId"]
            for item in playlist_items
            if item.get("snippet", {}).get("resourceId", {}).get("videoId")
        ]
        if not video_ids:
            return []

        videos_by_id: dict[str, dict] = {}
        for chunk in _chunked(video_ids, 50):
            videos_data = await self._get(
                "videos",
                {
                    "part": "snippet,contentDetails,liveStreamingDetails",
                    "id": ",".join(chunk),
                },
            )
            for video in videos_data.get("items", []):
                videos_by_id[video["id"]] = video

        events: list[MediaEvent] = []
        for video_id in video_ids:
            video = videos_by_id.get(video_id)
            if video is None:
                # Vidéo supprimée/privée entre les deux appels : on l'ignore
                # plutôt que de faire planter tout fetch_events().
                continue

            snippet = video.get("snippet", {})
            content_details = video.get("contentDetails", {})
            live_details = video.get("liveStreamingDetails")

            is_live_now = snippet.get("liveBroadcastContent") == "live"
            duration_seconds = _parse_duration_seconds(
                content_details.get("duration", "")
            )

            if is_live_now and live_details is not None:
                event_type = "youtube.live_started"
            elif duration_seconds <= _SHORT_MAX_SECONDS:
                event_type = "youtube.short_published"
            else:
                event_type = "youtube.video_published"

            events.append(
                MediaEvent(
                    platform=self.platform,
                    event_type=event_type,
                    external_id=video_id,
                    title=snippet.get("title", ""),
                    description=snippet.get("description", ""),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    thumbnail=(
                        snippet.get("thumbnails", {})
                        .get("high", {})
                        .get("url", "")
                    ),
                    author=snippet.get("channelTitle", self._channel_title),
                    published_at=_parse_iso_datetime(snippet.get("publishedAt", "")),
                )
            )

        # Pas de filtrage anti-doublon ici (rôle d'event_manager.ingest()).
        return events

    async def check_status(self) -> bool:
        if self._channel_id is None:
            return False
        data = await self._get(
            "channels", {"part": "id", "id": self._channel_id}
        )
        return bool(data.get("items"))