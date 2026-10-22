"""
views/ticket/panel_setup_view.py — Configuration d'un panel (CV2 pur).

Refonte 2026-10-21 (demande Paul : "je ne suis pas fan des interfaces...
quelque chose d'autre avec un menu — facile de config, intuitif, moderne").

Avant : chaque champ avait sa propre ligne (Section ou bloc de texte) + son
propre bouton crayon — ça faisait beaucoup de composants à l'écran et ça
avait déjà failli dépasser la limite Discord de 40 composants/message une
fois (cf. ancien historique de ce fichier).

Maintenant : un seul écran compact avec UN SEUL menu déroulant natif
(`discord.ui.Select`) qui liste tous les champs configurables. Chaque
option du menu affiche la VALEUR ACTUELLE du champ directement dans sa
description (fonctionnalité native des select Discord) — on voit l'état
complet du panel sans rien ouvrir. Choisir une option ouvre soit un modal
(champs texte), soit le même sous-écran de sélection native qu'avant
(ChannelSelect/RoleSelect — inchangé, cf. views/giveaway/create_view.py
pour le pattern d'origine), puis revient à ce même écran.

Bénéfice secondaire : ce design tient dans une dizaine de composants au
lieu d'une trentaine — bien plus de marge pour ajouter des réglages futurs
sans revivre le quasi-dépassement de la limite Discord.

Principe inchangé : un `ctx` dict mutable accumule la config, consommé par
/ticket panel_create (ctx vide), /ticket panel_edit et le sélecteur de
panel réutilisable (views/ticket/panel_picker.py, ctx pré-rempli via
`build_edit_ctx`).
"""
from __future__ import annotations

import logging
import re
import time

import discord
from discord import ui
from discord.ui import LayoutView, Modal, Select, TextInput

from utils.boutique.gold_manager import is_gold, send_gold_error
from utils.container_universel import error_container, success_container
from utils.perm_admin import is_admin
from utils.managers import ticket_manager as tm
from utils.ticket_limits import (
    DEFAULT_PANEL_EMOJI,
    MAX_STAFF_ROLES_PER_PANEL,
    PANEL_EMOJI_MAX_LENGTH,
    PANEL_IMAGE_URL_MAX_LENGTH,
    PANEL_MESSAGE_MAX_LENGTH,
    PANEL_TITLE_MAX_LENGTH,
    WIZARD_TIMEOUT,
)
from views._components.channel_select import ChannelSelect
from views._components.role_select import RoleSelect
from views.ticket.panel_public_view import PanelPublicView

log = logging.getLogger(__name__)

CATEGORY_TYPES = [discord.ChannelType.category]
TEXT_CHANNEL_TYPES = [discord.ChannelType.text, discord.ChannelType.news]

# Emoji personnalisé Discord : <:nom:id> ou <a:nom:id> (animé).
_CUSTOM_EMOJI_RE = re.compile(r"^<a?:[A-Za-z0-9_~]{2,32}:(\d{15,21})>$")

# Limite d'affichage d'une description de SelectOption (plafond Discord :
# 100 caractères — on garde une petite marge pour l'ellipse).
_DESC_MAX = 95


# ============================================================
# 🔧 Helpers d'affichage
# ============================================================

def _truncate(s: str, n: int = _DESC_MAX) -> str:
    s = " ".join(s.split())  # aplatit les retours à la ligne pour une description sur 1 ligne
    return s if len(s) <= n else s[: n - 1] + "…"


def _desc_channel(guild: discord.Guild, channel_id, *, optional: bool) -> str:
    if not channel_id:
        return "Non défini (optionnel)" if optional else "⚠️ Non défini"
    ch = guild.get_channel(int(channel_id))
    return f"#{ch.name}" if ch else "⚠️ Salon introuvable"


def _desc_role(guild: discord.Guild, role_id) -> str:
    if not role_id:
        return "Non défini (optionnel)"
    role = guild.get_role(int(role_id))
    return f"@{role.name}" if role else "⚠️ Rôle introuvable"


def _desc_roles_list(guild: discord.Guild, role_ids: list) -> str:
    if not role_ids:
        return "⚠️ Non défini"
    names = []
    for rid in role_ids:
        role = guild.get_role(int(rid))
        names.append(f"@{role.name}" if role else "rôle introuvable")
    return ", ".join(names)


