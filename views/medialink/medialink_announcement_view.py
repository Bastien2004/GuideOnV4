"""
views/medialink/medialink_announcement_view.py — liste + édition des
MediaTemplate (§7, 4e concept "Announcement Template").

── MISE EN FORME (2026-09, cadré avec Paul) ─────────────────────────
container_config (accent_color/title/description/thumbnail_enabled) et
buttons ont maintenant leur UI d'édition ci-dessous : EditContainerModal
pour titre/description/couleur, un bouton toggle direct pour
thumbnail_enabled (pas de Select possible dans un Modal — cf. maquette
AddRuleView dans medialink_events_view.py pour le même constat), et
AddButtonModal pour ajouter un bouton lien (suppression via un bouton
par entrée). "Aperçu" envoie un rendu réel (utils/medialink/builders/
announcement.py) construit avec un MediaEvent d'exemple, en éphémère —
seul moyen fiable de vérifier visuellement la règle §7 ("ne jamais
afficher une valeur nulle") sans attendre un vrai événement.

content (texte libre) garde son fonctionnement d'origine, inchangé.
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

EMOJI_ADD = "<:plus:1495444111505752154>"
EMOJI_EDIT = "<:modifier:1495444144712192003>"
EMOJI_DELETE = "<:supprimer:1495444051623809075>"
EMOJI_BACK = "<:retour:1515658955190308995>"

# Événement d'exemple pour l'Aperçu (_cb_preview ci-dessous) — permet de
# voir le rendu réel d'un template (titre/description/vignette/boutons)
# sans attendre un vrai événement plateforme. Tous les placeholders
# connus (PLACEHOLDER_FIELDS) ont volontairement une valeur non vide ici,
# pour que l'aperçu montre le template "au mieux" ; un vrai événement
# peut avoir moins de champs disponibles (cf. §7 dans placeholders.py).
_PREVIEW_EVENT = MediaEvent(
    platform="youtube",
    event_type="new_post",
    external_id="preview",
    title="Titre de la vidéo (exemple)",
    description="Description de l'événement, utilisée pour prévisualiser le rendu du template (exemple).",
    url="https://youtube.com",
    thumbnail="https://placehold.co/480x270?text=Vignette",
    author="Nom de la chaîne (exemple)",
)


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


class EditContainerModal(discord.ui.Modal):
    """Édition de container_config (titre/description/couleur) — pas
    thumbnail_enabled, qui se bascule directement par bouton sur
    TemplateEditView (cf. _cb_toggle_thumbnail) puisqu'un booléen n'a pas
    sa place dans un Modal."""

    def __init__(self, *, template: dict, owner_id: int):
        super().__init__(title="Modifier la mise en forme")
        self.template = template
        self.owner_id = owner_id
        config = template.get("container_config") or {}

        self.title_input = discord.ui.TextInput(
            label="Titre (optionnel)",
            placeholder="Ex : 🎬 Nouvelle vidéo",
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
                    view=error_container(
                        "Couleur invalide — utilise un code hexadécimal à 6 "
                        "caractères, ex : `#5865F2`."
                    ),
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


class AddButtonModal(discord.ui.Modal):
    """Ajout d'un bouton lien (label + URL) à `buttons` — rendu en
    ActionRow de Button(style=link) par announcement.py."""

    def __init__(self, *, template: dict, owner_id: int):
        super().__init__(title="Ajouter un bouton")
        self.template = template
        self.owner_id = owner_id

        self.label_input = discord.ui.TextInput(
            label="Texte du bouton",
            placeholder="Ex : Voir la vidéo",
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
                view=error_container(f"Un template ne peut pas avoir plus de {MAX_BUTTONS} boutons."),
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
        container.add_item(TextDisplay("# 📢 Annonces"))
        container.add_item(TextDisplay(f"-# {len(self.templates)} template(s) créé(s) sur ce serveur."))
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
                    TextDisplay(f"**📝 {tpl['name']}**\n-# {preview}{_extras_label(tpl)}"),
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


def _extras_label(tpl: dict) -> str:
    """Petite indication " · mise en forme, 2 bouton(s)" dans la liste,
    pour distinguer d'un coup d'œil un template texte simple d'un
    template avec container_config/buttons — sans avoir à ouvrir
    chacun."""
    config = tpl.get("container_config") or {}
    extras = []
    if config.get("title") or config.get("description"):
        extras.append("mise en forme")
    buttons = tpl.get("buttons") or []
    if buttons:
        extras.append(f"{len(buttons)} bouton(s)")
    return f" · {', '.join(extras)}" if extras else ""


class TemplateEditView(BaseLayoutView):
    """Édition d'un template : texte libre (content), mise en forme
    Components V2 (container_config) et boutons (buttons)."""

    def __init__(self, *, template: dict, owner_id: int):
        super().__init__(owner_id=owner_id, timeout=300)
        self.template = template
        self._build()

    def _build(self) -> None:
        self.clear_items()

        container = Container()
        container.add_item(TextDisplay(f"# ✏️ {self.template.get('name', 'Sans nom')}"))
        container.add_item(Separator())

        placeholders_help = ", ".join(f"`{{{p}}}`" for p in PLACEHOLDER_FIELDS)
        container.add_item(TextDisplay(f"**Placeholders disponibles**\n-# {placeholders_help}"))
        container.add_item(Separator())

        # ── Texte libre ────────────────────────────────────────────
        content = self.template.get("content") or "*(vide)*"
        edit_content_btn = Button(label="Modifier", style=ButtonStyle.secondary, emoji=EMOJI_EDIT)
        edit_content_btn.callback = self._cb_edit_content
        container.add_item(Section(TextDisplay(f"**Texte libre**\n>>> {content}"), accessory=edit_content_btn))
        container.add_item(Separator())

        # ── Mise en forme (container_config) ─────────────────────────
        config = self.template.get("container_config") or {}
        title = config.get("title") or "*(aucun)*"
        description = config.get("description") or "*(aucune)*"
        accent_color = config.get("accent_color")
        color_str = f"#{accent_color:06X}" if isinstance(accent_color, int) else "*(par défaut)*"

        edit_container_btn = Button(label="Modifier", style=ButtonStyle.secondary, emoji=EMOJI_EDIT)
        edit_container_btn.callback = self._cb_edit_container
        container.add_item(Section(
            TextDisplay(
                f"**Mise en forme**\n"
                f"-# Titre : {title}\n"
                f"-# Description : {description}\n"
                f"-# Couleur : {color_str}"
            ),
            accessory=edit_container_btn,
        ))

        thumbnail_enabled = bool(config.get("thumbnail_enabled"))
        toggle_btn = Button(
            label="Vignette : Activée" if thumbnail_enabled else "Vignette : Désactivée",
            style=ButtonStyle.success if thumbnail_enabled else ButtonStyle.secondary,
        )
        toggle_btn.callback = self._cb_toggle_thumbnail
        container.add_item(Section(
            TextDisplay("-# Affiche la vignette de l'événement (`{vignette}`) à côté du texte, si disponible."),
            accessory=toggle_btn,
        ))
        container.add_item(Separator())

        # ── Boutons ───────────────────────────────────────────────
        buttons = self.template.get("buttons") or []
        container.add_item(TextDisplay(f"**Boutons** ({len(buttons)}/{MAX_BUTTONS})"))
        for index, btn in enumerate(buttons):
            remove_btn = Button(style=ButtonStyle.danger, emoji=EMOJI_DELETE)
            remove_btn.callback = self._cb_remove_button(index)
            container.add_item(Section(
                TextDisplay(f"🔗 **{btn.get('label', '(sans texte)')}**\n-# {btn.get('url', '')}"),
                accessory=remove_btn,
            ))

        if len(buttons) < MAX_BUTTONS:
            add_button_btn = Button(label="Ajouter un bouton", style=ButtonStyle.secondary, emoji=EMOJI_ADD)
            add_button_btn.callback = self._cb_add_button
            container.add_item(ActionRow(add_button_btn))
        else:
            container.add_item(TextDisplay(f"-# Maximum de {MAX_BUTTONS} boutons atteint."))

        container.add_item(Separator())

        preview_btn = Button(label="Aperçu", style=ButtonStyle.primary, emoji="👁️")
        preview_btn.callback = self._cb_preview
        delete_btn = Button(label="Supprimer", style=ButtonStyle.danger, emoji=EMOJI_DELETE)
        delete_btn.callback = self._cb_delete_template
        back_btn = Button(label="Retour", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        back_btn.callback = self._cb_back

        container.add_item(ActionRow(preview_btn, delete_btn, back_btn))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

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
        # MediaTemplate transitoire (jamais ajouté à une session, jamais
        # persisté) : announcement_builder.build() ne lit que
        # content/container_config/buttons, une instance en mémoire à
        # partir du dict suffit — pas besoin d'aller rechercher en base.
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
                info_container("Ce template est vide pour l'instant — rien à prévisualiser."),
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