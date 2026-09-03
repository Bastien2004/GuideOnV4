"""
utils/medialink/providers/youtube.py — Provider MEDIALINK pour YouTube.

═══════════════════════════════════════════════════════════════════════
 POUR BASTIEN — CE QUI EST ATTENDU DE TOI SUR CE FICHIER
═══════════════════════════════════════════════════════════════════════

Ce fichier est un SQUELETTE : la classe hérite déjà de BaseMediaProvider
(utils/medialink/providers/base.py — LIS-LE EN PREMIER, c'est le contrat
que toutes les méthodes ci-dessous doivent respecter) et chaque méthode
est présente avec sa signature exacte, mais le corps lève
NotImplementedError. Ton travail : remplacer chaque corps par du vrai
code qui appelle l'API YouTube Data v3, SANS changer les signatures
(le reste du bot — event_manager, scheduler — appelle ces méthodes
telles quelles).

Règle d'or à ne jamais casser (rappelée dans base.py) : ce Provider ne
doit JAMAIS envoyer de message Discord. Il ne fait QUE lire l'API
YouTube et renvoyer des MediaEvent. C'est event_manager.py qui décide
quoi en faire ensuite.

── API utilisée ─────────────────────────────────────────────────────
YouTube Data API v3 (Google Cloud). Docs officielles :
https://developers.google.com/youtube/v3/getting-started

Authentification : une simple clé API (API key) suffit pour tout ce
dont on a besoin ici (données PUBLIQUES d'une chaîne) — pas besoin
d'OAuth utilisateur, pas de token à rafraîchir. Étapes :
  1. Créer un projet sur Google Cloud Console.
  2. Activer "YouTube Data API v3" pour ce projet.
  3. Créer une clé API (API key), la restreindre à cette API.
  4. Ajouter la clé dans utils/settings.py (voir plus bas) et dans le
     fichier .env du bot — jamais en dur dans le code.

── Où mettre la clé (à ajouter toi-même dans utils/settings.py) ────
Le bot centralise déjà toute config/API key dans utils/settings.py via
pydantic-settings (regarde le champ `ng_api_key` existant, c'est le
même principe). Ajoute :

    youtube_api_key: str = ""

dans la classe Settings, puis `YOUTUBE_API_KEY=...` dans le `.env`.
Utilisation : `from utils.settings import settings` puis
`settings.youtube_api_key`.

── Endpoints à utiliser, et POURQUOI (quota) ────────────────────────
Le quota par défaut est de 10 000 unités/jour pour le projet entier
(cf. https://developers.google.com/youtube/v3/getting-started). Deux
pièges à éviter absolument :

  - `search.list` coûte cher en unités et est TENTANT pour "trouver les
    dernières vidéos d'une chaîne", mais NE PAS l'utiliser pour le
    polling régulier (ça viderait le quota très vite avec plusieurs
    connexions actives). Réserver `search.list` à validate_account()
    (un seul appel, pas répété).
  - À la place, pour fetch_events() : récupérer la playlist "uploads"
    de la chaîne (son ID se déduit de l'ID de chaîne, cf.
    _uploads_playlist_id ci-dessous) puis lister ses items avec
    `playlistItems.list` — beaucoup moins coûteux et suffisant pour
    détecter les nouvelles vidéos/shorts.
  - Pour distinguer une vidéo normale d'un Short et détecter un live en
    cours, un appel `videos.list` (part=snippet,liveStreamingDetails,
    contentDetails) sur les IDs renvoyés par playlistItems.list donne
    tout ce qu'il faut en un seul appel groupé (jusqu'à 50 IDs à la
    fois) — grouper les appels plutôt qu'un videos.list par vidéo.

Un Short se détecte en pratique par une durée <= 3 minutes ET un ratio
vertical (pas d'info fiable et documentée à 100% côté API — à affiner
en test réel ; commence par la durée, c'est le signal le plus robuste).

── event_type à produire (cf. MediaRule.event_type, libre côté DB) ──
  - "youtube.video_published"  : nouvelle vidéo standard.
  - "youtube.short_published"  : nouveau Short.
  - "youtube.live_started"     : passage en direct détecté.

── Anti-doublon ──────────────────────────────────────────────────────
external_id d'un MediaEvent = l'ID de vidéo YouTube (11 caractères,
ex: "dQw4w9WgXcQ"). C'est lui qui alimente MediaEvent.external_id ; ne
JAMAIS le modifier/reformater — c'est la clé anti-doublon (§9.1), gérée
par utils/medialink/event_manager.py, pas par ce fichier.

── check_status() ────────────────────────────────────────────────────
Un simple appel léger (ex: channels.list?part=id sur external_id) qui
réussit ou lève une exception suffit : pas besoin d'une vérification
complexe, juste confirmer "l'API répond et le compte existe toujours".
"""
from __future__ import annotations