def _check_complete(ctx: dict) -> tuple[bool, list]:
    missing = []
    if not ctx.get("title"):                 missing.append("Titre")
    if not ctx.get("panel_message"):         missing.append("Message")
    if not ctx.get("ticket_category_id"):    missing.append("Catégorie")
    if not ctx.get("transcript_channel_id"): missing.append("Transcript")
    if not ctx.get("staff_roles"):           missing.append("Rôles staff")
    return (len(missing) == 0, missing)


async def _check_admin(interaction: discord.Interaction) -> bool:
    if not is_admin(interaction):
        await interaction.response.send_message(
            view=error_container("Vous devez être administrateur pour cette action."),
            ephemeral=True,
        )
        return False
    return True


async def _refresh(interaction: discord.Interaction, guild: discord.Guild, ctx: dict):
    await interaction.edit_original_response(view=build_setup_view(guild, ctx))


def _parse_panel_emoji(value: str, client: discord.Client) -> str | None:
    """
    Valide et normalise un emoji saisi par un admin. Renvoie la représentation
    à stocker (texte brut, réutilisable tel quel comme `emoji=` d'un Button ou
    dans un TextDisplay), ou None si l'entrée n'est pas un emoji valide.

    - Emoji personnalisé `<:nom:id>`/`<a:nom:id>` : accepté seulement si le
      bot a effectivement accès à cet emoji (sinon il s'afficherait cassé
      pour tout le monde — même logique qu'un sélecteur d'emoji Discord qui
      ne propose que les emojis accessibles).
    - Emoji unicode classique (🎫, 🔥, etc.) : accepté s'il contient au moins
      un caractère non-ASCII (un emoji n'est jamais composé uniquement de
      caractères ASCII) dans une longueur raisonnable (large marge pour les
      séquences avec variante de peau/ZWJ).
    - Tout le reste (texte brut, ID mal formé, > un seul "token"...) : rejeté.
    """
    custom_match = _CUSTOM_EMOJI_RE.match(value)
    if custom_match:
        emoji_id = int(custom_match.group(1))
        return value if client.get_emoji(emoji_id) is not None else None

    if "<" in value or ">" in value:
        # Ressemble à un emoji personnalisé mal formé — on rejette plutôt que
        # de stocker un texte cassé qui s'afficherait tel quel sur le bouton.
        return None

    if not value or len(value) > 16 or all(ord(c) < 128 for c in value):
        return None
    return value


def _parse_panel_image_url(value: str) -> str | None:
    """
    Valide une URL d'image de bannière. Pas de vérification réseau (le bot ne
    télécharge rien pour "voir" si c'est une image) — juste un garde-fou
    basique : schéma https, pas d'espace, longueur raisonnable. Une URL
    acceptée mais qui ne pointe pas vers une image réelle échoue simplement à
    s'afficher côté Discord (MediaGallery cassé, non bloquant) — même logique
    pragmatique que la validation d'emoji ci-dessus.
    """
    value = value.strip()
    if not value or " " in value or len(value) > PANEL_IMAGE_URL_MAX_LENGTH:
        return None
    if not value.lower().startswith("https://"):
        return None
    return value


# ============================================================
# 🧾 Champs du menu — ordre d'affichage, description courante, action
# ============================================================
# Chaque entrée : (value, emoji, label, kind). `kind` pilote le dispatch
# dans _FieldSelect.callback (modal texte / sous-écran salon / sous-écran
# rôle / cas spéciaux emoji+image).

_FIELD_ORDER = [
    ("title_message", "📝", "Titre & Message"),
    ("panel_emoji", "🙂", "Emoji du panel"),
    ("panel_image_url", "🖼️", "Image du panel (Gold+)"),
    ("ticket_category_id", "📁", "Catégorie des tickets"),
    ("backup_category_id", "🆘", "Catégorie de secours"),
    ("transcript_channel_id", "📄", "Salon transcript"),
    ("closed_category_id", "🔒", "Catégorie tickets fermés"),
    ("staff_roles", "👥", "Rôles staff"),
    ("ping_role_id", "🔔", "Rôle ping à l'ouverture"),
    ("role_ban_ticket_id", "🚫", "Rôle ban ticket"),
]


