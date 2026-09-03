"""
utils/medialink/providers/tiktok.py — Provider MEDIALINK pour TikTok.

═══════════════════════════════════════════════════════════════════════
 ⚠️ POUR BASTIEN (ET PAUL) — CE FICHIER EST BLOQUÉ, PAS UN SIMPLE TODO
═══════════════════════════════════════════════════════════════════════

Contrairement à youtube.py / twitch.py / reddit.py, ce n'est PAS "voici
les endpoints, remplace les NotImplementedError" : j'ai vérifié
(septembre 2026) qu'il n'existe PAS d'API TikTok officielle qui permette
à une application tierce de lire les nouveaux posts d'un compte PUBLIC
qu'elle ne possède pas. C'est une vraie limite de la plateforme, pas un
manque de recherche de ma part — à décider AVANT d'écrire du code ici,
sinon le temps de Bastien part sur une fausse piste.

── Ce qui existe officiellement chez TikTok, et pourquoi ça ne suffit pas ──

  • Content Posting API — permet à un compte de PUBLIER du contenu sur
    SON PROPRE compte TikTok (après que l'utilisateur autorise l'app en
    OAuth). Ne permet PAS de lire les posts d'un autre compte. Inutile
    pour MEDIALINK, qui doit surveiller des comptes qui ne sont pas
    forcément liés au bot.
    https://developers.tiktok.com/docs/en/content-sharing-guidelines

  • Display API / Login Kit — donne accès aux données de L'UTILISATEUR
    QUI S'EST CONNECTÉ avec son propre compte (comme "Se connecter avec
    TikTok"). Même limite : ça ne couvre que le compte qui a
    explicitement autorisé l'app, pas un compte tiers qu'on veut
    seulement suivre en lecture.

  • Research API — donne un accès en lecture plus large (y compris à
    du contenu public), MAIS réservé aux chercheurs académiques
    qualifiés après candidature et validation par TikTok — pas conçu
    pour un usage commercial/bot Discord, accès non garanti même en
    candidatant.

En clair : il n'y a pas de "clé API publique" équivalente à YouTube ici.

── Les options réalistes (à choisir avec Paul, pas à décider seul) ──

  1. Service tiers payant d'agrégation TikTok (des sociétés vendent un
     accès API à des données TikTok qu'elles collectent elles-mêmes,
     en s'appuyant sur des méthodes non officielles). Avantage : API
     propre, pas de scraping à maintenir soi-même. Inconvénients :
     coût récurrent (abonnement/pay-per-request), dépendance à un
     prestataire tiers dont le service peut s'arrêter si TikTok change
     ses protections, et un flou juridique/ToS à faire porter par ce
     prestataire plutôt que par GuideOn directement (à vérifier
     précisément leurs conditions avant de s'engager).

  2. Scraping "maison" des pages publiques TikTok. Fragile par
     construction (TikTok fait activement la chasse au scraping, la
     structure des pages change sans préavis), demande un entretien
     continu, et est explicitement contraire aux conditions
     d'utilisation de TikTok — risque réel de blocage d'IP/de compte
     si c'est fait au nom du bot. Je déconseille cette option pour un
     produit qui doit tourner de façon fiable en continu.

  3. Ne PAS automatiser TikTok pour l'instant : le lister comme
     "Bientôt disponible" dans l'UI (le dashboard automod du bot a
     déjà ce pattern — voir `"available": False` dans
     views/mod/automod_dashboard_view.py, _SYSTEMS) et livrer
     YouTube/Twitch/Reddit d'abord, le temps de trancher.

Mon avis technique : commencer par l'option 3 (ne pas bloquer les 3
autres plateformes sur celle-ci), pendant que Paul évalue un prestataire
pour l'option 1 si TikTok reste une priorité produit. Ce fichier reste
en place comme point d'ancrage : dès qu'une méthode d'accès est choisie,
seul CE fichier change (le contrat BaseMediaProvider ne bouge pas, donc
rien d'autre dans le pipeline n'a besoin d'être retouché).

── Ce qui EST fait ci-dessous ────────────────────────────────────────
La classe respecte le contrat BaseMediaProvider (capabilities déclarées
pour que le reste du code sache ce que TikTok est censé fournir une fois
débloqué), mais toutes les méthodes lèvent une exception explicite et
PARLANTE plutôt que NotImplementedError nu — pour qu'un appel accidentel
à ce Provider avant décision échoue avec un message clair au lieu d'un
comportement silencieux ou d'un crash générique.
"""
from __future__ import annotations

from utils.medialink.event import MediaEvent
from utils.medialink.providers.base import (
    BaseMediaProvider,
    ProviderAccount,
    ProviderCapabilities,
)


class TikTokNotAvailableError(NotImplementedError):
    """Levée par toutes les méthodes de TikTokProvider tant qu'aucune
    méthode d'accès aux données publiques TikTok n'a été choisie avec
    Paul — cf. docstring de module pour les options."""

    def __init__(self, method_name: str) -> None:
        super().__init__(
            f"TikTokProvider.{method_name}() : aucune source de données "
            "TikTok n'est branchée pour l'instant. TikTok n'a pas d'API "
            "publique de lecture pour des comptes tiers (cf. docstring "
            "de utils/medialink/providers/tiktok.py) — décision produit "
            "nécessaire (prestataire tiers payant, ou report de TikTok) "
            "avant d'implémenter ce Provider."
        )


class TikTokProvider(BaseMediaProvider):
    name = "tiktok"
    platform = "tiktok"
    # Déclaré pour documenter l'INTENTION (ce que TikTok devrait couvrir
    # une fois débloqué), pas parce que c'est fonctionnel aujourd'hui.
    capabilities = ProviderCapabilities.NEW_POST | ProviderCapabilities.SHORT_FORM

    async def connect(self, external_id: str, **credentials: object) -> None:
        raise TikTokNotAvailableError("connect")

    async def disconnect(self) -> None:
        raise TikTokNotAvailableError("disconnect")

    async def validate_account(self, external_id: str) -> bool:
        raise TikTokNotAvailableError("validate_account")

    async def get_account(self, external_id: str) -> ProviderAccount:
        raise TikTokNotAvailableError("get_account")

    async def fetch_events(self) -> list[MediaEvent]:
        raise TikTokNotAvailableError("fetch_events")

    async def check_status(self) -> bool:
        raise TikTokNotAvailableError("check_status")
