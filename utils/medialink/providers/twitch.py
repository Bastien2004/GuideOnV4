"""
utils/medialink/providers/twitch.py — Provider MEDIALINK pour Twitch.

═══════════════════════════════════════════════════════════════════════
 POUR BASTIEN — CE QUI EST ATTENDU DE TOI SUR CE FICHIER
═══════════════════════════════════════════════════════════════════════

Même principe que youtube.py (lis-le si tu ne l'as pas déjà fait, et
lis utils/medialink/providers/base.py en premier — c'est le contrat que
toutes les méthodes ci-dessous doivent respecter). Ici, la particularité
de Twitch par rapport à YouTube : PAS de notion de "vidéo publiée" à
détecter en V1, seulement "la chaîne vient de passer en direct" — donc
capabilities ne couvre que LIVE_STATUS pour l'instant (les clips/VODs
pourraient être une capability NEW_POST ajoutée plus tard, hors scope
immédiat).

── API utilisée ─────────────────────────────────────────────────────
Twitch Helix API. Docs officielles : https://dev.twitch.tv/docs/api/
Authentification : https://dev.twitch.tv/docs/authentication/

Contrairement à YouTube (simple clé API), Twitch demande un vrai flow
OAuth "App Access Token" (client credentials, PAS un token utilisateur —
on ne lit que du public, pas besoin qu'un streamer autorise quoi que ce
soit) :
  1. Créer une application sur https://dev.twitch.tv/console/apps
     → donne un client_id + client_secret.
  2. POST https://id.twitch.tv/oauth2/token avec client_id,
     client_secret, grant_type=client_credentials → renvoie un
     access_token + son expires_in (généralement ~60 jours).
  3. CE TOKEN EXPIRE — il faut le régénérer avant expiration (ou sur
     401), et Twitch recommande de le valider périodiquement via
     GET https://id.twitch.tv/oauth2/validate (~1x/heure, cf. leurs
     bonnes pratiques). C'est un vrai état à gérer (contrairement à la
     clé API YouTube qui ne change jamais) — voir _ensure_token() plus
     bas, c'est le morceau le plus délicat de ce provider.
  4. Chaque requête Helix a besoin de deux headers :
     "Client-Id: {client_id}" et "Authorization: Bearer {access_token}".

── Où mettre les secrets (à ajouter toi-même dans utils/settings.py) ──
Même principe que pour YouTube (regarde le champ `ng_api_key`
existant) :

    twitch_client_id: str = ""
    twitch_client_secret: str = ""

dans la classe Settings, puis TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET
dans le `.env`. L'access_token lui-même NE va PAS dans settings (il
expire et se régénère) — à garder en mémoire dans ce provider (ou dans
un petit cache partagé si plusieurs instances de TwitchProvider tournent
en même temps, à voir selon comment le Scheduler les instancie).

── Deux façons de détecter un live : laquelle choisir ? ─────────────
1. POLLING (ce que ce squelette suppose pour fetch_events(), le plus
   simple à mettre en route) : à chaque passage du scheduler, appeler
   GET https://api.twitch.tv/helix/streams?user_id={external_id}. Si un
   objet "stream" est renvoyé maintenant et qu'il n'y en avait PAS au
   passage précédent → nouvel événement "live démarré". Ça implique de
   retenir un état ("était en live ou non lors du dernier check") quelque
   part — voir la note dans fetch_events() ci-dessous, ce n'est PAS un
   détail à improviser au hasard.

2. EVENTSUB WEBHOOKS (la méthode recommandée par Twitch en production,
   temps réel au lieu d'un polling qui peut louper jusqu'à un intervalle
   de retard) : Twitch POST directement vers une URL publique à toi
   quand `stream.online`/`stream.offline` se produit. Ça demande une URL
   HTTPS publique avec un certificat valide — le bot a DÉJÀ un serveur
   FastAPI partagé (cogs/api/base.py, avec d'autres routes dans
   cogs/api/notation_api_app.py, staff_api.py...) où une route
   `cogs/api/medialink_webhook.py` pourrait être ajoutée sur ce modèle.
   C'est une meilleure solution à terme, mais c'est aussi plus de
   travail (vérification de signature Twitch, gestion des
   souscriptions EventSub par connexion...) — mon avis : commencer par
   le polling pour la Phase 0/V1 (ce squelette), et migrer vers EventSub
   dans une itération suivante une fois le pipeline de bout en bout
   validé. À trancher avec Paul si tu penses que ça vaut le coup de
   partir direct sur EventSub.

── event_type produit ────────────────────────────────────────────────
  - "twitch.live_started" : uniquement ça en V1 (cf. capabilities).

── Anti-doublon ──────────────────────────────────────────────────────
IMPORTANT — ne PAS utiliser user_id (l'ID de la chaîne) comme
external_id : il ne change jamais, donc un 2e live du même streamer
serait pris pour un doublon de la 1ère fois. Utiliser le champ `id` de
l'objet stream renvoyé par Get Streams — c'est l'ID de LA SESSION de
live en cours, différent à chaque fois qu'un streamer relance un live.
C'est lui qui doit remplir MediaEvent.external_id.

── check_status() ────────────────────────────────────────────────────
Vérifier que l'access_token est encore valide via
GET https://id.twitch.tv/oauth2/validate (renvoie 401 si expiré/révoqué
— dans ce cas, regénérer le token via _ensure_token() plutôt que de
renvoyer False directement, et ne renvoyer False que si la
régénération elle-même échoue).
"""
from __future__ import annotations

