"""
utils/medialink/builders/announcement.py — assemble un MediaTemplate +
un MediaEvent en un message Discord concret (contenu texte + mise en
forme Components V2).

STRUCTURE FIXÉE (2026-09, avec Paul) : PAS un embed Discord — la mise en
forme structurée du template (`container_config` : accent_color/title/
description/thumbnail_enabled) est rendue en Components V2 (Container/
Section/Thumbnail/TextDisplay), au même titre que le reste du bot (cf.
utils/db/models/medialink_template.py pour la forme exacte du JSON, et
migration 91702a990fd8 pour l'historique du renommage embed_config →
container_config).

Tout le texte (content libre, title, description) passe par
utils/medialink/builders/placeholders.py::resolve() — jamais affiché
avec un placeholder non résolu ni une valeur vide (§7 : "ne jamais
afficher une valeur nulle").
"""
from __future__ import annotations

from dataclasses import dataclass, field

from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay, Thumbnail

from utils.db.models.medialink_template import MediaTemplate
from utils.medialink.builders.placeholders import resolve
from utils.medialink.event import MediaEvent

# Discord limite un ActionRow à 5 composants — s'applique aussi bien aux
# boutons qu'à un Select. TemplateEditView (medialink_announcement_view.py)
# doit empêcher d'ajouter un 6e bouton en amont ; ce plafond ici n'est
# qu'un filet de sécurité si jamais des données existantes en dépassent.
MAX_BUTTONS = 5


@dataclass(slots=True)
class BuiltAnnouncement:
    """Résultat prêt à envoyer via channel.send(**built.to_kwargs())."""

    content: str | None
    view: LayoutView | None = field(default=None)

    def to_kwargs(self) -> dict:
        kwargs: dict = {}
        if self.content:
            kwargs["content"] = self.content
        if self.view is not None:
            kwargs["view"] = self.view
        return kwargs


def build(template: MediaTemplate, event: MediaEvent) -> BuiltAnnouncement:
    """Résout le texte libre du template contre l'événement, et construit
    la mise en forme Components V2 à partir de container_config/buttons
    (si le template en a — un template sans container_config ni buttons
    reste un simple message texte, comme avant)."""
    content = resolve(template.content, event) if template.content else None
    view = _build_container_view(template, event)

    return BuiltAnnouncement(content=content, view=view)


def _resolved_or_none(text: str | None, event: MediaEvent) -> str | None:
    """resolve() puis strip() — un champ qui ne contient QUE des
    placeholders indisponibles pour cet événement (ex: title="{titre}"
    sans event.title) doit disparaître, pas s'afficher vide (§7)."""
    if not text:
        return None
    resolved = resolve(text, event).strip()
    return resolved or None


def _build_container_view(template: MediaTemplate, event: MediaEvent) -> LayoutView | None:
    config = template.container_config or {}
    buttons_config = (template.buttons or [])[:MAX_BUTTONS]

    title = _resolved_or_none(config.get("title"), event)
    description = _resolved_or_none(config.get("description"), event)
    thumbnail_enabled = bool(config.get("thumbnail_enabled"))
    accent_color = config.get("accent_color")

    has_text = bool(title or description)
    if not has_text and not buttons_config:
        # Rien de structuré à afficher — le template ne fait qu'un
        # message texte simple (content déjà géré côté build() ci-dessus).
        return None

    container = Container(accent_color=accent_color) if accent_color is not None else Container()

    if has_text:
        lines = []
        if title:
            lines.append(f"# {title}")
        if description:
            lines.append(description)
        text_display = TextDisplay("\n".join(lines))

        thumbnail_url = event.thumbnail if thumbnail_enabled else None
        if thumbnail_url:
            container.add_item(Section(text_display, accessory=Thumbnail(thumbnail_url)))
        else:
            container.add_item(text_display)

    link_buttons = [
        Button(style=ButtonStyle.link, label=btn["label"], url=btn["url"])
        for btn in buttons_config
        if btn.get("label") and btn.get("url")
    ]
    if link_buttons:
        if has_text:
            container.add_item(Separator())
        container.add_item(ActionRow(*link_buttons))

    if not container.children:
        return None

    view = LayoutView(timeout=None)
    view.add_item(container)
    return view