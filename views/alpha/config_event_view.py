"""
views/alpha/config_event_view.py — Dashboard configuration Système Events Alpha.

Sections :
  Vue principale → aperçu + [📡 Salon, 🔔 Rôle Ping, 🎮 Statuts, ↩️]
  _ChannelView  → ChannelSelect
  _RoleView     → RoleSelect
  _StatusView   → Select event → boutons statut
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.managers.alpha_event_config_manager import load_event_config, save_event_config
from utils.events_alpha import load_events, get_event, update_event_status, STATUS_EMOJIS, STATUS_LABELS, STATUS_VALUES
from views._components.channel_select import ChannelSelect
from views._components.role_select import RoleSelect

log = logging.getLogger(__name__)

_ch   = lambda v: f"<#{v}>" if v else "*Non configuré*"
_role = lambda v: f"<@&{v}>" if v else "*Non configuré*"


# ── retour vers main ──────────────────────────────────────────

def _back_main(gid, oid):
    async def _fn(i):
        cfg = await load_event_config(gid)
        await i.response.edit_message(view=EventConfigView(gid, cfg, oid))
    return _fn


# ════════════════════════════════════════════════════════════
# 🏠 Vue principale
# ════════════════════════════════════════════════════════════

class EventConfigView(LayoutView):
    def __init__(self, guild_id: int, cfg: dict, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.cfg = cfg
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, i):
        if i.user.id != self.owner_id:
            await i.response.send_message("Seul l'auteur peut utiliser ce menu.", ephemeral=True)
            return False
        return True

    def _build(self) -> None:
        events = load_events()
        nb_ok   = sum(1 for e in events if e["status"] == "fonctionne")
        nb_maint = sum(1 for e in events if e["status"] == "maintenance")
        nb_ferme = sum(1 for e in events if e["status"] == "fermé")

        c = Container()
        c.add_item(TextDisplay("## 🎮 Config Alpha — Système Events"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**📡 Salon annonces :** {_ch(self.cfg.get('channel_id'))}\n"
            f"**🔔 Rôle ping :** {_role(self.cfg.get('ping_role_id'))}\n\n"
            f"**Events :** ✅ `{nb_ok}` · 🔧 `{nb_maint}` · 🔴 `{nb_ferme}`  *(total : {len(events)})*"
        ))
        c.add_item(Separator())

        btn_ch  = Button(label="📡 Salon",       style=ButtonStyle.primary,   custom_id="ev_ch")
        btn_rl  = Button(label="🔔 Rôle Ping",   style=ButtonStyle.primary,   custom_id="ev_rl")
        btn_st  = Button(label="🎮 Statuts",      style=ButtonStyle.primary,   custom_id="ev_st")
        btn_bck = Button(label="↩️ Tableau de bord", style=ButtonStyle.secondary, custom_id="ev_bck")

        btn_ch.callback  = lambda i: i.response.edit_message(view=_ChannelView(self.guild_id, self.cfg, self.owner_id))
        btn_rl.callback  = lambda i: i.response.edit_message(view=_RoleView(self.guild_id, self.cfg, self.owner_id))
        btn_st.callback  = lambda i: i.response.edit_message(view=_StatusView(self.guild_id, self.owner_id))
        btn_bck.callback = self._on_back

        c.add_item(ActionRow(btn_ch, btn_rl, btn_st))
        c.add_item(ActionRow(btn_bck))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_back(self, i: Interaction) -> None:
        from views.alpha.config_dashboard_view import ConfigDashboardView
        await i.response.edit_message(view=ConfigDashboardView(self.guild_id, self.owner_id))


# ════════════════════════════════════════════════════════════
# 📡 Salon
# ════════════════════════════════════════════════════════════

class _ChannelView(LayoutView):
    def __init__(self, guild_id, cfg, owner_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id; self.cfg = cfg; self.owner_id = owner_id
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self):
        c = Container()
        c.add_item(TextDisplay(f"## 📡 Salon d'annonces\n**Actuel :** {_ch(self.cfg.get('channel_id'))}"))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# start_event et event_regle enverront dans ce salon."))
        c.add_item(ActionRow(ChannelSelect(
            placeholder="Choisir le salon",
            on_select=self._save,
            channel_types=[discord.ChannelType.text],
        )))
        c.add_item(Separator())
        btn = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="ev_bck_ch")
        btn.callback = _back_main(self.guild_id, self.owner_id)
        c.add_item(ActionRow(btn))
        self.add_item(c)

    async def _save(self, i, ch):
        self.cfg = await save_event_config(self.guild_id, channel_id=ch)
        await i.response.edit_message(view=_ChannelView(self.guild_id, self.cfg, self.owner_id))


# ════════════════════════════════════════════════════════════
# 🔔 Rôle ping
# ════════════════════════════════════════════════════════════

class _RoleView(LayoutView):
    def __init__(self, guild_id, cfg, owner_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id; self.cfg = cfg; self.owner_id = owner_id
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self):
        c = Container()
        c.add_item(TextDisplay(f"## 🔔 Rôle Ping\n**Actuel :** {_role(self.cfg.get('ping_role_id'))}"))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# Ce rôle sera @mentionné dans chaque annonce start_event."))
        c.add_item(ActionRow(RoleSelect(
            placeholder="Choisir le rôle à pinger",
            on_select=lambda i, ids: self._save(i, ids[0]),
        )))
        c.add_item(Separator())
        btn = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="ev_bck_rl")
        btn.callback = _back_main(self.guild_id, self.owner_id)
        c.add_item(ActionRow(btn))
        self.add_item(c)

    async def _save(self, i, role_id):
        self.cfg = await save_event_config(self.guild_id, ping_role_id=role_id)
        await i.response.edit_message(view=_RoleView(self.guild_id, self.cfg, self.owner_id))


# ════════════════════════════════════════════════════════════
# 🎮 Gestion des statuts
# ════════════════════════════════════════════════════════════

class _StatusView(LayoutView):
    """Sélectionner un event pour changer son statut."""

    def __init__(self, guild_id: int, owner_id: int, selected_id: int | None = None) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.selected_id = selected_id
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self) -> None:
        events = load_events()
        c = Container()
        c.add_item(TextDisplay("## 🎮 Gestion des statuts"))
        c.add_item(Separator())

        # Résumé par statut
        lines = []
        for e in events:
            emoji = STATUS_EMOJIS.get(e["status"], "?")
            lines.append(f"{emoji} **{e['name']}**")
        # Afficher en 2 colonnes dans un seul TextDisplay
        half = (len(lines) + 1) // 2
        col1, col2 = lines[:half], lines[half:]
        combined = "\n".join(
            f"{c1}{'  ·  ' + c2 if i < len(col2) else ''}"
            for i, (c1, c2) in enumerate(zip(col1, col2 + [''] * len(col1)))
            if c1
        )
        c.add_item(TextDisplay(combined))
        c.add_item(Separator())

        # Select
        sel = discord.ui.Select(
            placeholder="Sélectionner un event pour changer son statut…",
            options=[
                discord.SelectOption(
                    label=e["name"],
                    value=str(e["id"]),
                    emoji=STATUS_EMOJIS.get(e["status"], "?"),
                    description=STATUS_LABELS.get(e["status"], e["status"]),
                )
                for e in events
            ],
            custom_id="ev_status_sel",
        )
        sel.callback = self._on_select
        c.add_item(ActionRow(sel))
        c.add_item(Separator())

        btn_back = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="ev_bck_st")
        btn_back.callback = _back_main(self.guild_id, self.owner_id)
        c.add_item(ActionRow(btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_select(self, i: Interaction) -> None:
        event_id = int(i.data["values"][0])
        event = get_event(event_id)
        if event is None:
            return await i.response.send_message("Event introuvable.", ephemeral=True)
        await i.response.edit_message(
            view=_StatusEditView(self.guild_id, self.owner_id, event)
        )


class _StatusEditView(LayoutView):
    """Boutons pour changer le statut d'un event spécifique."""

    def __init__(self, guild_id: int, owner_id: int, event: dict) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.event = event
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self) -> None:
        e = self.event
        cur_status = e["status"]
        cur_emoji = STATUS_EMOJIS.get(cur_status, "?")
        cur_label = STATUS_LABELS.get(cur_status, cur_status)

        c = Container()
        c.add_item(TextDisplay(
            f"## 🎮 {e['name']}\n"
            f"**Statut actuel :** {cur_emoji} {cur_label}"
        ))
        c.add_item(Separator())
        c.add_item(TextDisplay("Choisissez le nouveau statut :"))

        STATUS_BUTTONS = [
            ("fonctionne",  "✅ Opérationnel", ButtonStyle.success),
            ("maintenance", "🔧 Maintenance",  ButtonStyle.secondary),
            ("fermé",       "🔴 Fermé",        ButtonStyle.danger),
        ]
        buttons = []
        for val, label, style in STATUS_BUTTONS:
            btn = Button(
                label=label, style=style,
                custom_id=f"ev_st_{val}",
                disabled=(val == cur_status),
            )
            btn.callback = self._make_set_status(val)
            buttons.append(btn)

        btn_back = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="ev_bck_se")
        btn_back.callback = lambda i: i.response.edit_message(
            view=_StatusView(self.guild_id, self.owner_id)
        )
        buttons.append(btn_back)

        c.add_item(ActionRow(*buttons))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    def _make_set_status(self, new_status: str):
        async def _fn(i: Interaction) -> None:
            await update_event_status(self.event["id"], new_status)
            updated_event = get_event(self.event["id"])
            await i.response.edit_message(
                view=_StatusEditView(self.guild_id, self.owner_id, updated_event or self.event)
            )
        return _fn