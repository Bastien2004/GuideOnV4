"""
views/medialink/medialink_announcement_view.py — édition d'un
MediaTemplate (texte + embed_config + boutons), §7.

STUB : dépend de la structure définitive d'embed_config (cf.
utils/medialink/builders/announcement.py et
utils/db/models/medialink_template.py) — pas encore figée avec Paul. Un
premier jet réaliste ne devrait couvrir QUE l'édition du texte libre
(`content`, via Modal) tant que la partie embed n'est pas cadrée, plutôt
que de construire une UI complexe sur un schéma encore instable.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import Button, Container, Section, Separator, TextDisplay

from utils.medialink.builders.placeholders import PLACEHOLDER_FIELDS
from views._components.base_view import BaseLayoutView


class TemplateEditView(BaseLayoutView):
    """Édition d'un template — pour l'instant, texte libre uniquement."""

    def __init__(self, *, template: dict, owner_id: int):
        super().__init__(owner_id=owner_id, timeout=300)
        self.template = template
        self._build()

    def _build(self) -> None:
        container = Container()
        container.add_item(TextDisplay(f"# ✏️ Template — {self.template.get('name', 'Sans nom')}"))
        container.add_item(Separator())

        placeholders_help = ", ".join(f"{{{p}}}" for p in PLACEHOLDER_FIELDS)
        container.add_item(TextDisplay(f"-# Placeholders disponibles : {placeholders_help}"))

        content = self.template.get("content") or "*(vide)*"
        edit_btn = Button(label="Modifier le texte", style=ButtonStyle.primary)
        edit_btn.callback = self._cb_edit_content
        container.add_item(Section(TextDisplay(f"Texte actuel :\n>>> {content}"), accessory=edit_btn))

        self.add_item(container)

    async def _cb_edit_content(self, interaction: discord.Interaction) -> None:
        # TODO : ouvrir un discord.ui.Modal pour éditer `content`, puis
        # persister (le CRUD des templates n'est pas encore dans
        # utils/managers/medialink_manager.py, cf. ce fichier).
        raise NotImplementedError(
            "announcement._cb_edit_content — Modal + CRUD templates (roadmap V1)"
        )