from utils.medialink.event import MediaEvent
from utils.medialink.providers.base import (
    BaseMediaProvider,
    ProviderAccount,
    ProviderCapabilities,
)

_AUTH_URL = "https://id.twitch.tv/oauth2/token"
_VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
_API_BASE_URL = "https://api.twitch.tv/helix"


class TwitchProvider(BaseMediaProvider):
    name = "twitch"
    platform = "twitch"
    capabilities = ProviderCapabilities.LIVE_STATUS

    def __init__(self) -> None:
        # TODO Bastien : stocker ici l'external_id (user_id Twitch) une
        # fois connect() appelé, l'access_token courant + sa date
        # d'expiration, et un client HTTP réutilisable (httpx>=0.27,
        # déjà dans requirements.txt).
        self._user_id: str | None = None
        self._access_token: str | None = None
        self._token_expires_at: float | None = None  # timestamp epoch
        # État nécessaire au polling (cf. fetch_events()) : était-on en
        # live lors du dernier appel ? Sans ça, impossible de savoir si
        # un stream renvoyé maintenant est un live QUI VIENT DE
        # commencer ou un live déjà en cours depuis 3 passages.
        self._was_live: bool = False

    async def _ensure_token(self) -> None:
        """TODO Bastien : si self._access_token est None ou expiré
        (comparer à self._token_expires_at), POST _AUTH_URL avec
        client_id=settings.twitch_client_id,
        client_secret=settings.twitch_client_secret,
        grant_type=client_credentials — puis stocker le nouveau token et
        calculer _token_expires_at = maintenant + expires_in (avec une
        marge de sécurité, ex: -300s, pour ne pas l'utiliser à la toute
        dernière seconde). Appelée en interne par connect() et par
        check_status() en cas de token expiré — pas exposée dans le
        contrat BaseMediaProvider, c'est un détail d'implémentation."""
        raise NotImplementedError("TwitchProvider._ensure_token()")

    async def connect(self, external_id: str, **credentials: object) -> None:
        """external_id = l'ID utilisateur Twitch (numérique, PAS le
        login/pseudo — si l'UI de connexion (§6) ne connaît que le
        pseudo, résous-le en ID via GET helix/users?login={pseudo} au
        moment de la création de la connexion, pas ici).

        TODO Bastien :
          1. self._user_id = external_id.
          2. await self._ensure_token().
          3. Optionnel mais recommandé : un premier appel Get Streams
             pour initialiser self._was_live à l'état réel actuel,
             plutôt que de partir de False par défaut (sinon un live
             déjà en cours au moment du connect() serait pris à tort
             pour "vient de démarrer" au prochain fetch_events())."""
        raise NotImplementedError("TwitchProvider.connect()")

    async def disconnect(self) -> None:
        """TODO Bastien : fermer le client HTTP s'il y en a un. Pas
        besoin de révoquer l'access_token (un App Access Token est
        partagé, pas propre à une connexion)."""
        raise NotImplementedError("TwitchProvider.disconnect()")

    async def validate_account(self, external_id: str) -> bool:
        """TODO Bastien : GET helix/users?login={external_id} (si on
        accepte un pseudo en entrée) ou ?id={external_id}. Renvoyer True
        si `data` contient au moins un élément, False sinon (PAS
        d'exception pour "compte introuvable")."""
        raise NotImplementedError("TwitchProvider.validate_account()")

    async def get_account(self, external_id: str) -> ProviderAccount:
        """TODO Bastien : GET helix/users?id={external_id} (ou ?login=),
        mapper data[0].display_name → username,
        data[0].profile_image_url → avatar_url,
        f"https://twitch.tv/{data[0]['login']}" → url. IMPORTANT :
        renvoyer aussi le VRAI user_id numérique dans ProviderAccount
        (via `raw`, ou en s'assurant que external_id renvoyé correspond
        à l'ID et pas au pseudo) pour que le code appelant puisse
        stocker le bon identifiant stable en base."""
        raise NotImplementedError("TwitchProvider.get_account()")

    async def fetch_events(self) -> list[MediaEvent]:
        """TODO Bastien :
          1. await self._ensure_token().
          2. GET helix/streams?user_id={self._user_id}.
          3. is_live_now = bool(data) (liste non vide).
          4. Si is_live_now and not self._was_live : construire UN
             MediaEvent (external_id=data[0]["id"] — cf. note
             anti-doublon en tête de fichier, PAS user_id — event_type=
             "twitch.live_started", title=data[0]["title"],
             url=f"https://twitch.tv/{data[0]['user_login']}",
             thumbnail=data[0]["thumbnail_url"].replace("{width}",
             "1280").replace("{height}", "720"), author=
             data[0]["user_name"], published_at=data[0]["started_at"]).
          5. Mettre à jour self._was_live = is_live_now AVANT de
             renvoyer (sinon un appel qui échoue à mi-chemin pourrait
             re-déclencher le même événement au passage suivant — pas
             grave en soi grâce à l'anti-doublon côté event_manager,
             mais autant être propre).
          6. Renvoyer [] si rien de nouveau (pas d'exception)."""
        raise NotImplementedError("TwitchProvider.fetch_events()")

    async def check_status(self) -> bool:
        """TODO Bastien : GET _VALIDATE_URL avec le header Authorization
        actuel. Si 401 : tenter self._ensure_token() puis réessayer une
        fois ; si ça échoue encore, renvoyer False. Sinon True."""
        raise NotImplementedError("TwitchProvider.check_status()")
