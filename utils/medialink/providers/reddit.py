"""
utils/medialink/providers/reddit.py — Provider MEDIALINK pour Reddit.

═══════════════════════════════════════════════════════════════════════
 POUR BASTIEN — CE QUI EST ATTENDU DE TOI SUR CE FICHIER
═══════════════════════════════════════════════════════════════════════

Même principe que youtube.py/twitch.py — lis d'abord
utils/medialink/providers/base.py (le contrat), puis remplace chaque
NotImplementedError par du vrai code, sans changer les signatures.

── ⚠️ POINT OUVERT À CONFIRMER AVEC PAUL AVANT DE CODER ─────────────
Le cahier des charges parle de suivre des "comptes/chaînes" par
plateforme, mais pour Reddit ça peut vouloir dire deux choses
différentes :
  (a) suivre un SUBREDDIT (annoncer les nouveaux posts de r/xxx), ou
  (b) suivre un UTILISATEUR (annoncer les nouveaux posts d'un
      redditor précis, u/xxx).
Ce squelette part sur (a) — suivi de subreddit — car c'est l'usage le
plus courant pour ce genre de bot d'annonce, et parce que ça se
rapproche le plus de "chaîne YouTube"/"chaîne Twitch" (un espace, pas
une personne). MAIS je n'ai pas de confirmation explicite de Paul
là-dessus — À VÉRIFIER avant d'aller loin dans l'implémentation. Si
c'est finalement un suivi d'utilisateur, le changement est mineur (même
appel API, juste /user/{nom}/submitted.json au lieu de /r/{nom}/new.json)
mais autant le savoir avant de coder les deux méthodes qui en dépendent
(fetch_events, validate_account, get_account).

── API utilisée ─────────────────────────────────────────────────────
Reddit Data API (OAuth). Docs : https://www.reddit.com/dev/api/ et
https://github.com/reddit-archive/reddit/wiki/OAuth2

Authentification : un "script app" en OAuth2 client_credentials — comme
Twitch, PAS un login utilisateur (on ne lit que du contenu public) :
  1. Créer une app sur https://www.reddit.com/prefs/apps (type
     "script" ou équivalent app-only selon ce que propose l'interface
     au moment où tu t'y colles) → client_id + client_secret.
  2. POST https://www.reddit.com/api/v1/access_token avec Basic Auth
     (client_id:client_secret) et grant_type=client_credentials dans le
     corps → renvoie un access_token + expires_in (~1h, à régénérer
     comme pour Twitch, cf. _ensure_token()).
  3. ⚠️ OBLIGATOIRE : chaque requête doit avoir un header User-Agent
     descriptif et unique, format recommandé par Reddit :
     "platform:app_id:version (by /u/ton_pseudo_reddit)" — ex:
     "discord-bot:guideon-medialink:1.0 (by /u/xxx)". Sans ça, Reddit
     peut throttle ou bloquer les requêtes silencieusement.
  4. Une fois le token obtenu, utiliser le domaine
     https://oauth.reddit.com/... (PAS www.reddit.com) pour les appels
     de lecture, avec "Authorization: Bearer {access_token}" + le
     User-Agent ci-dessus.

── Rate limit ────────────────────────────────────────────────────────
100 requêtes/minute par client OAuth, moyennées sur une fenêtre de 10
minutes (donc des pics courts sont tolérés). Avec plusieurs subreddits
suivis, le Scheduler (utils/medialink/scheduler.py) doit répartir ses
appels dans le temps plutôt que tout interroger d'un coup si le nombre
de connexions Reddit devient grand — pas un problème pour un nombre
raisonnable de connexions, à garder en tête si ça grossit beaucoup.

── Où mettre les secrets (à ajouter toi-même dans utils/settings.py) ──
Même principe que YouTube/Twitch (regarde `ng_api_key`) :

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "discord-bot:guideon-medialink:1.0"

puis REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT dans
le `.env`. L'access_token, comme pour Twitch, ne va PAS dans settings
(il expire) — à garder en mémoire dans ce provider.

── event_type produit ────────────────────────────────────────────────
  - "reddit.post_published" : nouveau post dans le subreddit suivi.
  (COMMENTS — nouveaux commentaires — est listé dans
  ProviderCapabilities mais volontairement PAS activé ici : hors scope
  immédiat, le cahier ne le demande pas explicitement.)

── Anti-doublon ──────────────────────────────────────────────────────
external_id = l'ID du post SANS le préfixe de type Reddit (Reddit
renvoie des ID du type "t3_1abcde" pour un post — "t3_" est le préfixe
de type "link/post" ; ne garder que la partie après "t3_", ou garder le
préfixe complet du moment que c'est TOUJOURS fait de la même façon —
l'important est la cohérence, pas le format exact).

── check_status() ────────────────────────────────────────────────────
Un appel léger sur /r/{subreddit}/about.json suffit (renvoie 404 si le
subreddit a été supprimé/banni entretemps, 403 s'il est devenu privé —
ces deux cas → False, pas une exception).
"""
from __future__ import annotations

from utils.medialink.event import MediaEvent
from utils.medialink.providers.base import (
    BaseMediaProvider,
    ProviderAccount,
    ProviderCapabilities,
)

_AUTH_URL = "https://www.reddit.com/api/v1/access_token"
_API_BASE_URL = "https://oauth.reddit.com"


