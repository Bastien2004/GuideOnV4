"""
views/ngstaff/config_nota_view.py — Dashboard de configuration du système de
notations, multi-serveurs (ex-views/alpha/config_nota_view.py).

Sections :
  Salons     → staff, public, logs (ChannelSelects)
  Rôle & Config → rôle ping, pays, URL lookup
  Horaires   → présence, deadline, public (modals HH:MM par jour + heure)
  Paramètres → enabled toggle
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.managers.ng_nota_manager import load_nota_config, save_nota_config
from views._components.channel_select import ChannelSelect
from views._components.role_select import RoleSelect
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

# Refonte multi-serveurs phase 11 : ce fichier servait à l'origine à la fois
# /alpha config_alpha (dashboard="alpha", toujours server="alpha") et
# /ngstaff config (dashboard="ngstaff", server résolu dynamiquement). La
# commande /alpha config_alpha a depuis été supprimée — /ngstaff config est
# le seul appelant restant, `dashboard` vaut donc toujours "ngstaff" en
# pratique (branche "alpha" désormais morte mais inoffensive, nomenclature
# nettoyée, Paul, 2026-08-22).

# Noms des jours
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

# ── Helpers ──────────────────────────────────────────────────

def _ch(v): return f"<#{v}>" if v else "*Non configuré*"
def _role(v): return f"<@&{v}>" if v else "*Non configuré*"
def _hm(wd, h, m):
    if wd is None or h is None or m is None:
        return "*Non configuré*"
    return f"**{JOURS[wd]}** à `{h:02d}:{m:02d}`"
def _bool(v): return "✅ Activé" if v else "❌ Désactivé"


# ════════════════════════════════════════════════════════════
# 🏠 Vue principale
# ════════════════════════════════════════════════════════════

class NotaConfigView(LayoutView):
    def __init__(
        self, guild_id: int, server: str, cfg: dict, owner_id: int, *, dashboard: str = "alpha"
    ) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.server = server
        self.cfg = cfg
        self.owner_id = owner_id
        self.dashboard = dashboard
        self._build()

    async def interaction_check(self, i: Interaction) -> bool:
        if i.user.id != self.owner_id:
            await i.response.send_message("Seul l'auteur peut utiliser ce menu.", ephemeral=True)
            return False
        return True

    def _build(self) -> None:
        cfg = self.cfg
        c = Container()
        c.add_item(TextDisplay("## 📋 Config Alpha — Système Notations"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**📡 Salon staff :** {_ch(cfg.get('channel_staff_id'))}\n"
            f"**🌐 Salon public :** {_ch(cfg.get('channel_public_id'))}\n"
            f"**🗒️ Salon logs :** {_ch(cfg.get('channel_logs_id'))}\n"
            f"**🔔 Rôle ping :** {_role(cfg.get('role_id'))}\n"
            f"**🌍 Pays :** `{cfg.get('countries_count', 238)}`\n\n"
            f"**⏰ Présence & Rappels :** {_hm(cfg.get('send_presence_weekday'), cfg.get('send_presence_hour'), cfg.get('send_presence_minute'))}\n"
            f"**⛔ Deadline :** {_hm(cfg.get('deadline_weekday'), cfg.get('deadline_hour'), cfg.get('deadline_minute'))}\n"
            f"**📤 Envoi public :** {_hm(cfg.get('send_public_weekday'), cfg.get('send_public_hour'), cfg.get('send_public_minute'))}\n\n"
            f"**Système :** {_bool(cfg.get('enabled', True))}"
        ))
        c.add_item(Separator())

        btn_salons = Button(label="📡 Salons",    style=ButtonStyle.primary,   custom_id="nota_salons")
        btn_cfg    = Button(label="⚙️ Rôle & Config", style=ButtonStyle.primary, custom_id="nota_cfg")
        btn_hor    = Button(label="⏰ Horaires",   style=ButtonStyle.primary,   custom_id="nota_hor")
        btn_param  = Button(label="🎛️ Paramètres", style=ButtonStyle.secondary, custom_id="nota_param")
        btn_back   = Button(label="↩️ Tableau de bord", style=ButtonStyle.secondary, custom_id="nota_back")

        btn_salons.callback = self._on_salons
        btn_cfg.callback    = self._on_config
        btn_hor.callback    = self._on_horaires
        btn_param.callback  = self._on_params
        btn_back.callback   = self._on_back

        c.add_item(ActionRow(btn_salons, btn_cfg, btn_hor))
        c.add_item(ActionRow(btn_param, btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _reload(self, i: Interaction) -> None:
        cfg = await load_nota_config(self.server)
        await i.response.edit_message(view=NotaConfigView(self.guild_id, self.server, cfg, self.owner_id, dashboard=self.dashboard))

    async def _on_salons(self, i: Interaction) -> None:
        cfg = await load_nota_config(self.server)
        await i.response.edit_message(view=_SalonsView(self.guild_id, self.server, cfg, self.owner_id, dashboard=self.dashboard))

    async def _on_config(self, i: Interaction) -> None:
        cfg = await load_nota_config(self.server)
        await i.response.edit_message(view=_RoleCfgView(self.guild_id, self.server, cfg, self.owner_id, dashboard=self.dashboard))

    async def _on_horaires(self, i: Interaction) -> None:
        cfg = await load_nota_config(self.server)
        await i.response.edit_message(view=_HorairesView(self.guild_id, self.server, cfg, self.owner_id, dashboard=self.dashboard))

    async def _on_params(self, i: Interaction) -> None:
        cfg = await load_nota_config(self.server)
        await i.response.edit_message(view=_ParamsView(self.guild_id, self.server, cfg, self.owner_id, dashboard=self.dashboard))

    async def _on_back(self, i: Interaction) -> None:
        if self.dashboard == "ngstaff":
            from views.ngstaff.config_dashboard_view import NGStaffConfigDashboardView
            await i.response.edit_message(
                view=NGStaffConfigDashboardView(self.guild_id, self.server, self.owner_id)
            )
        else:
            from views.alpha.config_dashboard_view import ConfigDashboardView
            await i.response.edit_message(view=ConfigDashboardView(self.guild_id, self.owner_id))


def _back_to_main(guild_id, server, owner_id, *, dashboard: str = "alpha"):
    async def _fn(i: Interaction):
        cfg = await load_nota_config(server)
        await i.response.edit_message(
            view=NotaConfigView(guild_id, server, cfg, owner_id, dashboard=dashboard)
        )
    return _fn


# ════════════════════════════════════════════════════════════
# 📡 Salons
# ════════════════════════════════════════════════════════════

class _SalonsView(LayoutView):
    def __init__(
        self, guild_id: int, server: str, cfg: dict, owner_id: int, *, dashboard: str = "alpha"
    ) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.server = server
        self.cfg = cfg
        self.owner_id = owner_id
        self.dashboard = dashboard
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("## 📡 Salons"))
        c.add_item(Separator())

        for label, field, current in [
            ("Salon staff (message de présence)", "channel_staff_id",  self.cfg.get("channel_staff_id")),
            ("Salon public (notation)",           "channel_public_id", self.cfg.get("channel_public_id")),
            ("Salon logs",                        "channel_logs_id",   self.cfg.get("channel_logs_id")),
        ]:
            c.add_item(TextDisplay(f"**{label} :** {_ch(current)}"))
            c.add_item(ActionRow(ChannelSelect(
                placeholder=f"Choisir : {label}",
                on_select=self._make_save(field),
                channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            )))

        c.add_item(Separator())
        btn = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="nota_back_s")
        btn.callback = _back_to_main(self.guild_id, self.server, self.owner_id, dashboard=self.dashboard)
        c.add_item(ActionRow(btn))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    def _make_save(self, field: str):
        async def _fn(i: Interaction, ch: int) -> None:
            self.cfg = await save_nota_config(self.server, **{field: ch})
            await i.response.edit_message(view=_SalonsView(self.guild_id, self.server, self.cfg, self.owner_id, dashboard=self.dashboard))
        return _fn


# ════════════════════════════════════════════════════════════
# ⚙️ Rôle & Config
# ════════════════════════════════════════════════════════════

class _RoleCfgView(LayoutView):
    def __init__(
        self, guild_id: int, server: str, cfg: dict, owner_id: int, *, dashboard: str = "alpha"
    ) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.server = server
        self.cfg = cfg
        self.owner_id = owner_id
        self.dashboard = dashboard
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("## ⚙️ Rôle & Configuration"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**Rôle @mention :** {_role(self.cfg.get('role_id'))}\n"
            f"**Nombre de pays :** `{self.cfg.get('countries_count', 238)}`\n"
            f"**URL lookup pays :** {'*Configurée*' if self.cfg.get('url_country_lookup') else '*Non configurée*'}"
        ))
        c.add_item(ActionRow(RoleSelect(
            placeholder="Rôle @mention dans les messages",
            on_select=lambda i, ids: self._save(i, "role_id", ids[0]),
        )))

        btn_pays = Button(label="🌍 Nombre de pays", style=ButtonStyle.secondary, custom_id="nota_pays")
        btn_url  = Button(label="🔗 URL lookup",     style=ButtonStyle.secondary, custom_id="nota_url")
        btn_back = Button(label="↩️ Retour",          style=ButtonStyle.secondary, custom_id="nota_back_rc")
        btn_pays.callback = self._on_pays
        btn_url.callback  = self._on_url
        btn_back.callback = _back_to_main(self.guild_id, self.server, self.owner_id, dashboard=self.dashboard)
        c.add_item(ActionRow(btn_pays, btn_url, btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _save(self, i: Interaction, field: str, value) -> None:
        self.cfg = await save_nota_config(self.server, **{field: value})
        await i.response.edit_message(view=_RoleCfgView(self.guild_id, self.server, self.cfg, self.owner_id, dashboard=self.dashboard))

    async def _on_pays(self, i: Interaction) -> None:
        async def on_submit(inter: Interaction, val: str) -> None:
            try:
                n = int(val.strip())
                assert 1 <= n <= 10000
            except Exception:
                return await inter.response.send_message("Nombre invalide (1–10000).", ephemeral=True)
            self.cfg = await save_nota_config(self.server, countries_count=n)
            await inter.response.edit_message(view=_RoleCfgView(self.guild_id, self.server, self.cfg, self.owner_id, dashboard=self.dashboard))
        modal = TextModal(
            title="Nombre de pays",
            label="Nombre total de pays à répartir",
            placeholder="238",
            default=str(self.cfg.get("countries_count", 238)),
            min_length=1, max_length=5,
            on_submit=on_submit,
        )
        await i.response.send_modal(modal)

    async def _on_url(self, i: Interaction) -> None:
        async def on_submit(inter: Interaction, val: str) -> None:
            self.cfg = await save_nota_config(self.server, url_country_lookup=val.strip() or None)
            await inter.response.edit_message(view=_RoleCfgView(self.guild_id, self.server, self.cfg, self.owner_id, dashboard=self.dashboard))
        modal = TextModal(
            title="URL lookup pays",
            label="URL du bouton 'Numéro de mon pays'",
            placeholder="https://guideonbot.guideon.dev/",
            default=self.cfg.get("url_country_lookup") or "",
            min_length=0, max_length=300,
            on_submit=on_submit,
        )
        await i.response.send_modal(modal)


# ════════════════════════════════════════════════════════════
# ⏰ Horaires
# ════════════════════════════════════════════════════════════

_JOUR_OPTIONS = [discord.SelectOption(label=j, value=str(i)) for i, j in enumerate(JOURS)]


class _HorairesView(LayoutView):
    def __init__(
        self, guild_id: int, server: str, cfg: dict, owner_id: int, *, dashboard: str = "alpha"
    ) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.server = server
        self.cfg = cfg
        self.owner_id = owner_id
        self.dashboard = dashboard
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("## ⏰ Horaires"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**Présence & Rappels :** {_hm(self.cfg.get('send_presence_weekday'), self.cfg.get('send_presence_hour'), self.cfg.get('send_presence_minute'))}\n"
            f"**Deadline vote :** {_hm(self.cfg.get('deadline_weekday'), self.cfg.get('deadline_hour'), self.cfg.get('deadline_minute'))}\n"
            f"**Envoi public :** {_hm(self.cfg.get('send_public_weekday'), self.cfg.get('send_public_hour'), self.cfg.get('send_public_minute'))}"
        ))
        c.add_item(Separator())

        btn_pre = Button(label="⏰ Présence",     style=ButtonStyle.primary,   custom_id="nota_btn_pre")
        btn_dl  = Button(label="⛔ Deadline",     style=ButtonStyle.primary,   custom_id="nota_btn_dl")
        btn_pub = Button(label="📤 Envoi public", style=ButtonStyle.primary,   custom_id="nota_btn_pub")
        btn_bck = Button(label="↩️ Retour",        style=ButtonStyle.secondary, custom_id="nota_back_h")

        btn_pre.callback = lambda i: self._open_time_modal(i, "presence")
        btn_dl.callback  = lambda i: self._open_time_modal(i, "deadline")
        btn_pub.callback = lambda i: self._open_time_modal(i, "public")
        btn_bck.callback = _back_to_main(self.guild_id, self.server, self.owner_id, dashboard=self.dashboard)

        c.add_item(ActionRow(btn_pre, btn_dl, btn_pub, btn_bck))
        c.add_item(TextDisplay("-# *Format modal : `Vendredi HH:MM` (ex: `Vendredi 08:00`)*"))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _open_time_modal(self, i: Interaction, which: str) -> None:
        titles = {"presence": "Présence & Rappels", "deadline": "Deadline vote", "public": "Envoi public"}
        fields = {
            "presence": ("send_presence_weekday", "send_presence_hour", "send_presence_minute"),
            "deadline": ("deadline_weekday", "deadline_hour", "deadline_minute"),
            "public":   ("send_public_weekday",  "send_public_hour",  "send_public_minute"),
        }
        wd_f, h_f, m_f = fields[which]
        wd = self.cfg.get(wd_f)
        h  = self.cfg.get(h_f)
        m  = self.cfg.get(m_f)
        current = f"{JOURS[wd]} {h:02d}:{m:02d}" if wd is not None and h is not None and m is not None else ""

        async def on_submit(inter: Interaction, val: str) -> None:
            val = val.strip()
            try:
                parts = val.rsplit(" ", 1)
                jour_str, hm_str = parts[0].strip().capitalize(), parts[1].strip()
                wd_val = next(idx for idx, j in enumerate(JOURS) if j.lower() == jour_str.lower())
                hh, mm = int(hm_str.split(":")[0]), int(hm_str.split(":")[1])
                assert 0 <= hh <= 23 and 0 <= mm <= 59
            except Exception:
                return await inter.response.send_message(
                    "Format invalide. Utilisez **Jour HH:MM** (ex: `Vendredi 08:00`).", ephemeral=True
                )
            self.cfg = await save_nota_config(self.server, **{wd_f: wd_val, h_f: hh, m_f: mm})
            await inter.response.edit_message(view=_HorairesView(self.guild_id, self.server, self.cfg, self.owner_id, dashboard=self.dashboard))

        modal = TextModal(
            title=titles[which],
            label="Jour et heure (ex: Vendredi 08:00)",
            placeholder="Vendredi 08:00",
            default=current,
            min_length=4, max_length=20,
            on_submit=on_submit,
        )
        await i.response.send_modal(modal)


# ════════════════════════════════════════════════════════════
# 🎛️ Paramètres
# ════════════════════════════════════════════════════════════

class _ParamsView(LayoutView):
    def __init__(
        self, guild_id: int, server: str, cfg: dict, owner_id: int, *, dashboard: str = "alpha"
    ) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.server = server
        self.cfg = cfg
        self.owner_id = owner_id
        self.dashboard = dashboard
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("## 🎛️ Paramètres"))
        c.add_item(Separator())
        c.add_item(TextDisplay(f"**Système :** {_bool(self.cfg.get('enabled', True))}"))
        c.add_item(Separator())

        btn_toggle = Button(
            label="✅ Désactiver" if self.cfg.get("enabled", True) else "❌ Activer",
            style=ButtonStyle.danger if self.cfg.get("enabled", True) else ButtonStyle.success,
            custom_id="nota_toggle_en",
        )
        btn_back = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="nota_back_p")
        btn_toggle.callback = self._on_toggle
        btn_back.callback   = _back_to_main(self.guild_id, self.server, self.owner_id, dashboard=self.dashboard)
        c.add_item(ActionRow(btn_toggle, btn_back))
        c.add_item(TextDisplay(
            "-# Les opérateurs sont automatiquement tirés de la liste staff (SM + Admin)."
        ))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_toggle(self, i: Interaction) -> None:
        self.cfg = await save_nota_config(self.server, enabled=not self.cfg.get("enabled", True))
        await i.response.edit_message(view=_ParamsView(self.guild_id, self.server, self.cfg, self.owner_id, dashboard=self.dashboard))
