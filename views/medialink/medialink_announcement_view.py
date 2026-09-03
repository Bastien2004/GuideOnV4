"""
views/medialink/medialink_announcement_view.py — liste + édition des
MediaTemplate (§7, 4e concept "Announcement Template").

── MODE ACTUEL : TEXTE LIBRE UNIQUEMENT ─────────────────────────────
embed_config/buttons restent gérés uniquement côté CRUD
(utils/managers/medialink_manager.py) — pas encore d'UI pour les
éditer, cf. docstring d'origine de ce fichier : leur structure (champs,
couleur, thumbnail, boutons...) n'est pas figée avec Paul. Un template
créé ici n'a donc qu'un `content` (texte + placeholders) tant que ça
n'est pas cadré ; embed_config/buttons restent NULL. C'est un choix
délibéré pour ne pas construire une UI complexe sur un schéma instable
(cf. builders/announcement.py, qui a le même blocage côté envoi).

QUAND embed_config SERA CADRÉ AVEC PAUL — à faire à ce moment-là :
  - Ajouter un écran (ou une section de TemplateEditView) pour éditer
    embed_config (titre, description, couleur, thumbnail on/off...) et
    buttons, avec un aperçu si possible.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import Button, Container, Section, Separator, TextDisplay

from utils.managers import medialink_manager as medialink_mgr
from utils.medialink.builders.placeholders import PLACEHOLDER_FIELDS
from views._components.base_view import BaseLayoutView


class CreateTemplateModal(discord.ui.Modal):
    """Création d'un template — juste un nom pour l'instant, le texte
    s'édite ensuite depuis TemplateEditView (cf. EditContentModal)."""

    def __init__(self, *, guild_id: int, owner_id: int):
        super().__init__(title="Créer un template")
        self.guild_id = guild_id
        self.owner_id = owner_id

        self.name_input = discord.ui.TextInput(
            label="Nom du template",
            placeholder="Ex : Nouvelle vidéo YouTube",
            required=True,
            max_length=100,
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        template = await medialink_mgr.add_template(self.guild_id, self.name_input.value.strip())

        view = TemplateEditView(template=template, owner_id=self.owner_id)
        await interaction.response.edit_message(view=view)


class EditContentModal(discord.ui.Modal):
    """Édition du texte libre (`content`) d'un template existant."""

    def __init__(self, *, template: dict, owner_id: int):
        super().__init__(title="Modifier le texte du template")
        self.template = template
        self.owner_id = owner_id

        self.content_input = discord.ui.TextInput(
            label="Texte de l'annonce",
            style=discord.TextStyle.paragraph,
            placeholder="Ex : 🎬 Nouvelle vidéo de {auteur} : {titre}",
            default=template.get("content") or "",
            required=False,
            max_length=2000,
        )
        self.add_item(self.content_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        updated = await medialink_mgr.update_template(
            self.template["id"], content=self.content_input.value.strip() or None,
        )
        if updated is None:
            # Le template a été supprimé entre l'ouverture du Modal et sa
            # validation (concurrence) — retour propre à la liste plutôt
            # qu'un crash sur un template qui n'existe plus.
            view = await TemplateListView.build(guild_id=self.template["guild_id"], owner_id=self.owner_id)
            await interaction.response.edit_message(view=view)
            return

        view = TemplateEditView(template=updated, owner_id=self.owner_id)
        await interaction.response.edit_message(view=view)


class TemplateListView(BaseLayoutView):
    """Liste des templates d'une guild — point d'entrée (§16, accessible
    depuis le dashboard, cf. medialink_dashboard_view.py)."""

    def __init__(self, *, guild_id: int, owner_id: int, templates: list[dict]):
        super().__init__(owner_id=owner_id, timeout=300)
        self.guild_id = guild_id
        self.templates = templates
        self._build()

    @classmethod
    async def build(cls, *, guild_id: int, owner_id: int) -> "TemplateListView":
        templates = await medialink_mgr.list_templates(guild_id)
        return cls(guild_id=guild_id, owner_id=owner_id, templates=templates)

    def _build(self) -> None:
        container = Container()
        container.add_item(TextDisplay("# 📝 Templates MEDIALINK"))
        container.add_item(Separator())

        if not self.templates:
            container.add_item(TextDisplay("*Aucun template créé pour l'instant.*"))
        else:
            for tpl in self.templates:
                edit_btn = Button(label="Modifier", style=ButtonStyle.secondary)
                edit_btn.callback = self._cb_open_template(tpl["id"])
                container.add_item(Section(
                    TextDisplay(f"➥ **{tpl['name']}**"),
                    accessory=edit_btn,
                ))

        container.add_item(Separator())
        create_btn = Button(label="Créer un template", style=ButtonStyle.primary, emoji="➕")
        create_btn.callback = self._cb_create_template
        container.add_item(create_btn)

        back_btn = Button(label="Retour au dashboard", style=ButtonStyle.secondary)
        back_btn.callback = self._cb_back
        container.add_item(back_btn)

        self.add_item(container)

    def _cb_open_template(self, template_id: int):
        async def _callback(interaction: discord.Interaction) -> None:
            template = next((t for t in self.templates if t["id"] == template_id), None)
            if template is None:
                return
            view = TemplateEditView(template=template, owner_id=self.owner_id)
            await self.push_update(interaction, view=view)
        return _callback

    async def _cb_create_template(self, interaction: discord.Interaction) -> None:
        modal = CreateTemplateModal(guild_id=self.guild_id, owner_id=self.owner_id)
        await interaction.response.send_modal(modal)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        from views.medialink.medialink_dashboard_view import MediaLinkDashboardView

        view = await MediaLinkDashboardView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)


class TemplateEditView(BaseLayoutView):
    """Édition d'un template — texte libre uniquement pour l'instant,
    cf. docstring de module."""

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

        container.add_item(Separator())
        delete_btn = Button(label="Supprimer le template", style=ButtonStyle.danger, emoji="🗑️")
        delete_btn.callback = self._cb_delete_template
        container.add_item(delete_btn)

        back_btn = Button(label="Retour à la liste", style=ButtonStyle.secondary)
        back_btn.callback = self._cb_back
        container.add_item(back_btn)

        self.add_item(container)

    async def _cb_edit_content(self, interaction: discord.Interaction) -> None:
        modal = EditContentModal(template=self.template, owner_id=self.owner_id)
        await interaction.response.send_modal(modal)

    async def _cb_delete_template(self, interaction: discord.Interaction) -> None:
        await medialink_mgr.remove_template(self.template["id"])

        view = await TemplateListView.build(guild_id=self.template["guild_id"], owner_id=self.owner_id)
        await self.push_update(interaction, view=view)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        view = await TemplateListView.build(guild_id=self.template["guild_id"], owner_id=self.owner_id)
        await self.push_update(interaction, view=view)