class RedditProvider(BaseMediaProvider):
    name = "reddit"
    platform = "reddit"
    capabilities = ProviderCapabilities.NEW_POST

    def __init__(self) -> None:
        # TODO Bastien : external_id = nom du subreddit suivi (SANS le
        # préfixe "r/" — à normaliser dès l'entrée, ex: retirer "r/" si
        # l'utilisateur le tape dans la vue de configuration), token +
        # expiration comme pour Twitch, client HTTP réutilisable
        # (httpx>=0.27, déjà dans requirements.txt).
        self._subreddit: str | None = None
        self._access_token: str | None = None
        self._token_expires_at: float | None = None  # timestamp epoch
        # Nécessaire pour ne pas ré-annoncer tout l'historique du
        # subreddit au premier passage : à défaut d'un curseur officiel
        # simple côté Reddit pour ce cas d'usage, garder le plus récent
        # published_at déjà vu et ignorer tout ce qui est plus ancien ou
        # égal lors du fetch suivant (cf. fetch_events()).
        self._last_seen_created_utc: float | None = None

    async def _ensure_token(self) -> None:
        """TODO Bastien : même logique que
        TwitchProvider._ensure_token() — regénérer si absent/expiré,
        via POST _AUTH_URL en Basic Auth (client_id, client_secret) +
        grant_type=client_credentials, avec le header User-Agent
        (settings.reddit_user_agent) déjà présent sur CET appel aussi
        (Reddit l'exige partout, y compris pour obtenir le token)."""
        raise NotImplementedError("RedditProvider._ensure_token()")

    async def connect(self, external_id: str, **credentials: object) -> None:
        """external_id = nom du subreddit (cf. note en tête de fichier
        sur subreddit vs utilisateur — à confirmer avec Paul).

        TODO Bastien :
          1. self._subreddit = external_id.lstrip("r/").strip("/") (ou
             équivalent — normaliser pour accepter "r/xxx", "/r/xxx" et
             "xxx" indifféremment côté saisie utilisateur).
          2. await self._ensure_token().
          3. Optionnel mais recommandé (même raisonnement que pour
             Twitch) : un premier appel pour initialiser
             self._last_seen_created_utc à l'horodatage du post le plus
             récent AU MOMENT du connect(), pour ne pas annoncer tout
             l'historique existant au premier fetch_events()."""
        raise NotImplementedError("RedditProvider.connect()")

    async def disconnect(self) -> None:
        """TODO Bastien : fermer le client HTTP s'il y en a un."""
        raise NotImplementedError("RedditProvider.disconnect()")

    async def validate_account(self, external_id: str) -> bool:
        """TODO Bastien : GET {_API_BASE_URL}/r/{external_id}/about.json
        (avec token + User-Agent). Renvoyer True si la réponse contient
        bien des données de subreddit (data.display_name présent),
        False si 404 (n'existe pas) ou 403 (privé/banni) — PAS
        d'exception pour ces deux cas, ce sont des réponses normales de
        l'API, pas des pannes."""
        raise NotImplementedError("RedditProvider.validate_account()")

    async def get_account(self, external_id: str) -> ProviderAccount:
        """TODO Bastien : même endpoint about.json, mapper
        data.display_name_prefixed (ex: "r/python") → username,
        data.community_icon ou data.icon_img → avatar_url (les deux
        peuvent être vides, prévoir un fallback None proprement),
        f"https://reddit.com{data.url}" → url."""
        raise NotImplementedError("RedditProvider.get_account()")

    async def fetch_events(self) -> list[MediaEvent]:
        """TODO Bastien :
          1. await self._ensure_token().
          2. GET {_API_BASE_URL}/r/{self._subreddit}/new.json?limit=25
             (triés du plus récent au plus ancien par défaut).
          3. Pour chaque item de data.children où data.created_utc >
             (self._last_seen_created_utc ou 0) : construire un
             MediaEvent (external_id=le champ "id" du post — cf. note
             anti-doublon en tête de fichier, event_type=
             "reddit.post_published", title=data.title,
             url=f"https://reddit.com{data.permalink}", thumbnail=
             data.thumbnail SI c'est une vraie URL http(s) — Reddit
             renvoie parfois "self"/"default"/"nsfw"/"spoiler" comme
             valeur littérale à la place d'une URL, à filtrer sinon on
             affiche un thumbnail invalide, author=data.author,
             published_at=datetime.fromtimestamp(data.created_utc,
             tz=timezone.utc)).
          4. Mettre à jour self._last_seen_created_utc au
             created_utc le plus grand rencontré, APRÈS avoir construit
             tous les MediaEvent (pas au fur et à mesure, pour éviter un
             état à moitié mis à jour si une exception survient au
             milieu du parcours).
          5. Renvoyer la liste (vide si rien de nouveau) — pas
             d'exception pour "rien de nouveau", c'est le cas normal."""
        raise NotImplementedError("RedditProvider.fetch_events()")

    async def check_status(self) -> bool:
        """TODO Bastien : GET about.json comme dans validate_account(),
        renvoyer True/False selon le code retour — régénérer le token
        via _ensure_token() d'abord si le dernier appel a échoué en 401."""
        raise NotImplementedError("RedditProvider.check_status()")