def _field_description(guild: discord.Guild, ctx: dict, value: str) -> str:
    if value == "title_message":
        title = ctx.get("title")
        if not title:
            return "⚠️ Non défini"
        msg = ctx.get("panel_message") or ""
        return _truncate(f"{title} — {msg}" if msg else title)
    if value == "panel_emoji":
        return ctx.get("panel_emoji") or f"Non défini (défaut : {DEFAULT_PANEL_EMOJI})"
    if value == "panel_image_url":
        if not is_gold(guild.id):
            return "🔒 Réservé aux serveurs Gold+"
        url = ctx.get("panel_image_url")
        return _truncate(url) if url else "Non défini (optionnel)"
    if value == "ticket_category_id":
        return _desc_channel(guild, ctx.get("ticket_category_id"), optional=False)
    if value == "backup_category_id":
        return _desc_channel(guild, ctx.get("backup_category_id"), optional=True)
    if value == "transcript_channel_id":
        return _desc_channel(guild, ctx.get("transcript_channel_id"), optional=False)
    if value == "closed_category_id":
        return _desc_channel(guild, ctx.get("closed_category_id"), optional=True)
    if value == "staff_roles":
        return _truncate(_desc_roles_list(guild, ctx.get("staff_roles", [])))
    if value == "ping_role_id":
        return _desc_role(guild, ctx.get("ping_role_id"))
    if value == "role_ban_ticket_id":
        return _desc_role(guild, ctx.get("role_ban_ticket_id"))
    return "Non défini"


# ============================================================
# 🪟 Vue principale — dashboard + menu déroulant
# ============================================================

def build_setup_view(guild: discord.Guild, ctx: dict, locked: bool = False) -> LayoutView:
    view = LayoutView(timeout=WIZARD_TIMEOUT)
    container = ui.Container()

    is_edit = bool(ctx.get("panel_id"))
    is_complete, missing = _check_complete(ctx)
    header = "✏️ Modifier le panel" if is_edit else "🎫 Créer un panel de tickets"

    if locked:
        status = "✅ Panel enregistré — cette fenêtre est terminée."
    elif is_complete:
        status = "✅ Prêt à être validé"
    else:
        status = f"⚠️ Manquant : {', '.join(missing)}"

    container.add_item(ui.TextDisplay(f"# {header}"))
    container.add_item(ui.TextDisplay(f"-# {status}"))
    container.add_item(ui.Separator())

    options = [
        discord.SelectOption(
            label=label,
            value=value,
            description=_field_description(guild, ctx, value),
            emoji=emoji,
        )
        for value, emoji, label in _FIELD_ORDER
    ]
    select = _FieldSelect(guild=guild, ctx=ctx, options=options, disabled=locked)
    container.add_item(ui.ActionRow(select))
    container.add_item(ui.Separator())

    validate_label = "✅ Mettre à jour le panel" if is_edit else "✅ Créer le panel"
    btn_validate = ui.Button(
        label=validate_label,
        style=discord.ButtonStyle.success if not locked else discord.ButtonStyle.secondary,
        disabled=not is_complete or locked,
    )

    async def cb_validate(interaction: discord.Interaction):
        if not await _check_admin(interaction):
            return
        await _finalize_panel(interaction, guild, ctx)

    btn_validate.callback = cb_validate
    container.add_item(ui.ActionRow(btn_validate))
    container.add_item(ui.Separator())
    container.add_item(ui.TextDisplay("-# GuideON — Système de tickets"))

    view.add_item(container)
    return view


