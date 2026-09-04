"""
utils/medialink/builders/announcement.py — Assemble un MediaTemplate + un MediaEvent en un message Discord.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay, Thumbnail

from utils.db.models.medialink_template import MediaTemplate
from utils.medialink.builders.placeholders import resolve
from utils.medialink.event import MediaEvent


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


def build(template: MediaTemplate, event: MediaEvent, *, mention: str | None = None) -> BuiltAnnouncement:
    """Contruit un BuiltAnnouncement à partir d'un MediaTemplate + un MediaEvent."""

    content = resolve(template.content, event) if template.content else None
    if mention:
        content = f"{mention} {content}" if content else mention

    container = _build_container(template, event)

    if container is None:
        return BuiltAnnouncement(content=content, view=None)

    view = LayoutView(timeout=None)
    if content:
        view.add_item(TextDisplay(content))
    view.add_item(container)
    return BuiltAnnouncement(content=None, view=view)


def _resolved_or_none(text: str | None, event: MediaEvent) -> str | None:
    """Gestion des placeholders."""

    if not text:
        return None
    resolved = resolve(text, event).strip()
    return resolved or None


def _build_container(template: MediaTemplate, event: MediaEvent) -> Container | None:
    """Construit le Container (titre/description/vignette/boutons)."""

    config = template.container_config or {}
    buttons_config = (template.buttons or [])[:MAX_BUTTONS]

    title = _resolved_or_none(config.get("title"), event)
    description = _resolved_or_none(config.get("description"), event)
    thumbnail_enabled = bool(config.get("thumbnail_enabled"))
    accent_color = config.get("accent_color")

    has_text = bool(title or description)
    if not has_text and not buttons_config:
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

    return container