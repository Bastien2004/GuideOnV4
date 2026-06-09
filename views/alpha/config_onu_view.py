"""
views/alpha/config_onu_view.py — Dashboard de configuration du système ONU Alpha.

Sections :
  Salon & Rôle → ChannelSelect + RoleSelect
  Horaires     → Select jour + modals pré-annonce/annonce
  Ping MP      → Toggle + UserSelect add/remove
  Paramètres   → Modals image, URL rejoindre + toggle enabled
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.managers.alpha_onu_manager import (
    load_onu_config, save_onu_config,
    get_onu_ping_members, add_onu_ping_member, remove_onu_ping_member,
)
from utils.db.models.alpha_onu_config import JOURS_LABELS
from views._components.channel_select import ChannelSelect
from views._components.role_select import RoleSelect
from views._components.user_select import UserSelect
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────

def _ch(v): return f"<#{v}>" if v else "*Non configuré*"
def _role(v): return f"<@&{v}>" if v else "*Non configuré*"
def _hm(h, m): return f"`{h:02d}:{m:02d}`" if h is not None and m is not None else "*Non configuré*"
def _jour(j): return JOURS_LABELS[j] if j is not None else "*Non configuré*"
def _bool(v): return "✅ Activé" if v else "❌ Désactivé"


# ════════════════════════════════════════════════════════════
# 🏠 Vue principale
# ════════════════════════════════════════════════════════════

class ONUConfigView(LayoutView):
    def __init__(self, guild_id: int, cfg: dict, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.cfg = cfg
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, i: Interaction) -> bool:
        if i.user.id != self.owner_id:
            await i.response.send_message("Seul l'auteur peut utiliser ce menu.", ephemeral=True)
            return False
        return True

    def _build(self) -> None:
        cfg = self.cfg
        c = Container()
        c.add_item(TextDisplay("## 🌐 Config Alpha — Système ONU"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**📡 Salon :** {_ch(cfg.get('channel_id'))}\n"
            f"**🔔 Rôle ping :** {_role(cfg.get('role_id'))}\n\n"
            f"**📅 Jour :** {_jour(cfg.get('jour_onu'))}\n"
            f"**⏰ Pré-annonce :** {_hm(cfg.get('pre_heure'), cfg.get('pre_minute'))} "
            f"| **Annonce :** {_hm(cfg.get('ann_heure'), cfg.get('ann_minute'))}\n"
            f"**🌍 Fuseau :** `{cfg.get('timezone', 'Europe/Paris')}`\n\n"
            f"**👥 Ping MP :** {_bool(cfg.get('ping_mp'))}\n"
            f"**🖼️ Image :** `{cfg.get('image_name') or 'Non configurée'}`\n"
            f"**🔗 URL rejoindre :** {'*Configurée*' if cfg.get('join_url') else '*Non configurée*'}\n\n"
            f"**Système :** {_bool(cfg.get('enabled', True))}"
        ))
        c.add_item(Separator())

        btn_salon = Button(label="📡 Salon & Rôle", style=ButtonStyle.primary, custom_id="onu_salon")
        btn_hor   = Button(label="⏰ Horaires",     style=ButtonStyle.primary, custom_id="onu_hor")
        btn_ping  = Button(label="👥 Ping MP",      style=ButtonStyle.primary, custom_id="onu_ping")
        btn_param = Button(label="🎛️ Paramètres",   style=ButtonStyle.secondary, custom_id="onu_param")
        btn_back  = Button(label="↩️ Tableau de bord", style=ButtonStyle.secondary, custom_id="onu_back")

        btn_salon.callback = self._on_salon
        btn_hor.callback   = self._on_horaires
        btn_ping.callback  = self._on_ping
        btn_param.callback = self._on_param
        btn_back.callback  = self._on_back

        c.add_item(ActionRow(btn_salon, btn_hor, btn_ping))
        c.add_item(ActionRow(btn_param, btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _reload(self, i: Interaction) -> None:
        cfg = await load_onu_config(self.guild_id)
        await i.response.edit_message(view=ONUConfigView(self.guild_id, cfg, self.owner_id))

    async def _on_salon(self, i: Interaction) -> None:
        cfg = await load_onu_config(self.guild_id)
        await i.response.edit_message(view=_SalonRoleView(self.guild_id, cfg, self.owner_id))

    async def _on_horaires(self, i: Interaction) -> None:
        cfg = await load_onu_config(self.guild_id)
        await i.response.edit_message(view=_HorairesView(self.guild_id, cfg, self.owner_id))

    async def _on_ping(self, i: Interaction) -> None:
        cfg = await load_onu_config(self.guild_id)
        members = await get_onu_ping_members(self.guild_id)
        await i.response.edit_message(view=_PingMPView(self.guild_id, cfg, self.owner_id, members))

    async def _on_param(self, i: Interaction) -> None:
        cfg = await load_onu_config(self.guild_id)
        await i.response.edit_message(view=_ParamsView(self.guild_id, cfg, self.owner_id))

    async def _on_back(self, i: Interaction) -> None:
        from views.alpha.config_dashboard_view import ConfigDashboardView
        await i.response.edit_message(view=ConfigDashboardView(self.guild_id, self.owner_id))


# ════════════════════════════════════════════════════════════
# 📡 Salon & Rôle
# ════════════════════════════════════════════════════════════

class _SalonRoleView(LayoutView):
    def __init__(self, guild_id: int, cfg: dict, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.cfg = cfg
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("## 📡 Salon & Rôle"))
        c.add_item(Separator())
        c.add_item(TextDisplay(f"**Salon annonces :** {_ch(self.cfg.get('channel_id'))}"))
        c.add_item(ActionRow(ChannelSelect(
            placeholder="Salon ONU",
            on_select=lambda i, ch: self._save(i, "channel_id", ch),
            channel_types=[discord.ChannelType.text],
        )))
        c.add_item(TextDisplay(f"**Rôle @mention :** {_role(self.cfg.get('role_id'))}"))
        c.add_item(ActionRow(RoleSelect(
            placeholder="Rôle à pinger",
            on_select=lambda i, ids: self._save(i, "role_id", ids[0]),
        )))
        c.add_item(Separator())
        btn = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="onu_back_sr")
        btn.callback = self._on_back
        c.add_item(ActionRow(btn))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _save(self, i: Interaction, field: str, value) -> None:
        self.cfg = await save_onu_config(self.guild_id, **{field: value})
        await i.response.edit_message(view=_SalonRoleView(self.guild_id, self.cfg, self.owner_id))

    async def _on_back(self, i: Interaction) -> None:
        cfg = await load_onu_config(self.guild_id)
        await i.response.edit_message(view=ONUConfigView(self.guild_id, cfg, self.owner_id))


# ════════════════════════════════════════════════════════════
# ⏰ Horaires
# ════════════════════════════════════════════════════════════

_JOUR_OPTIONS = [
    discord.SelectOption(label=label, value=str(i))
    for i, label in enumerate(JOURS_LABELS)
]


class _HorairesView(LayoutView):
    def __init__(self, guild_id: int, cfg: dict, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.cfg = cfg
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("## ⏰ Horaires"))
        c.add_item(Separator())
        c.add_item(TextDisplay(f"**Jour :** {_jour(self.cfg.get('jour_onu'))}"))

        day_select = discord.ui.Select(
            placeholder="Choisir le jour de l'ONU",
            options=_JOUR_OPTIONS,
            min_values=1, max_values=1,
            custom_id="onu_day_sel",
        )
        day_select.callback = self._on_day
        c.add_item(ActionRow(day_select))
        c.add_item(Separator())

        c.add_item(TextDisplay(
            f"**Pré-annonce :** {_hm(self.cfg.get('pre_heure'), self.cfg.get('pre_minute'))}\n"
            f"**Annonce :** {_hm(self.cfg.get('ann_heure'), self.cfg.get('ann_minute'))}"
        ))

        btn_pre = Button(label="⏰ Heure pré-annonce", style=ButtonStyle.primary, custom_id="onu_pre")
        btn_ann = Button(label="🕐 Heure annonce",     style=ButtonStyle.primary, custom_id="onu_ann")
        btn_bck = Button(label="↩️ Retour",            style=ButtonStyle.secondary, custom_id="onu_back_h")
        btn_pre.callback = self._on_pre
        btn_ann.callback = self._on_ann
        btn_bck.callback = self._on_back
        c.add_item(ActionRow(btn_pre, btn_ann, btn_bck))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_day(self, i: Interaction) -> None:
        val = int(i.data["values"][0])
        self.cfg = await save_onu_config(self.guild_id, jour_onu=val)
        await i.response.edit_message(view=_HorairesView(self.guild_id, self.cfg, self.owner_id))

    def _make_time_modal(self, title: str, h_field: str, m_field: str, current_h, current_m):
        default = f"{current_h:02d}:{current_m:02d}" if current_h is not None and current_m is not None else ""

        async def on_submit(i: Interaction, value: str) -> None:
            value = value.strip()
            try:
                parts = value.split(":")
                h, m = int(parts[0]), int(parts[1])
                assert 0 <= h <= 23 and 0 <= m <= 59
            except Exception:
                await i.response.send_message(
                    "Format invalide. Utilisez **HH:MM** (ex: `17:00`).", ephemeral=True
                )
                return
            self.cfg = await save_onu_config(self.guild_id, **{h_field: h, m_field: m})
            await i.response.edit_message(view=_HorairesView(self.guild_id, self.cfg, self.owner_id))

        return TextModal(
            title=title,
            label="Heure (format HH:MM)",
            placeholder="Ex: 16:30",
            default=default,
            min_length=4, max_length=5,
            on_submit=on_submit,
        )

    async def _on_pre(self, i: Interaction) -> None:
        modal = self._make_time_modal(
            "Pré-annonce", "pre_heure", "pre_minute",
            self.cfg.get("pre_heure"), self.cfg.get("pre_minute"),
        )
        await i.response.send_modal(modal)

    async def _on_ann(self, i: Interaction) -> None:
        modal = self._make_time_modal(
            "Annonce", "ann_heure", "ann_minute",
            self.cfg.get("ann_heure"), self.cfg.get("ann_minute"),
        )
        await i.response.send_modal(modal)

    async def _on_back(self, i: Interaction) -> None:
        cfg = await load_onu_config(self.guild_id)
        await i.response.edit_message(view=ONUConfigView(self.guild_id, cfg, self.owner_id))


# ════════════════════════════════════════════════════════════
# 👥 Ping MP
# ════════════════════════════════════════════════════════════

class _PingMPView(LayoutView):
    def __init__(self, guild_id: int, cfg: dict, owner_id: int, ping_ids: list[int]) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.cfg = cfg
        self.owner_id = owner_id
        self.ping_ids = ping_ids
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("## 👥 Ping MP"))
        c.add_item(Separator())

        count = len(self.ping_ids)
        pings_str = " ".join(f"<@{uid}>" for uid in self.ping_ids) or "*Aucun*"
        c.add_item(TextDisplay(
            f"**Ping MP :** {_bool(self.cfg.get('ping_mp'))}\n"
            f"**Membres ({count}) :** {pings_str}"
        ))
        c.add_item(Separator())

        btn_toggle = Button(
            label="✅ Désactiver" if self.cfg.get("ping_mp") else "❌ Activer",
            style=ButtonStyle.danger if self.cfg.get("ping_mp") else ButtonStyle.success,
            custom_id="onu_toggle_mp",
        )
        btn_toggle.callback = self._on_toggle
        c.add_item(ActionRow(btn_toggle))

        c.add_item(TextDisplay("**Ajouter un membre à la ping-list :**"))
        add_select = UserSelect(
            placeholder="Ajouter un membre…",
            on_select=self._on_add,
        )
        c.add_item(ActionRow(add_select))

        c.add_item(TextDisplay("**Retirer un membre de la ping-list :**"))
        rem_select = UserSelect(
            placeholder="Retirer un membre…",
            on_select=self._on_remove,
        )
        c.add_item(ActionRow(rem_select))

        c.add_item(Separator())
        btn_back = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="onu_back_mp")
        btn_back.callback = self._on_back
        c.add_item(ActionRow(btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_toggle(self, i: Interaction) -> None:
        new_val = not self.cfg.get("ping_mp", False)
        self.cfg = await save_onu_config(self.guild_id, ping_mp=new_val)
        members = await get_onu_ping_members(self.guild_id)
        await i.response.edit_message(view=_PingMPView(self.guild_id, self.cfg, self.owner_id, members))

    async def _on_add(self, i: Interaction, user_ids: list[int]) -> None:
        uid = user_ids[0]
        added = await add_onu_ping_member(self.guild_id, uid)
        members = await get_onu_ping_members(self.guild_id)
        if not added:
            await i.response.send_message(f"<@{uid}> est déjà dans la ping-list.", ephemeral=True)
        else:
            await i.response.edit_message(
                view=_PingMPView(self.guild_id, self.cfg, self.owner_id, members)
            )

    async def _on_remove(self, i: Interaction, user_ids: list[int]) -> None:
        uid = user_ids[0]
        removed = await remove_onu_ping_member(self.guild_id, uid)
        members = await get_onu_ping_members(self.guild_id)
        if not removed:
            await i.response.send_message(f"<@{uid}> n'est pas dans la ping-list.", ephemeral=True)
        else:
            await i.response.edit_message(
                view=_PingMPView(self.guild_id, self.cfg, self.owner_id, members)
            )

    async def _on_back(self, i: Interaction) -> None:
        cfg = await load_onu_config(self.guild_id)
        await i.response.edit_message(view=ONUConfigView(self.guild_id, cfg, self.owner_id))


# ════════════════════════════════════════════════════════════
# 🎛️ Paramètres (image, URL, enabled)
# ════════════════════════════════════════════════════════════

class _ParamsView(LayoutView):
    def __init__(self, guild_id: int, cfg: dict, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.cfg = cfg
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("## 🎛️ Paramètres"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**🖼️ Image :** `{self.cfg.get('image_name') or 'Non configurée'}`\n"
            f"-# Fichier dans source/ (ex: onu_alpha_1.png)\n\n"
            f"**🔗 URL rejoindre :** {'*Configurée*' if self.cfg.get('join_url') else '*Non configurée*'}\n\n"
            f"**Système :** {_bool(self.cfg.get('enabled', True))}"
        ))
        c.add_item(Separator())

        btn_img    = Button(label="🖼️ Image",       style=ButtonStyle.secondary, custom_id="onu_img")
        btn_url    = Button(label="🔗 URL rejoindre", style=ButtonStyle.secondary, custom_id="onu_url")
        btn_toggle = Button(
            label="✅ Désactiver" if self.cfg.get("enabled", True) else "❌ Activer",
            style=ButtonStyle.danger if self.cfg.get("enabled", True) else ButtonStyle.success,
            custom_id="onu_toggle_en",
        )
        btn_back   = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="onu_back_p")

        btn_img.callback    = self._on_image
        btn_url.callback    = self._on_url
        btn_toggle.callback = self._on_toggle
        btn_back.callback   = self._on_back

        c.add_item(ActionRow(btn_img, btn_url, btn_toggle, btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_image(self, i: Interaction) -> None:
        async def on_submit(inter: Interaction, value: str) -> None:
            self.cfg = await save_onu_config(self.guild_id, image_name=value.strip() or None)
            await inter.response.edit_message(view=_ParamsView(self.guild_id, self.cfg, self.owner_id))
        modal = TextModal(
            title="Image ONU",
            label="Nom du fichier (dans source/)",
            placeholder="Ex: onu_alpha_1.png",
            default=self.cfg.get("image_name") or "",
            min_length=0, max_length=100,
            on_submit=on_submit,
        )
        await i.response.send_modal(modal)

    async def _on_url(self, i: Interaction) -> None:
        async def on_submit(inter: Interaction, value: str) -> None:
            self.cfg = await save_onu_config(self.guild_id, join_url=value.strip() or None)
            await inter.response.edit_message(view=_ParamsView(self.guild_id, self.cfg, self.owner_id))
        modal = TextModal(
            title="URL rejoindre la conférence",
            label="URL Discord du salon vocal",
            placeholder="https://discord.com/channels/.../...",
            default=self.cfg.get("join_url") or "",
            min_length=0, max_length=300,
            on_submit=on_submit,
        )
        await i.response.send_modal(modal)

    async def _on_toggle(self, i: Interaction) -> None:
        new_val = not self.cfg.get("enabled", True)
        self.cfg = await save_onu_config(self.guild_id, enabled=new_val)
        await i.response.edit_message(view=_ParamsView(self.guild_id, self.cfg, self.owner_id))

    async def _on_back(self, i: Interaction) -> None:
        cfg = await load_onu_config(self.guild_id)
        await i.response.edit_message(view=ONUConfigView(self.guild_id, cfg, self.owner_id))