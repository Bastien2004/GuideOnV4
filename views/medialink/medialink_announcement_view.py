"""
views/medialink/medialink_announcement_view.py — Gestion des templates d'annonces.
"""

from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container, info_container, send_ephemeral
from utils.db.models.medialink_template import MediaTemplate
from utils.managers import medialink_manager as medialink_mgr

from utils.medialink.builders import announcement as announcement_builder
from utils.medialink.builders.announcement import MAX_BUTTONS
from utils.medialink.builders.placeholders import PLACEHOLDER_FIELDS
from utils.medialink.event import MediaEvent
from views._components.base_view import BaseLayoutView


# ============================================================
# 🥰 Emojis
# ============================================================

EMOJI_ADD = "<:plus:1495444111505752154>"
EMOJI_EDIT = "<:modifier:1495444144712192003>"
EMOJI_DELETE = "<:supprimer:1495444051623809075>"
EMOJI_BACK = "<:retour:1515658955190308995>"


_PREVIEW_EVENT = MediaEvent(
    platform="Youtube",
    event_type="new_post",
    external_id="preview",
    title="Titre de la vidéo (exemple)",
    description="Description de l'événement, utilisée pour prévisualiser le rendu du template (exemple).",
    url="https://youtube.com",
    thumbnail="https://placehold.co/480x270?text=Vignette",
    author="Nom de la chaîne (exemple)",
)


# ============================================================
# 💻 Création d'un template
# ============================================================

class CreateTemplateModal(discord.ui.Modal):
    """Création d'un template."""

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


# ============================================================
# 🖍️ Edition du texte libre
# ============================================================