from utils.medialink.event import MediaEvent
from utils.medialink.providers.base import (
    BaseMediaProvider,
    ProviderAccount,
    ProviderCapabilities,
)

_API_BASE_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeProvider(BaseMediaProvider):
    name = "youtube"
    platform = "youtube"
    capabilities = (
        ProviderCapabilities.NEW_POST
        | ProviderCapabilities.SHORT_FORM
        | ProviderCapabilities.LIVE_STATUS
    )

    def __init__(self) -> None:
        # TODO Bastien : stocker ici ce dont les autres méthodes auront
        # besoin — la clé API (settings.youtube_api_key), un client
        # HTTP réutilisable : httpx.AsyncClient (httpx>=0.27 est déjà
        # dans requirements.txt, pas besoin d'ajouter de dépendance), et
        # après connect(), l'external_id de la chaîne suivie + l'ID de
        # sa playlist "uploads" (cf. _uploads_playlist_id).
        self._channel_id: str | None = None
        self._uploads_playlist_id: str | None = None

    async def connect(self, external_id: str, **credentials: object) -> None:
        """external_id = l'ID de chaîne YouTube (commence par "UC...").

        TODO Bastien :
          1. Stocker self._channel_id = external_id.
          2. Appeler channels.list?part=contentDetails&id={external_id}
             pour récupérer contentDetails.relatedPlaylists.uploads —
             c'est l'ID de playlist à utiliser dans fetch_events().
             Le stocker dans self._uploads_playlist_id.
          3. Si le channel n'existe pas / la réponse est vide, lever une
             exception explicite (à définir : ex: un ProviderAuthError
             ou ProviderNotFoundError commun à tous les providers —
             discute avec l'équipe Core de où le mettre, probablement
             un nouveau utils/medialink/errors.py, pas encore créé dans
             ce squelette).
        """
        raise NotImplementedError("YouTubeProvider.connect()")

    async def disconnect(self) -> None:
        """TODO Bastien : fermer le client HTTP s'il y en a un (ex:
        await self._client.aclose()) — doit être sans effet si connect()
        n'a jamais été appelé (idempotent, cf. contrat de base.py)."""
        raise NotImplementedError("YouTubeProvider.disconnect()")

    async def validate_account(self, external_id: str) -> bool:
        """TODO Bastien : channels.list?part=id&id={external_id} (ou
        &forHandle={...} si on veut accepter un @handle en plus d'un ID
        de chaîne — à voir avec Paul pour l'UX de la vue d'ajout de
        connexion, cf. views/medialink/medialink_platforms_view.py).
        Renvoyer True si la réponse contient au moins un item, False
        sinon. NE PAS lever d'exception sur "compte introuvable" — c'est
        un cas normal (False), pas une erreur technique."""
        raise NotImplementedError("YouTubeProvider.validate_account()")

    async def get_account(self, external_id: str) -> ProviderAccount:
        """TODO Bastien : channels.list?part=snippet&id={external_id},
        puis mapper snippet.title → username, snippet.thumbnails.default
        .url → avatar_url, et construire l'URL publique
        (https://www.youtube.com/channel/{external_id}) → url."""
        raise NotImplementedError("YouTubeProvider.get_account()")

    async def fetch_events(self) -> list[MediaEvent]:
        """TODO Bastien — à implémenter dans cet ordre :
          1. playlistItems.list sur self._uploads_playlist_id
             (part=snippet, maxResults=10 suffit largement pour du
             polling régulier — on ne rate rien si le scheduler passe
             assez souvent, cf. utils/medialink/scheduler.py).
          2. Extraire les videoId des items renvoyés.
          3. Un seul appel videos.list groupé (part=snippet,
             contentDetails, liveStreamingDetails) sur ces IDs pour
             obtenir durée + statut live en un coup.
          4. Pour chaque vidéo : construire un MediaEvent avec
             external_id=videoId, event_type déterminé par la durée
             (short vs vidéo standard) et par liveStreamingDetails
             (live en cours → "youtube.live_started"), title, url
             (https://www.youtube.com/watch?v={videoId}), thumbnail,
             author (nom de la chaîne), published_at.
          5. NE PAS filtrer les doublons ici — c'est le rôle
             d'event_manager.ingest(), pas du Provider (cf. règle d'or,
             base.py). Renvoyer tout ce que l'API a renvoyé, même des
             vidéos déjà vues lors d'un appel précédent.
        """
        raise NotImplementedError("YouTubeProvider.fetch_events()")

    async def check_status(self) -> bool:
        """TODO Bastien : channels.list?part=id&id={self._channel_id},
        renvoyer True si ça répond avec un item, False (PAS d'exception)
        si le channel a disparu, une exception uniquement pour une vraie
        panne réseau/API (timeout, 5xx...)."""
        raise NotImplementedError("YouTubeProvider.check_status()")