class _FieldSelect(Select):
    """Le menu déroulant unique du dashboard : une option par champ
    configurable, choisir une option ouvre le bon modal/sous-écran."""

    def __init__(self, *, guild: discord.Guild, ctx: dict, options, disabled: bool):
        super().__init__(
            placeholder="✏️ Choisir un champ à modifier…",
            options=options,
            min_values=1,
            max_values=1,
            disabled=disabled,
        )
        self._guild = guild
        self._ctx = ctx

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await _check_admin(interaction):
            return

        value = self.values[0]
        guild, ctx = self._guild, self._ctx

        if value == "title_message":
            await interaction.response.send_modal(TitleMessageModal(guild, ctx))
            return
        if value == "panel_emoji":
            await interaction.response.send_modal(PanelEmojiModal(guild, ctx))
            return
        if value == "panel_image_url":
            if not is_gold(guild.id):
                await send_gold_error(interaction)
                return
            await interaction.response.send_modal(PanelImageModal(guild, ctx))
            return
        if value == "ticket_category_id":
            await _opener_category(
                guild, ctx, ctx_key="ticket_category_id",
                title="📁 Catégorie des tickets",
                description="Catégorie où seront créés les nouveaux tickets.",
                optional=False,
            )(interaction)
            return
        if value == "backup_category_id":
            await _opener_category(
                guild, ctx, ctx_key="backup_category_id",
                title="🆘 Catégorie de secours",
                description=(
                    "Optionnelle : si la catégorie principale est pleine, les "
                    "nouveaux tickets sont créés ici à la place."
                ),
                optional=True,
            )(interaction)
            return
        if value == "transcript_channel_id":
            await _opener_text_channel(
                guild, ctx, ctx_key="transcript_channel_id",
                title="📄 Salon transcript",
                description="Salon où seront envoyés les transcripts à la fermeture d'un ticket.",
            )(interaction)
            return
        if value == "closed_category_id":
            await _opener_category(
                guild, ctx, ctx_key="closed_category_id",
                title="📁 Catégorie des tickets fermés",
                description="Optionnelle : catégorie où déplacer un ticket une fois fermé.",
                optional=True,
            )(interaction)
            return
        if value == "staff_roles":
            await _opener_staff_roles(guild, ctx)(interaction)
            return
        if value == "ping_role_id":
            await _opener_role(
                guild, ctx, ctx_key="ping_role_id",
                title="🔔 Rôle ping à l'ouverture",
                description="Optionnel : rôle mentionné dans le salon à chaque nouveau ticket.",
                optional=True,
            )(interaction)
            return
        if value == "role_ban_ticket_id":
            await _opener_role(
                guild, ctx, ctx_key="role_ban_ticket_id",
                title="🚫 Rôle ban ticket",
                description="Optionnel : un membre avec ce rôle ne peut plus ouvrir de ticket.",
                optional=True,
            )(interaction)
            return


# ============================================================
# 🧭 Sous-écrans de sélection native (salons / rôles)
#
# Même pattern que views/giveaway/create_view.py::_cb_channel/_cb_role :
# choisir l'option dans le menu remplace temporairement le dashboard par un
# petit écran avec un select natif Discord (ChannelSelect/RoleSelect) + un
# bouton Annuler (et Retirer si le champ est optionnel et déjà défini).
# Impossible d'y saisir un ID invalide ou un objet du mauvais type — le
# select ne propose que les salons/rôles réellement valides pour ce champ.
# ============================================================

def _back_to_wizard(guild: discord.Guild, ctx: dict):
    async def cb(interaction: discord.Interaction):
        await interaction.response.edit_message(view=build_setup_view(guild, ctx))
    return cb


def _opener_category(
    guild: discord.Guild, ctx: dict, *, ctx_key: str, title: str, description: str, optional: bool,
):
    async def opener(interaction: discord.Interaction) -> None:
        async def on_select(sel: discord.Interaction, channel_id: int) -> None:
            channel = sel.guild.get_channel(channel_id)
            if not isinstance(channel, discord.CategoryChannel):
                await sel.response.send_message(
                    view=error_container("Catégorie introuvable."), ephemeral=True
                )
                return
            ctx[ctx_key] = channel_id
            await sel.response.edit_message(view=build_setup_view(guild, ctx))

        select = ChannelSelect(
            placeholder="Choisir une catégorie", on_select=on_select, channel_types=CATEGORY_TYPES,
        )
        await _show_picker(interaction, guild, ctx, ctx_key, title, description, select, optional)
    return opener


def _opener_text_channel(
    guild: discord.Guild, ctx: dict, *, ctx_key: str, title: str, description: str, optional: bool = False,
):
    async def opener(interaction: discord.Interaction) -> None:
        async def on_select(sel: discord.Interaction, channel_id: int) -> None:
            channel = sel.guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                await sel.response.send_message(
                    view=error_container("Salon textuel introuvable."), ephemeral=True
                )
                return
            ctx[ctx_key] = channel_id
            await sel.response.edit_message(view=build_setup_view(guild, ctx))

        select = ChannelSelect(
            placeholder="Choisir un salon", on_select=on_select, channel_types=TEXT_CHANNEL_TYPES,
        )
        await _show_picker(interaction, guild, ctx, ctx_key, title, description, select, optional)
    return opener


