"""
views/mod/automod_banword_view.py — Configuration du système Ban Word (v3).

Refactorée en 2 pages :

  1. `create_automod_banword_view` (page principale)
       Vue courte : toggle activation + Section "Mots interdits" avec bouton
       "Gérer" (accessory) qui ouvre la page 2. Le retour de cette page
       renvoie vers le dashboard automod.

  2. `create_automod_banword_words_view` (page gestion des mots)
       Liste complète des mots (paginée si nombreuse) + boutons
       Ajouter / Retirer / Vider. Le retour de cette page renvoie vers la
       page principale ban word (pas vers le dashboard directement).

Reste "pas de select" — cohérent avec le choix général du projet (les
ajouts/retraits passent par modal texte).
"""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.container_universel import error_container, warning_container
from utils.managers import mod_automod_banword_manager as mgr
from utils.settings import settings
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

MAX_WORD_LENGTH = 100
WORDS_PREVIEW_MAX = 30  # nombre max de mots affichés inline sur la page 2


# ═══════════════════════════════════════════════════════════════
# 📄 Page 1 — Vue principale (toggle + accès gestion)
# ═══════════════════════════════════════════════════════════════

async def create_automod_banword_view(
    guild_id: int, bot, author_id: Optional[int] = None,
) -> Optional[LayoutView]:
    """Vue principale ban word : toggle + accès à la gestion des mots."""
    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    cfg = await mgr.load_config(guild_id)
    words = await mgr.list_words(guild_id)
    enabled = cfg.get("enabled", False)

    view = LayoutView(timeout=600)
    container = Container()

    # Header
    dot = "🟢" if enabled else "🔴"
    state = "Activé" if enabled else "Désactivé"
    container.add_item(TextDisplay(f"# 🚫 Ban Word · {dot} {state}"))
    container.add_item(Separator())

    # Description
    container.add_item(TextDisplay(
        "-# Bloque les messages contenant un mot interdit. Reconnaît les "
        "contournements courants (accents, chiffres, espaces, ponctuation)."
    ))
    container.add_item(Separator())

    # Toggle activation
    toggle_btn = Button(
        label="✅ Activé" if enabled else "❌ Désactivé",
        style=ButtonStyle.success if enabled else ButtonStyle.danger,
    )
    toggle_btn.callback = _cb_toggle(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            "**🔘 Statut du système**\n"
            "-# Analyse chaque message avant publication."
        ),
        accessory=toggle_btn,
    ))
    container.add_item(Separator())

    # Section "Mots interdits" → bouton Gérer
    manage_btn = Button(label="Gérer", emoji="📋", style=ButtonStyle.primary)
    manage_btn.callback = _cb_open_manage(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            f"**📋 Mots interdits · {len(words)}**\n"
            "-# Ajouter, retirer ou vider la liste des mots surveillés."
        ),
        accessory=manage_btn,
    ))
    container.add_item(Separator())

    # Retour + doc
    btn_back = Button(label="Retour", style=ButtonStyle.secondary, emoji="↩️")
    btn_back.callback = _cb_back_to_dashboard(guild_id, bot, author_id)
    container.add_item(ActionRow(
        btn_back,
        Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚"),
    ))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ═══════════════════════════════════════════════════════════════
# 📄 Page 2 — Gestion des mots (liste + add/remove/clear)
# ═══════════════════════════════════════════════════════════════

async def create_automod_banword_words_view(
    guild_id: int, bot, author_id: Optional[int] = None,
) -> Optional[LayoutView]:
    """Page dédiée à la liste + gestion des mots interdits."""
    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    words = await mgr.list_words(guild_id)

    view = LayoutView(timeout=600)
    container = Container()

    # Header
    container.add_item(TextDisplay(f"# 📋 Mots interdits · {len(words)}"))
    container.add_item(Separator())

    # Liste
    if not words:
        container.add_item(TextDisplay(
            "-# *Aucun mot dans la liste.* Utilise le bouton **Ajouter** ci-dessous "
            "pour commencer."
        ))
    else:
        preview = words[:WORDS_PREVIEW_MAX]
        body = " · ".join(f"`{w}`" for w in preview)
        if len(words) > WORDS_PREVIEW_MAX:
            body += f"\n-# *… et {len(words) - WORDS_PREVIEW_MAX} de plus*"
        container.add_item(TextDisplay(body))
    container.add_item(Separator())

    # Actions
    btn_add = Button(label="Ajouter", style=ButtonStyle.success, emoji="➕")
    btn_add.callback = _cb_add_word(guild_id, bot, author_id)
    btn_remove = Button(label="Retirer", style=ButtonStyle.danger, emoji="➖", disabled=not words)
    btn_remove.callback = _cb_remove_word(guild_id, bot, author_id)
    btn_clear = Button(label="Tout vider", style=ButtonStyle.danger, emoji="🗑️", disabled=not words)
    btn_clear.callback = _cb_clear_words(guild_id, bot, author_id)
    container.add_item(ActionRow(btn_add, btn_remove, btn_clear))
    container.add_item(Separator())

    # Retour vers page 1 (ban word principal, pas le dashboard)
    btn_back = Button(label="Retour", style=ButtonStyle.secondary, emoji="↩️")
    btn_back.callback = _cb_back_to_banword(guild_id, bot, author_id)
    container.add_item(ActionRow(
        btn_back,
        Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚"),
    ))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ═══════════════════════════════════════════════════════════════
