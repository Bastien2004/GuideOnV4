"""
utils/medialink/event.py — MediaEvent : l'objet métier en mémoire qu'un
Provider produit et que l'Event Manager fait circuler dans le pipeline
(cf. cahier des charges §4 "Modèle de données interne" et §8 "Pipeline :
Providers → Normalizer → MediaEvent → Event Manager → Rules →
Notification Engine → Discord").

Distinct de utils.db.models.medialink_event.MediaEventRecord, qui est la
PERSISTANCE de cet objet une fois traité. MediaEvent n'a pas vocation à
être stocké tel quel — il naît chez un Provider, traverse le Normalizer
(si le Provider ne rend pas déjà des champs homogènes), puis l'Event
Manager décide de le persister (anti-doublon, §9.1) et de le router
(Rules) avant que le Notification Engine ne le transforme en message
Discord.

"Règle d'or" du cahier (§8) : le Provider ne doit JAMAIS envoyer de
message Discord lui-même — il produit des MediaEvent, le Core décide.
Cette classe est donc volontairement dépourvue de toute méthode d'envoi.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class MediaEvent:
    """Un événement brut/normalisé produit par un Provider.

    Champs alignés sur §4 : platform, event_type, external_id (identifiant
    fourni par la plateforme — devient external_event_id une fois
    persisté), title, description, url, thumbnail, author, published_at.
    """

    platform: str
    event_type: str
    external_id: str

    title: str | None = None
    description: str | None = None
    url: str | None = None
    thumbnail: str | None = None
    author: str | None = None
    published_at: datetime | None = None

    # Rempli par l'Event Manager une fois la connexion identifiée — un
    # Provider ne connaît que le compte externe (ex: chaîne YouTube), pas
    # forcément à quelle MediaConnection interne ça correspond tant que
    # l'Event Manager ne l'a pas résolu.
    connection_id: int | None = None

    # Données brutes de la plateforme, conservées pour du debug/logs
    # (media_logs) sans avoir à tout remodéliser dans MediaEvent — jamais
    # utilisées directement par les Builders (§7 : ils ne consomment que
    # les champs normalisés ci-dessus).
    raw: dict = field(default_factory=dict)

    def dedupe_key(self) -> tuple[str, int | None, str]:
        """Clé anti-doublon (§9.1) : platform + connection_id + external_id.

        connection_id peut être None avant résolution par l'Event
        Manager — dans ce cas la clé n'est pas encore fiable pour un
        anti-doublon en base (cf. utils.medialink.event_manager, qui
        contraint (connection_id, external_event_id) une fois
        connection_id connu).
        """
        return (self.platform, self.connection_id, self.external_id)
