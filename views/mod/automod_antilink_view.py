"""
views/mod/automod_antilink_view.py — Configuration du système Anti Link.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction, SelectOption
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Select, Separator, TextDisplay

from utils.container_universel import error_container, warning_container
from utils.managers import mod_automod_antilink_manager as mgr
from utils.settings import settings
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

MAX_EXTENSION_LENGTH = 20
EXTENSIONS_PREVIEW_MAX = 40
REMOVE_SELECT_MAX = 25


# ============================================================
# 🧩 Création de l'interface principale
# ============================================================

async def create_automod_antilink_view(guild_id: int, bot, author_id: Optional[int] = None) -> Optional[LayoutView]:
    """Création view principale Anti Link."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    cfg = await mgr.load_config(guild_id)
    extensions = await mgr.list_extensions(guild_id)
    enabled = cfg.get("enabled", False)

    view = LayoutView(timeout=600)
    container = Container()

    # Header
    container.add_item(TextDisplay("# <:fichier_i:1539608464324567040> Système Anti Link"))
    container.add_item(Separator())

    # Toggle activation
    toggle_btn = Button(
        label="Activé" if enabled else "Désactivé",
        emoji="<:valider:1495444292867723284>" if enabled else "<:annuler:1495444256754761979>",
        style=ButtonStyle.success if enabled else ButtonStyle.danger,
        custom_id=f"toggle_{guild_id}"
    )
    toggle_btn.callback = _cb_toggle(guild_id, bot, author_id)

    container.add_item(Section(
        TextDisplay(
            "**🔘 Statut du système**\n"
            "-# Bloque les fichiers/liens vers une extension dangereuse."
        ),
        accessory=toggle_btn,
    ))
    container.add_item(Separator())

    # Section extensions bloquées
    manage_btn = Button(label="Gérer", emoji="<:modifier:1495444144712192003>", style=ButtonStyle.primary)
    manage_btn.callback = _cb_open_manage(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            f"**📋 Extensions bloquées** (`{len(extensions)}`)\n"
            "-# Ajouter, retirer ou vider la liste des extensions."
        ),
        accessory=manage_btn,
    ))
    container.add_item(Separator())

    # Retour + doc
    btn_back = Button(label="Retour", style=ButtonStyle.secondary, emoji="<:retour:1515658955190308995>")
    btn_back.callback = _cb_back_to_dashboard(guild_id, bot, author_id)
    container.add_item(ActionRow(
        btn_back,
        Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚"),
    ))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# ⛔ Création de l'interface de gestion des extensions bloquées
# ============================================================

async def create_automod_antilink_extensions_view(guild_id: int, bot, author_id: Optional[int] = None) -> Optional[LayoutView]:
    """Page dédiée à la gestion des extensions bloquées."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    extensions = await mgr.list_extensions(guild_id)

    view = LayoutView(timeout=600)
    container = Container()

    # Header
    container.add_item(TextDisplay("# 📋 Extensions bloquées"))
    container.add_item(Separator())

    # Liste
    if not extensions:
        container.add_item(TextDisplay(
            "-# *Aucune extension dans la liste.* Utilise le bouton **Ajouter** "
            "ci-dessous pour commencer."
        ))
    else:
        preview = extensions[:EXTENSIONS_PREVIEW_MAX]
        body = " · ".join(f"`{e}`" for e in preview)
        if len(extensions) > EXTENSIONS_PREVIEW_MAX:
            body += f"\n-# *… et {len(extensions) - EXTENSIONS_PREVIEW_MAX} de plus*"
        container.add_item(TextDisplay(body))
    container.add_item(Separator())

    # Ajout (texte libre — une extension n'est pas une ressource Discord)
    btn_add = Button(label="Ajouter", style=ButtonStyle.success, emoji="<:plus:1495444111505752154>")
    btn_add.callback = _cb_add_extension(guild_id, bot, author_id)
    container.add_item(ActionRow(btn_add))

    # Retrait (Select construit depuis la DB — liste finie, ≤25)
    if extensions:
        remove_options: list[SelectOption] = [
            SelectOption(label=ext, value=ext) for ext in extensions[:REMOVE_SELECT_MAX]
        ]
        remove_select = Select(
            placeholder="Choisir une extension à retirer",
            options=remove_options, min_values=1, max_values=1,
        )
        remove_select.callback = _on_remove_extension(guild_id, bot, author_id, remove_select)
        container.add_item(ActionRow(remove_select))

    btn_clear = Button(
        label="Tout vider", style=ButtonStyle.danger,
        emoji="<:supprimer:1495444051623809075>", disabled=not extensions,
    )
    btn_clear.callback = _cb_clear_extensions(guild_id, bot, author_id)
    container.add_item(ActionRow(btn_clear))
    container.add_item(Separator())

    # Retour vers page principale
    btn_back = Button(label="Retour", style=ButtonStyle.secondary, emoji="<:retour:1515658955190308995>")
    btn_back.callback = _cb_back_to_antilink(guild_id, bot, author_id)
    container.add_item(ActionRow(
        btn_back,
        Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚"),
    ))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 🛡️ Garde d'accès
# ============================================================

def _guard(author_id: Optional[int]):
    async def check(interaction: Interaction) -> bool:
        if author_id is not None and interaction.user.id != author_id:
            await interaction.response.send_message(
                view=error_container("Seul l'**auteur** peut utiliser ce menu."), ephemeral=True,
            )
            return False
        m = interaction.user
        if not isinstance(m, discord.Member) or not m.guild_permissions.administrator:
            await interaction.response.send_message(
                view=error_container("Vous devez être **Administrateur**."), ephemeral=True,
            )
            return False
        return True
    return check


async def _rerender_main(interaction: Interaction, guild_id: int, bot, author_id) -> None:
    """Rebuild + réédite la vue principale Anti Link."""
    new_view = await create_automod_antilink_view(guild_id, bot, author_id)
    if new_view is None:
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


async def _rerender_extensions(interaction: Interaction, guild_id: int, bot, author_id) -> None:
    """Rebuild + réédite la vue gestion des extensions."""
    new_view = await create_automod_antilink_extensions_view(guild_id, bot, author_id)
    if new_view is None:
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


# ============================================================
# 📑 Callbacks — page principale
# ============================================================

def _cb_toggle(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        current = (await mgr.load_config(guild_id)).get("enabled", False)
        await mgr.set_enabled(guild_id, not current)
        await _rerender_main(interaction, guild_id, bot, author_id)
    return cb


def _cb_open_manage(guild_id, bot, author_id):
    """Ouvre la page 2 (gestion des extensions)."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await _rerender_extensions(interaction, guild_id, bot, author_id)
    return cb


