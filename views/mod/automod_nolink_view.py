"""
views/mod/automod_nolink_view.py — Configuration du système No Link.

Même structure à deux pages que automod_banword_view.py :
  - page 1 : toggle + accès à la gestion des salons whitelistés
  - page 2 : liste des salons whitelistés + ajout (ChannelSelect natif,
    ressource serveur toujours résolvable — pas un Select de membres) +
    retrait (Select manuel construit depuis la whitelist en DB, pour
    pouvoir retirer un salon même s'il a été supprimé depuis côté Discord)
    + purge complète (confirmation intégrée)
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction, SelectOption
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Select, Separator, TextDisplay

from utils.container_universel import error_container, warning_container
from utils.managers import mod_automod_nolink_manager as mgr
from utils.settings import settings
from views._components.channel_select import ChannelSelect

log = logging.getLogger(__name__)

CHANNEL_TYPES = [discord.ChannelType.text, discord.ChannelType.news]
CHANNELS_PREVIEW_MAX = 25
REMOVE_SELECT_MAX = 25


# ============================================================
# 🧩 Création de l'interface principale
# ============================================================

async def create_automod_nolink_view(guild_id: int, bot, author_id: Optional[int] = None) -> Optional[LayoutView]:
    """Création view principale No Link."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    cfg = await mgr.load_config(guild_id)
    whitelist = await mgr.list_whitelist(guild_id)
    enabled = cfg.get("enabled", False)
    bypass_gif = cfg.get("bypass_gif", False)

    view = LayoutView(timeout=600)
    container = Container()

    # Header
    container.add_item(TextDisplay("# <:protect_config:1539608365704028340> Système No Link"))
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
            "-# Supprime tous les liens hors salons whitelistés."
        ),
        accessory=toggle_btn,
    ))
    container.add_item(Separator())

    gif_toggle_btn = Button(
        label="Activé" if bypass_gif else "Désactivé",
        emoji="<:valider:1495444292867723284>" if bypass_gif else "<:annuler:1495444256754761979>",
        style=ButtonStyle.success if bypass_gif else ButtonStyle.danger,
        custom_id=f"toggle_gif_{guild_id}"
    )
    gif_toggle_btn.callback = _cb_toggle_gif(guild_id, bot, author_id)

    container.add_item(Section(
        TextDisplay(
            "**🖼️ Bypass GIF**\n"
            "-# Autorise les GIF malgré le système actif."
        ),
        accessory=gif_toggle_btn,
    ))
    container.add_item(Separator())

    # Section salons whitelistés
    manage_btn = Button(label="Gérer", emoji="<:modifier:1495444144712192003>", style=ButtonStyle.primary)
    manage_btn.callback = _cb_open_manage(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            f"**📋 Salons whitelistés** (`{len(whitelist)}`)\n"
            "-# Les liens y restent autorisés malgré le système actif."
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
# 📋 Création de l'interface de gestion des salons whitelistés
# ============================================================

async def create_automod_nolink_whitelist_view(guild_id: int, bot, author_id: Optional[int] = None) -> Optional[LayoutView]:
    """Page dédiée à la gestion des salons whitelistés."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    whitelist = await mgr.list_whitelist(guild_id)

    view = LayoutView(timeout=600)
    container = Container()

    # Header
    container.add_item(TextDisplay("# 📋 Salons whitelistés"))
    container.add_item(Separator())

    # Liste
    if not whitelist:
        container.add_item(TextDisplay(
            "-# *Aucun salon dans la liste.* Choisis un salon ci-dessous "
            "pour l'ajouter à la whitelist."
        ))
    else:
        preview = whitelist[:CHANNELS_PREVIEW_MAX]
        body = " · ".join(f"<#{cid}>" for cid in preview)
        if len(whitelist) > CHANNELS_PREVIEW_MAX:
            body += f"\n-# *… et {len(whitelist) - CHANNELS_PREVIEW_MAX} de plus*"
        container.add_item(TextDisplay(body))
    container.add_item(Separator())

    # Ajout (ChannelSelect natif — ressource serveur, toujours résolvable)
    add_select = ChannelSelect(
        placeholder="Choisir un salon à whitelister",
        on_select=_on_add_channel(guild_id, bot, author_id),
        channel_types=CHANNEL_TYPES,
    )
    container.add_item(ActionRow(add_select))

    # Retrait (Select manuel construit depuis la DB — fonctionne même si le
    # salon a été supprimé côté Discord depuis, contrairement à un ChannelSelect
    # natif qui ne proposerait plus le salon).
    if whitelist:
        remove_options: list[SelectOption] = []
        for cid in whitelist[:REMOVE_SELECT_MAX]:
            channel = guild.get_channel(cid)
            label = f"#{channel.name}" if channel is not None else f"Salon supprimé ({cid})"
            remove_options.append(SelectOption(label=label[:100], value=str(cid)))
        remove_select = Select(
            placeholder="Choisir un salon à retirer",
            options=remove_options, min_values=1, max_values=1,
        )
        remove_select.callback = _on_remove_channel(guild_id, bot, author_id, remove_select)
        container.add_item(ActionRow(remove_select))
    container.add_item(Separator())

    # Actions
    btn_clear = Button(
        label="Tout vider", style=ButtonStyle.danger,
        emoji="<:supprimer:1495444051623809075>", disabled=not whitelist,
    )
    btn_clear.callback = _cb_clear_whitelist(guild_id, bot, author_id)
    container.add_item(ActionRow(btn_clear))
    container.add_item(Separator())

    # Retour vers page principale
    btn_back = Button(label="Retour", style=ButtonStyle.secondary, emoji="<:retour:1515658955190308995>")
    btn_back.callback = _cb_back_to_nolink(guild_id, bot, author_id)
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
    """Rebuild + réédite la vue principale No Link."""
    new_view = await create_automod_nolink_view(guild_id, bot, author_id)
    if new_view is None:
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


async def _rerender_whitelist(interaction: Interaction, guild_id: int, bot, author_id) -> None:
    """Rebuild + réédite la vue gestion des salons."""
    new_view = await create_automod_nolink_whitelist_view(guild_id, bot, author_id)
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


def _cb_toggle_gif(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        current = (await mgr.load_config(guild_id)).get("bypass_gif", False)
        await mgr.set_bypass_gif(guild_id, not current)
        await _rerender_main(interaction, guild_id, bot, author_id)
    return cb


def _cb_open_manage(guild_id, bot, author_id):
    """Ouvre la page 2 (gestion des salons)."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await _rerender_whitelist(interaction, guild_id, bot, author_id)
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
# 📑 Callbacks — page gestion des salons
# ============================================================

def _cb_back_to_nolink(guild_id, bot, author_id):
    """Retour de la page 2 vers la page 1 (pas vers le dashboard)."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await _rerender_main(interaction, guild_id, bot, author_id)
    return cb


def _on_add_channel(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction, channel_id: int):
        if not await check(interaction):
            return
        added = await mgr.add_channel(guild_id, channel_id)
        if not added:
            await interaction.response.send_message(
                view=warning_container(f"<#{channel_id}> est **déjà** dans la whitelist."),
                ephemeral=True,
            )
            return
        await _rerender_whitelist(interaction, guild_id, bot, author_id)
    return cb


def _on_remove_channel(guild_id, bot, author_id, select_ref: Select):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        if not select_ref.values:
            return
        try:
            channel_id = int(select_ref.values[0])
        except ValueError:
            return
        removed = await mgr.remove_channel(guild_id, channel_id)
        if not removed:
            await interaction.response.send_message(
                view=warning_container("Ce salon n'est **plus** dans la whitelist."),
                ephemeral=True,
            )
            return
        await _rerender_whitelist(interaction, guild_id, bot, author_id)
    return cb


def _cb_clear_whitelist(guild_id, bot, author_id):
    """Confirmation intégrée (edit_message) avant purge complète."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        whitelist = await mgr.list_whitelist(guild_id)
        confirm = _build_clear_confirm(guild_id, bot, author_id, count=len(whitelist))
        await interaction.response.edit_message(view=confirm)
    return cb


def _build_clear_confirm(guild_id, bot, author_id, *, count: int) -> LayoutView:
    view = LayoutView(timeout=120)
    c = Container()
    c.add_item(TextDisplay("# 🗑️ Vider la whitelist des salons ?"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"Tu vas retirer **{count}** salon(s) de la whitelist définitivement.\n"
        "-# Cette action est irréversible."
    ))
    c.add_item(Separator())

    async def do_clear(interaction: Interaction):
        await mgr.clear_whitelist(guild_id)
        await _rerender_whitelist(interaction, guild_id, bot, author_id)

    async def cancel(interaction: Interaction):
        await _rerender_whitelist(interaction, guild_id, bot, author_id)

    btn_confirm = Button(label="Confirmer", style=ButtonStyle.danger, emoji="<:valider:1495444292867723284>")
    btn_confirm.callback = do_clear
    btn_cancel = Button(label="Annuler", style=ButtonStyle.secondary, emoji="<:retour:1515658955190308995>")
    btn_cancel.callback = cancel
    c.add_item(ActionRow(btn_confirm, btn_cancel))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c)
    return view