class EditContentModal(discord.ui.Modal):
    """Édition du texte libre (`content`) d'un template existant."""

    def __init__(self, *, template: dict, owner_id: int):
        super().__init__(title="Modifier le texte")
        self.template = template
        self.owner_id = owner_id

        self.content_input = discord.ui.TextInput(
            label="Texte de l'annonce",
            style=discord.TextStyle.paragraph,
            placeholder="Ex : <:clip:1552026756893114440> Nouvelle vidéo de {auteur} : {titre}",
            default=template.get("content") or "",
            required=False,
            max_length=2000,
        )
        self.add_item(self.content_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        updated = await medialink_mgr.update_template(self.template["id"], content=self.content_input.value.strip() or None)

        if updated is None:
            view = await TemplateListView.build(guild_id=self.template["guild_id"], owner_id=self.owner_id)
            await interaction.response.edit_message(view=view)
            return

        view = TemplateEditView(template=updated, owner_id=self.owner_id)
        await interaction.response.edit_message(view=view)


# ============================================================
# 🖍️ Edition du container
# ============================================================

class EditContainerModal(discord.ui.Modal):
    """Édition du container."""

    def __init__(self, *, template: dict, owner_id: int):
        super().__init__(title="Modifier la mise en forme")
        self.template = template
        self.owner_id = owner_id
        config = template.get("container_config") or {}

        self.title_input = discord.ui.TextInput(
            label="Titre (optionnel)",
            placeholder="Ex : <:clip:1552026756893114440> Nouvelle vidéo",
            default=config.get("title") or "",
            required=False,
            max_length=256,
        )
        self.description_input = discord.ui.TextInput(
            label="Description (optionnelle)",
            style=discord.TextStyle.paragraph,
            placeholder="Ex : {auteur} vient de publier {titre} !",
            default=config.get("description") or "",
            required=False,
            max_length=1000,
        )
        accent_color = config.get("accent_color")
        self.color_input = discord.ui.TextInput(
            label="Couleur (hex, optionnel)",
            placeholder="Ex : #5865F2",
            default=f"#{accent_color:06X}" if isinstance(accent_color, int) else "",
            required=False,
            max_length=7,
        )
        self.add_item(self.title_input)
        self.add_item(self.description_input)
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw_color = self.color_input.value.strip().lstrip("#")
        accent_color: int | None = None
        if raw_color:
            try:
                accent_color = int(raw_color, 16)
                if not (0 <= accent_color <= 0xFFFFFF):
                    raise ValueError
            except ValueError:
                await interaction.response.send_message(
                    view=error_container("Couleur **invalide** — utilise de l'__hexadécimal__ , ex : `#5865F2`."),
                    ephemeral=True,
                )
                return

        config = dict(self.template.get("container_config") or {})
        config["title"] = self.title_input.value.strip() or None
        config["description"] = self.description_input.value.strip() or None
        config["accent_color"] = accent_color
        config.setdefault("thumbnail_enabled", False)

        updated = await medialink_mgr.update_template(self.template["id"], container_config=config)
        if updated is None:
            view = await TemplateListView.build(guild_id=self.template["guild_id"], owner_id=self.owner_id)
            await interaction.response.edit_message(view=view)
            return

        view = TemplateEditView(template=updated, owner_id=self.owner_id)
        await interaction.response.edit_message(view=view)


# ============================================================
# 🪢 Ajout des boutons liens
# ============================================================

class AddButtonModal(discord.ui.Modal):
    """Ajout d'un bouton lien."""

    def __init__(self, *, template: dict, owner_id: int):
        super().__init__(title="Ajouter un bouton")
        self.template = template
        self.owner_id = owner_id

        self.label_input = discord.ui.TextInput(
            label="Texte du bouton",
            placeholder="Ex : <:lien:1552027533032034394> Voir la vidéo",
            required=True,
            max_length=80,
        )
        self.url_input = discord.ui.TextInput(
            label="Lien (URL)",
            placeholder="https://...",
            required=True,
            max_length=512,
        )
        self.add_item(self.label_input)
        self.add_item(self.url_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        label = self.label_input.value.strip()
        url = self.url_input.value.strip()

        if not url.startswith(("http://", "https://")):
            await interaction.response.send_message(
                view=error_container("Le lien doit commencer par `http://` ou `https://`."),
                ephemeral=True,
            )
            return

        buttons = list(self.template.get("buttons") or [])
        if len(buttons) >= MAX_BUTTONS:
            await interaction.response.send_message(
                view=error_container(f"Un **template** ne peut pas avoir plus de {MAX_BUTTONS} boutons."),
                ephemeral=True,
            )
            return
        buttons.append({"label": label, "url": url})

        updated = await medialink_mgr.update_template(self.template["id"], buttons=buttons)
        if updated is None:
            view = await TemplateListView.build(guild_id=self.template["guild_id"], owner_id=self.owner_id)
            await interaction.response.edit_message(view=view)
            return

        view = TemplateEditView(template=updated, owner_id=self.owner_id)
        await interaction.response.edit_message(view=view)


# ============================================================
# 📜 Liste des templates
# ============================================================

class TemplateListView(BaseLayoutView):
    """Liste des templates d'une guild."""

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
        container.add_item(TextDisplay("# <:annonce:1552028020896698398> Templates d'annonce"))
        container.add_item(Separator())

        if not self.templates:
            container.add_item(TextDisplay("*Aucun template créé pour l'instant.*"))
        else:
            for tpl in self.templates:
                edit_btn = Button(label="Modifier", style=ButtonStyle.secondary, emoji=EMOJI_EDIT)
                edit_btn.callback = self._cb_open_template(tpl["id"])
                preview = (tpl.get("content") or "*(vide)*").replace("\n", " ")
                if len(preview) > 80:
                    preview = preview[:77] + "…"
                    
                container.add_item(Section(
                    TextDisplay(f'**📝 {tpl['name']}**\n-# ➤ Template "{tpl['name']}".'),
                    accessory=edit_btn,
                ))

        container.add_item(Separator())
        create_btn = Button(label="Créer un template", style=ButtonStyle.success, emoji=EMOJI_ADD)
        create_btn.callback = self._cb_create_template
        back_btn = Button(label="Retour au hub", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        back_btn.callback = self._cb_back

        container.add_item(ActionRow(create_btn, back_btn))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

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
        from views.medialink.medialink_dashboard_view import MediaLinkHubView

        view = await MediaLinkHubView.build(guild=interaction.guild, owner_id=self.owner_id)
        await self.push_update(interaction, view=view)


# ============================================================
# 🖍️ Édition d'un template
# ============================================================

class TemplateEditView(BaseLayoutView):
    """Édition d'un template d'annonce."""

    def __init__(self, *, template: dict, owner_id: int):
        super().__init__(owner_id=owner_id, timeout=300)
        self.template = template
        self._build()

    def _build(self) -> None:
        self.clear_items()
        container = Container()

        template_name = self.template.get("name", "Sans nom")
        container.add_item(TextDisplay(f"# <:modifier:1495444144712192003> Édition de `{template_name}`"))
        
        placeholders_help = "  ".join(f"`{{{p}}}`" for p in PLACEHOLDER_FIELDS)
        container.add_item(
            TextDisplay(
                "### 🧩 Variables disponibles\n"
                f"{placeholders_help}\n"
                "-# *Incorporez ces balises dans vos textes pour les remplacer dynamiquement.*"
            )
        )
        container.add_item(Separator())

        content = self.template.get("content") or "*(Aucun texte défini)*"
        edit_content_btn = Button(
            label="Modifier le texte",
            style=ButtonStyle.primary,
            emoji=EMOJI_EDIT,
        )
        edit_content_btn.callback = self._cb_edit_content

        container.add_item(
            Section(
                TextDisplay(f"### 📝 Message principal\n> {content}"),
                accessory=edit_content_btn,
            )
        )
        container.add_item(Separator())

        config = self.template.get("container_config") or {}
        title = config.get("title") or "*(aucun)*"
        description = config.get("description") or "*(aucune)*"
        accent_color = config.get("accent_color")
        color_str = f"`#{accent_color:06X}`" if isinstance(accent_color, int) else "*(par défaut)*"

        edit_container_btn = Button(
            label="Mise en forme",
            style=ButtonStyle.secondary,
            emoji=EMOJI_EDIT,
        )
        edit_container_btn.callback = self._cb_edit_container

        container.add_item(
            Section(
                TextDisplay(
                    "### 🎨 Encadré & Apparence\n"
                    f"• **Titre :** {title}\n"
                    f"• **Description :** {description}\n"
                    f"• **Couleur d'accent :** {color_str}"
                ),
                accessory=edit_container_btn,
            )
        )

        thumbnail_enabled = bool(config.get("thumbnail_enabled"))
        toggle_btn = Button(
            label="Vignette : Active" if thumbnail_enabled else "Vignette : Inactive",
            style=ButtonStyle.success if thumbnail_enabled else ButtonStyle.secondary,
            emoji="📸" if thumbnail_enabled else "🚫",
        )
        toggle_btn.callback = self._cb_toggle_thumbnail

        container.add_item(
            Section(
                TextDisplay(
                    "### 🖼️ Vignette de l'événement\n"
                    "-# Afficher l'image/vignette miniature à côté de l'encadré."
                ),
                accessory=toggle_btn,
            )
        )
        container.add_item(Separator())

        buttons = self.template.get("buttons") or []
        container.add_item(
            TextDisplay(f"### 🔗 Boutons interactifs (`{len(buttons)}/{MAX_BUTTONS}`)")
        )

        for index, btn in enumerate(buttons):
            remove_btn = Button(
                label="Retirer",
                style=ButtonStyle.danger,
                emoji=EMOJI_DELETE,
            )
            remove_btn.callback = self._cb_remove_button(index)

            label_str = btn.get('label', '(sans texte)')
            url_str = btn.get('url', '')
            container.add_item(
                Section(
                    TextDisplay(f"• **{label_str}**\n-# `{url_str}`"),
                    accessory=remove_btn,
                )
            )

        if len(buttons) < MAX_BUTTONS:
            add_button_btn = Button(
                label="Ajouter un bouton",
                style=ButtonStyle.secondary,
                emoji=EMOJI_ADD,
            )
            add_button_btn.callback = self._cb_add_button
            container.add_item(ActionRow(add_button_btn))
        else:
            container.add_item(
                TextDisplay("-# ⚠️ *Limite maximale de boutons atteinte.*")
            )

        container.add_item(Separator())

        preview_btn = Button(label="Prévisualiser", style=ButtonStyle.primary, emoji="👁️")
        preview_btn.callback = self._cb_preview

        back_btn = Button(label="Retour", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        back_btn.callback = self._cb_back

        delete_btn = Button(label="Supprimer", style=ButtonStyle.danger, emoji=EMOJI_DELETE)
        delete_btn.callback = self._cb_delete_template

        container.add_item(ActionRow(preview_btn, back_btn, delete_btn))
        
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    # ============================================================
    # 🎛️ Callbacks
    # ============================================================

    async def _cb_edit_content(self, interaction: discord.Interaction) -> None:
        modal = EditContentModal(template=self.template, owner_id=self.owner_id)
        await interaction.response.send_modal(modal)

    async def _cb_edit_container(self, interaction: discord.Interaction) -> None:
        modal = EditContainerModal(template=self.template, owner_id=self.owner_id)
        await interaction.response.send_modal(modal)

    async def _cb_add_button(self, interaction: discord.Interaction) -> None:
        modal = AddButtonModal(template=self.template, owner_id=self.owner_id)
        await interaction.response.send_modal(modal)

    async def _cb_toggle_thumbnail(self, interaction: discord.Interaction) -> None:
        config = dict(self.template.get("container_config") or {})
        config["thumbnail_enabled"] = not config.get("thumbnail_enabled", False)

        updated = await medialink_mgr.update_template(self.template["id"], container_config=config)
        if updated is None:
            view = await TemplateListView.build(guild_id=self.template["guild_id"], owner_id=self.owner_id)
            await self.push_update(interaction, view=view)
            return

        self.template = updated
        self._build()
        await self.push_update(interaction)

    def _cb_remove_button(self, index: int):
        async def _callback(interaction: discord.Interaction) -> None:
            buttons = list(self.template.get("buttons") or [])
            if 0 <= index < len(buttons):
                buttons.pop(index)

            updated = await medialink_mgr.update_template(self.template["id"], buttons=buttons)
            if updated is None:
                view = await TemplateListView.build(guild_id=self.template["guild_id"], owner_id=self.owner_id)
                await self.push_update(interaction, view=view)
                return

            self.template = updated
            self._build()
            await self.push_update(interaction)
        return _callback

    async def _cb_preview(self, interaction: discord.Interaction) -> None:
        transient = MediaTemplate(
            id=self.template["id"],
            guild_id=self.template["guild_id"],
            name=self.template["name"],
            content=self.template.get("content"),
            container_config=self.template.get("container_config"),
            buttons=self.template.get("buttons"),
        )
        built = announcement_builder.build(transient, _PREVIEW_EVENT)
        kwargs = built.to_kwargs()

        if not kwargs:
            await send_ephemeral(
                interaction,
                info_container("Ce **template** n'est pas encore __construit__."),
            )
            return

        kwargs["ephemeral"] = True
        await interaction.response.send_message(**kwargs)

    async def _cb_delete_template(self, interaction: discord.Interaction) -> None:
        await medialink_mgr.remove_template(self.template["id"])

        view = await TemplateListView.build(guild_id=self.template["guild_id"], owner_id=self.owner_id)
        await self.push_update(interaction, view=view)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        view = await TemplateListView.build(guild_id=self.template["guild_id"], owner_id=self.owner_id)
        await self.push_update(interaction, view=view)