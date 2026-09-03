"""
utils/medialink/notification.py — Notification Engine (§8) : dernier
maillon du pipeline avant Discord. Prend un MediaEvent + une MediaRule
(+ son MediaTemplate le cas échéant) et produit/envoie le message
d'annonce final.

C'est le SEUL endroit du Core qui a le droit de parler à l'API Discord
(envoyer un message) — cohérent avec la règle d'or inverse côté
Provider (§8 : "le Provider ne doit jamais envoyer de message Discord").

STUB volontairement léger (roadmap V1) : dépend des Builders
(utils/medialink/builders/), eux-mêmes pas encore fixés en détail avec
Paul. Le contrat ci-dessous suffit pour que processor.py puisse être
écrit contre une interface stable.
"""
from __future__ import annotations

from utils.db.models.medialink_rule import MediaRule
from utils.medialink.event_manager import RoutedEvent


async def send(routed_event: RoutedEvent, rule: MediaRule) -> None:
    """Construit l'annonce (via builders.announcement/container/
    placeholders) pour `routed_event.event` selon le template de `rule`,
    puis l'envoie dans rule.channel_id (avec mention de
    rule.mention_role_id si défini).

    Non implémenté dans ce squelette — dépend de
    utils/medialink/builders/announcement.py et container.py
    (Components V2, cf. le reste du bot : Container/Section/TextDisplay
    comme dans views/join_to_create/...).
    """
    raise NotImplementedError("notification.send() — à implémenter (roadmap V1)")
