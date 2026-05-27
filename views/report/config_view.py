"""
views/report/config_view.py — Vues CV2 + Modals de /report (refacto V4).

Changements vs l'ancien ReportView.py :
- Callbacks attachés aux boutons (plus de routing global on_interaction).
- Importance via Select (menu déroulant) au lieu d'un modal texte fragile.
- error_container importé de utils.container_universel (plus de redéfinition).
- Draft géré par bug_report_manager (mémoire) ; report finalisé en DB.
- URL d'image validée avant affichage en MediaGallery.

Les vues sans état (home/success/cancel) ont timeout=None ; la vue form a un
timeout de 300s (le draft expire de toute façon en 30 min côté manager).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import discord
from discord import ButtonStyle, Interaction, SelectOption, MediaGalleryItem
from discord.ui import (
    ActionRow,
    Button,
    Container,
    LayoutView,
    MediaGallery,
    Modal,
    Section,
    Select,
    Separator,
    TextDisplay,
    TextInput,
)

from utils.container_universel import error_container, success_container
from utils.managers.bug_report_manager import (
    clear_draft,
    create_report_from_draft,
    get_draft,
)

log = logging.getLogger(__name__)

FOOTER = "-# GuideON Studio"

IMPORTANCE_OPTIONS = [
    ("gênant", "🟡", "Désagréable mais contournable"),
    ("important", "🟠", "Gêne réellement l'utilisation"),
    ("critique", "🔴", "Empêche d'utiliser une fonctionnalité"),
]

# Validation simple d'URL d'image (http/https + extension image courante,
# ou domaines CDN Discord/Imgur).
_IMG_RE = re.compile(
    r"^https?://.+\.(png|jpe?g|gif|webp)(\?.*)?$", re.IGNORECASE
)
_CDN_HOSTS = ("cdn.discordapp.com", "media.discordapp.net", "imgur.com", "i.imgur.com")


def _is_valid_image_url(url: str) -> bool:
    if not url:
        return False
    if _IMG_RE.match(url):
        return True
    return url.startswith("https://") and any(h in url for h in _CDN_HOSTS)


# ============================================================
# 🏠 HOME
# ============================================================

def home_view() -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# ⚠️ Signaler un problème"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        "Merci de contribuer à **améliorer** le bot.\n"
        "-# Ce formulaire te permet de remonter ton problème facilement."
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        "### Ce que tu peux signaler\n"
        "• Bug d'une fonctionnalité\n"
        "• Comportements inattendus\n"
        "• Problèmes d'affichage\n"
        "• Permissions incorrectes"
    ))
    c.add_item(Separator())

    start = Button(label="Commencer", emoji="✅", style=ButtonStyle.primary)
    cancel = Button(label="Annuler", emoji="✖️", style=ButtonStyle.secondary)

    async def start_cb(it: Interaction):
        clear_draft(it.user.id)
        await it.response.edit_message(view=form_view(it.user.id))

    async def cancel_cb(it: Interaction):
        clear_draft(it.user.id)
        await it.response.edit_message(view=cancel_view())

    start.callback = start_cb
    cancel.callback = cancel_cb
    c.add_item(ActionRow(start, cancel))
    c.add_item(Separator())
    c.add_item(TextDisplay(FOOTER))
    view.add_item(c)
    return view


# ============================================================
# 📝 MODALS (titre/desc, capture) + SELECT (importance)
# ============================================================

class TitleDescriptionModal(Modal, title="📝 Titre & Description"):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        draft = get_draft(user_id)
        self.title_input = TextInput(
            label="Titre", placeholder="Ex : Le bot ne répond pas à /...",
            default=draft.title or "", max_length=100, required=True,
        )
        self.desc_input = TextInput(
            label="Description", style=discord.TextStyle.paragraph,
            placeholder="Explique le problème le plus précisément possible.",
            default=draft.description or "", max_length=1000, required=True,
        )
        self.add_item(self.title_input)
        self.add_item(self.desc_input)

    async def on_submit(self, it: Interaction):
        draft = get_draft(self.user_id)
        draft.title = self.title_input.value.strip()
        draft.description = self.desc_input.value.strip()
        await it.response.edit_message(view=form_view(self.user_id))


class AttachmentModal(Modal, title="🖼️ Capture d'écran (URL)"):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        draft = get_draft(user_id)
        self.url_input = TextInput(
            label="URL de l'image",
            placeholder="https://cdn.discordapp.com/... ou https://i.imgur.com/...",
            default=draft.attachment_url or "", required=False,
        )
        self.add_item(self.url_input)

    async def on_submit(self, it: Interaction):
        draft = get_draft(self.user_id)
        url = self.url_input.value.strip()
        if url and not _is_valid_image_url(url):
            return await it.response.send_message(
                view=error_container(
                    "URL d'image invalide.\n"
                    "-# Formats acceptés : .png .jpg .gif .webp, ou un lien Discord/Imgur."
                ),
                ephemeral=True,
            )
        draft.attachment_url = url or None
        await it.response.edit_message(view=form_view(self.user_id))


class ImportanceSelect(Select):
    def __init__(self, user_id: int, current: Optional[str]):
        self.user_id = user_id
        options = [
            SelectOption(label=label.capitalize(), value=label, emoji=emoji,
                         description=desc, default=(label == current))
            for label, emoji, desc in IMPORTANCE_OPTIONS
        ]
        super().__init__(placeholder="Choisir le niveau d'importance…",
                         min_values=1, max_values=1, options=options)

    async def callback(self, it: Interaction):
        draft = get_draft(self.user_id)
        draft.importance = self.values[0]
        await it.response.edit_message(view=form_view(self.user_id))


# ============================================================
# 🧩 FORM
# ============================================================

def form_view(user_id: int) -> LayoutView:
    draft = get_draft(user_id)
    view = LayoutView(timeout=300)
    c = Container()

    c.add_item(TextDisplay("# 📋 Nouveau report"))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# Remplis chaque section puis envoie ton report."))
    c.add_item(Separator())

    # Titre & description
    btn_td = Button(label="Modifier", emoji="✏️", style=ButtonStyle.primary)

    async def td_cb(it: Interaction):
        await it.response.send_modal(TitleDescriptionModal(user_id))

    btn_td.callback = td_cb
    c.add_item(Section(
        TextDisplay(
            f"**Titre**\n{draft.title or '⬜ Non défini'}\n\n"
            f"**Description**\n{draft.description or '⬜ Non définie'}"
        ),
        accessory=btn_td,
    ))
    c.add_item(Separator())

    # Importance (Select)
    c.add_item(TextDisplay(f"**Importance**\n{draft.importance.capitalize() if draft.importance else '⬜ Non définie'}"))
    c.add_item(ActionRow(ImportanceSelect(user_id, draft.importance)))
    c.add_item(Separator())

    # Capture
    btn_att = Button(label="Ajouter", emoji="🖼️", style=ButtonStyle.secondary)

    async def att_cb(it: Interaction):
        await it.response.send_modal(AttachmentModal(user_id))

    btn_att.callback = att_cb
    c.add_item(Section(
        TextDisplay(f"**Capture d'écran**\n{draft.attachment_url or '⬜ Aucune'}"),
        accessory=btn_att,
    ))
    c.add_item(Separator())

    # Actions
    btn_submit = Button(label="Envoyer", emoji="📨", style=ButtonStyle.success,
                        disabled=not draft.is_complete())
    btn_reset = Button(label="Réinitialiser", emoji="🔄", style=ButtonStyle.secondary)
    btn_cancel = Button(label="Annuler", emoji="✖️", style=ButtonStyle.danger)

    async def reset_cb(it: Interaction):
        clear_draft(it.user.id)
        await it.response.edit_message(view=form_view(it.user.id))

    async def cancel_cb(it: Interaction):
        clear_draft(it.user.id)
        await it.response.edit_message(view=cancel_view())

    async def submit_cb(it: Interaction):
        d = get_draft(it.user.id)
        if not d.is_complete():
            return await it.response.send_message(
                view=error_container("Veuillez remplir tous les champs obligatoires."),
                ephemeral=True,
            )
        try:
            report = await create_report_from_draft(
                d, it.user.id, str(it.user),
                it.guild.id if it.guild else None,
            )
        except ValueError:
            return await it.response.send_message(
                view=error_container("Le brouillon est incomplet ou invalide."),
                ephemeral=True,
            )
        # Envoi aux devs (import tardif pour éviter tout cycle)
        from views.report.dev_report import send_to_devs
        try:
            await send_to_devs(it.client, report, it.user)
        except Exception:
            log.exception("Envoi du report %s aux devs échoué", report["reference"])
        clear_draft(it.user.id)
        await it.response.edit_message(view=success_view(report["reference"]))

    btn_reset.callback = reset_cb
    btn_cancel.callback = cancel_cb
    btn_submit.callback = submit_cb

    c.add_item(ActionRow(btn_submit, btn_reset, btn_cancel))
    c.add_item(TextDisplay(FOOTER))
    view.add_item(c)
    return view


# ============================================================
# 🎉 SUCCESS / ✖️ CANCEL
# ============================================================

def success_view(reference: str) -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# ✅ Report envoyé !"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"Merci pour ton aide !\n"
        f"**Référence :** `{reference}`\n"
        "Notre équipe va l'examiner dans les plus brefs délais."
    ))
    c.add_item(Separator())

    btn_new = Button(label="Nouveau", emoji="➕", style=ButtonStyle.primary)
    btn_close = Button(label="Fermer", emoji="✖️", style=ButtonStyle.secondary)

    async def new_cb(it: Interaction):
        clear_draft(it.user.id)
        await it.response.edit_message(view=home_view())

    async def close_cb(it: Interaction):
        clear_draft(it.user.id)
        await it.response.edit_message(view=cancel_view())

    btn_new.callback = new_cb
    btn_close.callback = close_cb
    c.add_item(ActionRow(btn_new, btn_close))
    c.add_item(TextDisplay(FOOTER))
    view.add_item(c)
    return view


def cancel_view() -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# ✖️ Report annulé"))
    c.add_item(Separator())
    c.add_item(TextDisplay("Ton signalement a été annulé."))
    c.add_item(Separator())

    btn_restart = Button(label="Faire un report", emoji="➕", style=ButtonStyle.primary)

    async def restart_cb(it: Interaction):
        clear_draft(it.user.id)
        await it.response.edit_message(view=home_view())

    btn_restart.callback = restart_cb
    c.add_item(ActionRow(btn_restart))
    c.add_item(TextDisplay(FOOTER))
    view.add_item(c)
    return view