def _opener_role(
    guild: discord.Guild, ctx: dict, *, ctx_key: str, title: str, description: str, optional: bool,
):
    async def opener(interaction: discord.Interaction) -> None:
        async def on_select(sel: discord.Interaction, role_ids: list[int]) -> None:
            if not role_ids:
                return
            role = sel.guild.get_role(role_ids[0])
            if role is None:
                await sel.response.send_message(
                    view=error_container("Rôle introuvable."), ephemeral=True
                )
                return
            if role.is_default():
                await sel.response.send_message(
                    view=error_container(
                        "Le rôle **@everyone** ne peut pas être utilisé ici."
                    ),
                    ephemeral=True,
                )
                return
            ctx[ctx_key] = role.id
            await sel.response.edit_message(view=build_setup_view(guild, ctx))

        select = RoleSelect(
            placeholder="Choisir un rôle", on_select=on_select, min_values=1, max_values=1,
        )
        await _show_picker(interaction, guild, ctx, ctx_key, title, description, select, optional)
    return opener


def _opener_staff_roles(guild: discord.Guild, ctx: dict):
    async def opener(interaction: discord.Interaction) -> None:
        async def on_select(sel: discord.Interaction, role_ids: list[int]) -> None:
            if not role_ids:
                await sel.response.send_message(
                    view=error_container("Sélectionnez au moins un rôle."), ephemeral=True
                )
                return
            roles = [sel.guild.get_role(rid) for rid in role_ids]
            if any(r is None for r in roles):
                await sel.response.send_message(
                    view=error_container("Un des rôles sélectionnés est introuvable."),
                    ephemeral=True,
                )
                return
            if any(r.is_default() for r in roles):
                await sel.response.send_message(
                    view=error_container(
                        "Le rôle **@everyone** ne peut pas être staff "
                        "(cela rendrait les tickets visibles par tout le monde)."
                    ),
                    ephemeral=True,
                )
                return
            ctx["staff_roles"] = role_ids
            await sel.response.edit_message(view=build_setup_view(guild, ctx))

        select = RoleSelect(
            placeholder=f"Choisir 1 à {MAX_STAFF_ROLES_PER_PANEL} rôle(s) staff",
            on_select=on_select, min_values=1, max_values=MAX_STAFF_ROLES_PER_PANEL,
        )
        await _show_picker(
            interaction, guild, ctx, "staff_roles",
            "👥 Rôles staff",
            f"Sélectionnez 1 à {MAX_STAFF_ROLES_PER_PANEL} rôle(s) — remplace la liste actuelle.",
            select, optional=False,
        )
    return opener


async def _show_picker(
    interaction: discord.Interaction,
    guild: discord.Guild,
    ctx: dict,
    ctx_key: str,
    title: str,
    description: str,
    select,
    optional: bool,
) -> None:
    """Affiche le sous-écran commun (select + Annuler [+ Retirer]) et édite le message en place."""

    async def on_clear(clear_inter: discord.Interaction) -> None:
        ctx[ctx_key] = None
        await clear_inter.response.edit_message(view=build_setup_view(guild, ctx))

    btn_cancel = ui.Button(label="Annuler", style=discord.ButtonStyle.secondary, emoji="↩️")
    btn_cancel.callback = _back_to_wizard(guild, ctx)

    temp = LayoutView(timeout=WIZARD_TIMEOUT)
    c = ui.Container()
    c.add_item(ui.TextDisplay(f"# {title}"))
    c.add_item(ui.TextDisplay(f"-# {description}"))
    c.add_item(ui.Separator())
    c.add_item(ui.ActionRow(select))
    c.add_item(ui.Separator())

    if optional and ctx.get(ctx_key):
        btn_clear = ui.Button(label="Retirer", style=discord.ButtonStyle.danger, emoji="🗑️")
        btn_clear.callback = on_clear
        c.add_item(ui.ActionRow(btn_clear, btn_cancel))
    else:
        c.add_item(ui.ActionRow(btn_cancel))

    temp.add_item(c)
    await interaction.response.edit_message(view=temp)


