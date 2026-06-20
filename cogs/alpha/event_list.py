"""
cogs/alpha/event_list.py — Affiche les events M+ du Alpha
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.botbancmd import verifier_ban_utilisateur
from utils.perm_alpha import check_modo_plus
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.events_alpha import load_events, get_event, STATUS_EMOJIS, STATUS_LABELS

log = logging.getLogger(__name__)


# ============================================================
# 🧩 Création de la view principale
# ============================================================

class EventListView(LayoutView):
    """Vue principale : select menu des events."""

    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, i: Interaction) -> bool:
        if i.user.id != self.owner_id:
            await i.response.send_message("Seul l'**auteur** peut utiliser ce __menu__.", ephemeral=True)
            return False
        return True

    def _build(self) -> None:
        events = load_events()
        c = Container()
        c.add_item(TextDisplay("## 🗂️ Liste des Events Alpha"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**{len(events)} events** disponibles."
        ))

        select = discord.ui.Select(
            placeholder="Choisir un event…",
            options=[
                discord.SelectOption(
                    label=e["name"],
                    value=str(e["id"]),
                    emoji=STATUS_EMOJIS.get(e["status"], "?"),
                    description=STATUS_LABELS.get(e["status"], e["status"]),
                )
                for e in events
            ],
            min_values=1, max_values=1,
            custom_id="event_list_sel",
        )
        select.callback = self._on_select
        c.add_item(ActionRow(select))
        c.add_item(Separator())

        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_select(self, i: Interaction) -> None:
        event_id = int(i.data["values"][0])
        event = get_event(event_id)
        if event is None:
            return await i.response.send_message("Event introuvable.", ephemeral=True)
        await i.response.edit_message(view=EventDetailView(event, self.owner_id))


# ============================================================
# 🧩 Création de la view détail
# ============================================================

class EventDetailView(LayoutView):
    """Vue détail d'un event avec bouton retour."""

    def __init__(self, event: dict, owner_id: int) -> None:
        super().__init__(timeout=180)
        self.event = event
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, i: Interaction) -> bool:
        return i.user.id == self.owner_id

    def _build(self) -> None:
        e = self.event
        status_emoji = STATUS_EMOJIS.get(e["status"], "?")
        status_label = STATUS_LABELS.get(e["status"], e["status"])

        c = Container()
        c.add_item(TextDisplay(f"# 🎮 {e['name']}"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**Statut :** {status_emoji} {status_label}\n"
            f"**Warp :** `{e['warp']}`\n\n"
            f"**Description :**\n{e['description']}"
        ))
        c.add_item(Separator())

        btn_back = Button(label="<:retour:1515658955190308995> Retour à la liste", style=discord.ButtonStyle.secondary, custom_id="ev_back")
        btn_back.callback = self._on_back
        c.add_item(ActionRow(btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_back(self, i: Interaction) -> None:
        await i.response.edit_message(view=EventListView(self.owner_id))


# ============================================================
# 🧭 Commande : /alpha event_list
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="event_list", description="🗂️ [M+] Affiche la liste des events Alpha")
async def event_list(interaction: Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction): return

    # 🔐 Vérification des permissions.
    if not await check_modo_plus(interaction, "**consulter** la liste des __events__"): return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "alpha_event_list"): return

    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_event_list")

    # ✉️ Envoi du menu
    await interaction.followup.send(view=EventListView(interaction.user.id), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@event_list.error
async def event_list_error(i: discord.Interaction, e: app_commands.AppCommandError):
    await handle_app_command_error(i, e)