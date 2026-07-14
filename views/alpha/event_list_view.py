"""
views/alpha/event_list_view.py — Liste et détail des events Alpha.

Extrait de cogs/alpha/event_list.py (même traitement que derank : le cog
se réduit à la commande, les views vivent ici). Branché sur BaseLayoutView —
panneau strictement personnel envoyé en followup éphémère, donc owner_id =
auteur de la commande.
"""
from __future__ import annotations

from discord import ButtonStyle, Interaction, SelectOption
from discord.ui import ActionRow, Button, Container, Select, Separator, TextDisplay

from utils.container_universel import error_container
from utils.events_alpha import STATUS_EMOJIS, STATUS_LABELS, get_event, load_events
from views._components.base_view import BaseLayoutView


# ============================================================
# 🧩 Vue principale : liste des events
# ============================================================

class EventListView(BaseLayoutView):
    """Vue principale : select menu des events."""

    def __init__(self, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=180)
        self._build()

    def _build(self) -> None:
        events = load_events()
        c = Container()
        c.add_item(TextDisplay("## 🗂️ Liste des Events Alpha"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**{len(events)} events** disponibles."
        ))

        select = Select(
            placeholder="Choisir un event…",
            options=[
                SelectOption(
                    label=e["name"],
                    value=str(e["id"]),
                    emoji=STATUS_EMOJIS.get(e["status"], "?"),
                    description=STATUS_LABELS.get(e["status"], e["status"]),
                )
                for e in events
            ],
            min_values=1, max_values=1,
        )
        select.callback = self._on_select
        c.add_item(ActionRow(select))
        c.add_item(Separator())

        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_select(self, interaction: Interaction) -> None:
        event_id = int(interaction.data["values"][0])
        event = get_event(event_id)
        if event is None:
            await interaction.response.send_message(
                view=error_container("Event **introuvable**."), ephemeral=True
            )
            return
        await interaction.response.edit_message(view=EventDetailView(event, self.owner_id))


# ============================================================
# 🧩 Vue détail d'un event
# ============================================================

class EventDetailView(BaseLayoutView):
    """Vue détail d'un event avec bouton retour."""

    def __init__(self, event: dict, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=180)
        self.event = event
        self._build()

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

        # Note : l'emoji va dans le paramètre `emoji=`, pas dans `label=`
        # (même correction que sur derank_view.py).
        btn_back = Button(
            label="Retour à la liste",
            style=ButtonStyle.secondary,
            emoji="<:retour:1515658955190308995>",
        )
        btn_back.callback = self._on_back
        c.add_item(ActionRow(btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(view=EventListView(self.owner_id))