def _cb_back_to_dashboard(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        from views.mod.automod_dashboard_view import create_automod_dashboard_view
        new_view = await create_automod_dashboard_view(guild_id, bot, author_id)
        if new_view is None:
            return
        await interaction.response.edit_message(view=new_view)
    return cb


# ============================================================
# 📑 Callbacks — page gestion des extensions
# ============================================================

def _cb_back_to_antilink(guild_id, bot, author_id):
    """Retour de la page 2 vers la page 1 (pas vers le dashboard)."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await _rerender_main(interaction, guild_id, bot, author_id)
    return cb


def _cb_add_extension(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        async def submit(inter: Interaction, value: str) -> None:
            value = (value or "").strip()
            if not value:
                await inter.response.send_message(
                    view=warning_container("L'extension ne peut pas être vide."), ephemeral=True,
                )
                return
            added = await mgr.add_extension(guild_id, value)
            if not added:
                await inter.response.send_message(
                    view=warning_container(f"Cette extension est **déjà** dans la liste, ou invalide."),
                    ephemeral=True,
                )
                return
            await _rerender_extensions(inter, guild_id, bot, author_id)

        await interaction.response.send_modal(TextModal(
            title="Ajouter une extension", label="Extension à bloquer", placeholder="Ex : .exe",
            required=True, max_length=MAX_EXTENSION_LENGTH, on_submit=submit,
        ))
    return cb


def _on_remove_extension(guild_id, bot, author_id, select_ref: Select):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        if not select_ref.values:
            return
        extension = select_ref.values[0]
        removed = await mgr.remove_extension(guild_id, extension)
        if not removed:
            await interaction.response.send_message(
                view=warning_container(f"L'extension `{extension}` n'est **plus** dans la liste."),
                ephemeral=True,
            )
            return
        await _rerender_extensions(interaction, guild_id, bot, author_id)
    return cb


def _cb_clear_extensions(guild_id, bot, author_id):
    """Confirmation intégrée (edit_message) avant purge complète."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        extensions = await mgr.list_extensions(guild_id)
        confirm = _build_clear_confirm(guild_id, bot, author_id, count=len(extensions))
        await interaction.response.edit_message(view=confirm)
    return cb


def _build_clear_confirm(guild_id, bot, author_id, *, count: int) -> LayoutView:
    view = LayoutView(timeout=120)
    c = Container()
    c.add_item(TextDisplay("# 🗑️ Vider la liste des extensions bloquées ?"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"Tu vas supprimer **{count}** extension(s) définitivement.\n"
        "-# Cette action est irréversible."
    ))
    c.add_item(Separator())

    async def do_clear(interaction: Interaction):
        await mgr.clear_extensions(guild_id)
        await _rerender_extensions(interaction, guild_id, bot, author_id)

    async def cancel(interaction: Interaction):
        await _rerender_extensions(interaction, guild_id, bot, author_id)

    btn_confirm = Button(label="Confirmer", style=ButtonStyle.danger, emoji="<:valider:1495444292867723284>")
    btn_confirm.callback = do_clear
    btn_cancel = Button(label="Annuler", style=ButtonStyle.secondary, emoji="<:retour:1515658955190308995>")
    btn_cancel.callback = cancel
    c.add_item(ActionRow(btn_confirm, btn_cancel))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c)
    return view