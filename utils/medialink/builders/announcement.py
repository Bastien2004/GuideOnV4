"""
utils/medialink/builders/announcement.py — assemble un MediaTemplate +
un MediaEvent en un message Discord concret (contenu texte + embed).

STUB léger : dépend de la structure définitive d'embed_config (JSON,
cf. utils/db/models/medialink_template.py) qui n'est pas encore figée
avec Paul. Le contrat de fonction ci-dessous est stable et peut être
codé contre dès que la forme d'embed_config est validée.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import discord

from utils.db.models.medialink_template import MediaTemplate
from utils.medialink.builders.placeholders import resolve
from utils.medialink.event import MediaEvent


@dataclass(slots=True)
class BuiltAnnouncement:
    """Résultat prêt à envoyer via channel.send(**built.to_kwargs())."""

    content: str | None
    embed: discord.Embed | None = None
    view: discord.ui.View | None = field(default=None)

    def to_kwargs(self) -> dict:
        kwargs: dict = {}
        if self.content:
            kwargs["content"] = self.content
        if self.embed is not None:
            kwargs["embed"] = self.embed
        if self.view is not None:
            kwargs["view"] = self.view
        return kwargs


def build(template: MediaTemplate, event: MediaEvent) -> BuiltAnnouncement:
    """Résout le texte libre du template contre l'événement ; l'embed et
    les boutons (JSON) restent à implémenter une fois embed_config figé
    — cf. docstring de module."""
    content = resolve(template.content, event) if template.content else None

    if template.embed_config:
        raise NotImplementedError(
            "announcement.build() : rendu d'embed_config non implémenté "
            "(structure JSON pas encore figée, cf. medialink_template.py)"
        )

    return BuiltAnnouncement(content=content)