# 📑 Guard + rerenders
# ═══════════════════════════════════════════════════════════════

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
    """Rebuild + réédite la vue principale ban word."""
    new_view = await create_automod_banword_view(guild_id, bot, author_id)
    if new_view is None:
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


async def _rerender_words(interaction: Interaction, guild_id: int, bot, author_id) -> None:
    """Rebuild + réédite la vue gestion des mots."""
    new_view = await create_automod_banword_words_view(guild_id, bot, author_id)
    if new_view is None:
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


# ═══════════════════════════════════════════════════════════════
# 📑 Callbacks — page principale
# ═══════════════════════════════════════════════════════════════

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
    """Ouvre la page 2 (gestion des mots)."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await _rerender_words(interaction, guild_id, bot, author_id)
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


# ═══════════════════════════════════════════════════════════════
# 📑 Callbacks — page gestion des mots
# ═══════════════════════════════════════════════════════════════

def _cb_back_to_banword(guild_id, bot, author_id):
    """Retour de la page 2 vers la page 1 (pas vers le dashboard)."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await _rerender_main(interaction, guild_id, bot, author_id)
    return cb


def _cb_add_word(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        async def submit(inter: Interaction, value: str) -> None:
            value = (value or "").strip()
            if not value:
                await inter.response.send_message(
                    view=warning_container("Le mot ne peut pas être vide."), ephemeral=True,
                )
                return
            added = await mgr.add_word(guild_id, value)
            if not added:
                await inter.response.send_message(
                    view=warning_container(f"Le mot `{value.lower()}` est **déjà** dans la liste."),
                    ephemeral=True,
                )
                return
            await _rerender_words(inter, guild_id, bot, author_id)

        await interaction.response.send_modal(TextModal(
            title="Ajouter un mot", label="Mot à bannir", placeholder="Ex : insulte",
            required=True, max_length=MAX_WORD_LENGTH, on_submit=submit,
        ))
    return cb


def _cb_remove_word(guild_id, bot, author_id):
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        async def submit(inter: Interaction, value: str) -> None:
            value = (value or "").strip()
            if not value:
                await inter.response.send_message(
                    view=warning_container("Le mot ne peut pas être vide."), ephemeral=True,
                )
                return
            removed = await mgr.remove_word(guild_id, value)
            if not removed:
                await inter.response.send_message(
                    view=warning_container(f"Le mot `{value.lower()}` n'est **pas** dans la liste."),
                    ephemeral=True,
                )
                return
            await _rerender_words(inter, guild_id, bot, author_id)

        await interaction.response.send_modal(TextModal(
            title="Retirer un mot", label="Mot à retirer", placeholder="Ex : insulte",
            required=True, max_length=MAX_WORD_LENGTH, on_submit=submit,
        ))
    return cb


def _cb_clear_words(guild_id, bot, author_id):
    """Confirmation intégrée (edit_message) avant purge complète."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        words = await mgr.list_words(guild_id)
        confirm = _build_clear_confirm(guild_id, bot, author_id, count=len(words))
        await interaction.response.edit_message(view=confirm)
    return cb


def _build_clear_confirm(guild_id, bot, author_id, *, count: int) -> LayoutView:
    view = LayoutView(timeout=120)
    c = Container()
    c.add_item(TextDisplay("# 🗑️ Vider la liste des mots bannis ?"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"Tu vas supprimer **{count}** mot(s) définitivement.\n"
        "-# Cette action est irréversible."
    ))
    c.add_item(Separator())

    async def do_clear(interaction: Interaction):
        await mgr.clear_words(guild_id)
        # Retour direct sur la page 2 après purge.
        await _rerender_words(interaction, guild_id, bot, author_id)

    async def cancel(interaction: Interaction):
        # Annuler → retour sur la page 2 sans changement.
        await _rerender_words(interaction, guild_id, bot, author_id)

    btn_confirm = Button(label="Confirmer", style=ButtonStyle.danger, emoji="✅")
    btn_confirm.callback = do_clear
    btn_cancel = Button(label="Annuler", style=ButtonStyle.secondary, emoji="↩️")
    btn_cancel.callback = cancel
    c.add_item(ActionRow(btn_confirm, btn_cancel))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c)
    return view