# ============================================================
# 📝 Modals (champs texte uniquement : titre, message, emoji, image)
# ============================================================

class TitleMessageModal(Modal):
    def __init__(self, guild, ctx):
        super().__init__(title="✏️ Titre & Message")
        self.guild, self.ctx = guild, ctx
        self.title_input = TextInput(
            label="Titre", default=ctx.get("title", ""), required=True, max_length=PANEL_TITLE_MAX_LENGTH,
        )
        self.message_input = TextInput(
            label="Message", default=ctx.get("panel_message", ""),
            style=discord.TextStyle.paragraph, required=True, max_length=PANEL_MESSAGE_MAX_LENGTH,
        )
        self.add_item(self.title_input)
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.ctx["title"] = self.title_input.value
        self.ctx["panel_message"] = self.message_input.value
        await interaction.response.defer()
        await _refresh(interaction, self.guild, self.ctx)


class PanelEmojiModal(Modal):
    def __init__(self, guild, ctx):
        super().__init__(title="✏️ Emoji du panel")
        self.guild, self.ctx = guild, ctx
        self.input = TextInput(
            label=f"Emoji (vide = {DEFAULT_PANEL_EMOJI} par défaut)",
            default=ctx.get("panel_emoji") or "",
            required=False,
            max_length=PANEL_EMOJI_MAX_LENGTH,
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        val = self.input.value.strip()
        if not val:
            self.ctx["panel_emoji"] = None
        else:
            parsed = _parse_panel_emoji(val, interaction.client)
            if parsed is None:
                return await interaction.response.send_message(
                    view=error_container(
                        "Emoji invalide. Utilisez un emoji unicode (🎫) ou un emoji "
                        "personnalisé auquel le bot a accès (`<:nom:id>`)."
                    ),
                    ephemeral=True,
                )
            self.ctx["panel_emoji"] = parsed
        await interaction.response.defer()
        await _refresh(interaction, self.guild, self.ctx)


class PanelImageModal(Modal):
    """Modal Gold+ — l'accès est déjà vérifié par l'appelant (_FieldSelect)
    avant d'ouvrir ce modal ; pas de double vérification ici."""

    def __init__(self, guild, ctx):
        super().__init__(title="✏️ Image du panel (Gold+)")
        self.guild, self.ctx = guild, ctx
        self.input = TextInput(
            label="URL de l'image (vide = aucune)",
            default=ctx.get("panel_image_url") or "",
            required=False,
            max_length=PANEL_IMAGE_URL_MAX_LENGTH,
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        val = self.input.value.strip()
        if not val:
            self.ctx["panel_image_url"] = None
        else:
            parsed = _parse_panel_image_url(val)
            if parsed is None:
                return await interaction.response.send_message(
                    view=error_container(
                        "URL invalide. Utilisez un lien **https://** direct vers une image "
                        "(sans espace)."
                    ),
                    ephemeral=True,
                )
            self.ctx["panel_image_url"] = parsed
        await interaction.response.defer()
        await _refresh(interaction, self.guild, self.ctx)


# ============================================================
# 🏗️ Construction du ctx depuis un panel existant (édition)
# ============================================================

def build_edit_ctx(panel: dict) -> dict:
    """Construit le `ctx` du dashboard depuis un dict panel (manager.to_dict()).

    Factorisé ici pour être partagé par /ticket panel_edit ET le sélecteur
    de panel réutilisable (views/ticket/panel_picker.py) — avant cette
    factorisation, panel_edit construisait ce dict en ligne dans son propre
    fichier, avec un risque de divergence si un nouveau champ était ajouté
    d'un côté et oublié de l'autre.
    """
    return {
        "panel_id": panel["panel_id"],
        "channel_id": panel["channel_id"],
        "message_id": panel["message_id"],
        "title": panel["title"],
        "panel_message": panel["panel_message"],
        "ticket_category_id": panel["ticket_category_id"],
        "transcript_channel_id": panel["transcript_channel_id"],
        "closed_category_id": panel.get("closed_category_id"),
        "backup_category_id": panel.get("backup_category_id"),
        "panel_emoji": panel.get("panel_emoji"),
        "panel_image_url": panel.get("panel_image_url"),
        "ping_role_id": panel.get("ping_role_id"),
        "role_ban_ticket_id": panel.get("role_ban_ticket_id"),
        "staff_roles": list(panel.get("staff_roles", [])),
        "counter": panel.get("counter", 1),
    }


# ============================================================
# ✅ Finalisation
# ============================================================

async def _finalize_panel(interaction: discord.Interaction, guild: discord.Guild, ctx: dict):
    await interaction.response.defer(ephemeral=True)

    guild_id = guild.id
    is_edit = bool(ctx.get("panel_id"))
    panel_id = ctx.get("panel_id") or f"panel_{int(time.time())}"
    channel_id = ctx.get("channel_id") or interaction.channel_id
    channel = guild.get_channel(channel_id)

    if not isinstance(channel, discord.TextChannel):
        return await interaction.followup.send(
            view=error_container("Salon d'envoi invalide."), ephemeral=True
        )

    panel_view = PanelPublicView(
        panel_id=panel_id, guild_id=guild_id,
        title=ctx["title"], message=ctx["panel_message"],
        emoji=ctx.get("panel_emoji"),
        image_url=ctx.get("panel_image_url"),
    )

    # Poste ou édite le message public
    try:
        if ctx.get("message_id"):
            try:
                msg = await channel.fetch_message(ctx["message_id"])
                await msg.edit(view=panel_view)
            except discord.HTTPException:
                msg = await channel.send(view=panel_view)
        else:
            msg = await channel.send(view=panel_view)
    except discord.HTTPException as e:
        return await interaction.followup.send(
            view=error_container(f"Erreur Discord : {e}"), ephemeral=True
        )

    # Persiste en DB
    try:
        if is_edit:
            await tm.update_panel(
                guild_id, panel_id,
                staff_role_ids=ctx["staff_roles"],
                channel_id=channel.id,
                message_id=msg.id,
                title=ctx["title"],
                panel_message=ctx["panel_message"],
                ticket_category_id=ctx["ticket_category_id"],
                transcript_channel_id=ctx["transcript_channel_id"],
                closed_category_id=ctx.get("closed_category_id"),
                backup_category_id=ctx.get("backup_category_id"),
                panel_emoji=ctx.get("panel_emoji"),
                panel_image_url=ctx.get("panel_image_url"),
                ping_role_id=ctx.get("ping_role_id"),
                role_ban_ticket_id=ctx.get("role_ban_ticket_id"),
            )
        else:
            await tm.create_panel(
                guild_id=guild_id, panel_id=panel_id,
                channel_id=channel.id, message_id=msg.id,
                title=ctx["title"], panel_message=ctx["panel_message"],
                ticket_category_id=ctx["ticket_category_id"],
                transcript_channel_id=ctx["transcript_channel_id"],
                staff_role_ids=ctx["staff_roles"],
                closed_category_id=ctx.get("closed_category_id"),
                backup_category_id=ctx.get("backup_category_id"),
                panel_emoji=ctx.get("panel_emoji"),
                panel_image_url=ctx.get("panel_image_url"),
                ping_role_id=ctx.get("ping_role_id"),
                role_ban_ticket_id=ctx.get("role_ban_ticket_id"),
                counter=ctx.get("counter", 1),
            )
    except Exception:
        log.exception("Persistance du panel échouée (guild=%s, panel=%s)", guild_id, panel_id)
        return await interaction.followup.send(
            view=error_container("Le panel a été posté mais la sauvegarde a échoué."),
            ephemeral=True,
        )

    # Réenregistre la vue persistante pour le process courant
    try:
        interaction.client.add_view(panel_view, message_id=msg.id)
    except Exception:
        pass

    # Verrouille le dashboard + confirme
    ctx["panel_id"] = panel_id
    ctx["message_id"] = msg.id
    await interaction.edit_original_response(view=build_setup_view(guild, ctx, locked=True))

    action = "mis à jour" if is_edit else "créé"
    await interaction.followup.send(
        view=success_container(
            f"Le panel **{ctx['title']}** a été {action} dans {channel.mention}."
        ),
        ephemeral=True,
    )
