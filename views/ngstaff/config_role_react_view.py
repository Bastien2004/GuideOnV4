"""
views/ngstaff/config_role_react_view.py — Dashboard configuration Rôle
Réaction, multi-serveurs (ex-views/alpha/config_role_react_view.py).

Sections :
  Vue principale → aperçu + [📡 Salon | 🎭 Rôles | 📤 Déployer | ↩️ Dashboard]
  _ChannelView   → ChannelSelect
  _RolesView     → liste + Select pour éditer + bouton Ajouter
  _EditRoleView  → édition label/emoji/description + suppression
  _AddFlow       → RoleSelect → Modal(label, emoji, desc)
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.managers.ng_role_react_manager import (
    MAX_ROLES, add_rr_entry, get_rr_entries, get_rr_entry_count,
    load_rr_config, remove_rr_entry, save_rr_config, update_rr_entry,
)
from views._components.channel_select import ChannelSelect
from views._components.role_select import RoleSelect
from views._components.text_modal import TextModal
from views.ngstaff.role_react_view import build_role_react_view, is_valid_emoji, parse_emoji
from utils.ng_server_display import get_server_display_name

log = logging.getLogger(__name__)

# Refonte multi-serveurs phase 11 : ce fichier servait à l'origine à la fois
# /alpha config_alpha (dashboard="alpha", toujours server="alpha") et
# /ngstaff config (dashboard="ngstaff", server résolu dynamiquement). La
# commande /alpha config_alpha a depuis été supprimée — /ngstaff config est
# le seul appelant restant, `dashboard` vaut donc toujours "ngstaff" en
# pratique (branche "alpha" désormais morte mais inoffensive, nomenclature
# nettoyée, Paul, 2026-08-22). guild_id / self.guild_id gardent leur rôle
# de navigation/identité de vue.


def _ch(v): return f"<#{v}>" if v else "*Non configuré*"


# ── helpers retour ────────────────────────────────────────────

def _back_main(guild_id: int, server: str, owner_id: int, *, dashboard: str = "alpha"):
    async def _fn(i: Interaction):
        cfg = await load_rr_config(server)
        entries = await get_rr_entries(server)
        await i.response.edit_message(
            view=RoleReactConfigView(guild_id, server, cfg, entries, owner_id, dashboard=dashboard)
        )
    return _fn

def _back_roles(guild_id: int, server: str, owner_id: int, *, dashboard: str = "alpha"):
    async def _fn(i: Interaction):
        entries = await get_rr_entries(server)
        await i.response.edit_message(
            view=_RolesView(guild_id, server, entries, owner_id, dashboard=dashboard)
        )
    return _fn


# ════════════════════════════════════════════════════════════
# 🏠 Vue principale
# ════════════════════════════════════════════════════════════

class RoleReactConfigView(LayoutView):
    def __init__(
        self,
        guild_id: int,
        server: str,
        cfg: dict,
        entries: list[dict],
        owner_id: int,
        *,
        dashboard: str = "alpha",
    ) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.server = server
        self.cfg = cfg
        self.entries = entries
        self.owner_id = owner_id
        self.dashboard = dashboard
        self._build()

    async def interaction_check(self, i: Interaction) -> bool:
        if i.user.id != self.owner_id:
            await i.response.send_message("Seul l'auteur peut utiliser ce menu.", ephemeral=True)
            return False
        return True

    def _build(self) -> None:
        n = len(self.entries)
        msg_status = (
            f"<#{self.cfg.get('channel_id')}> — message prêt ✅"
            if self.cfg.get("message_id") else
            f"<#{self.cfg.get('channel_id')}> — non déployé ⚠️"
            if self.cfg.get("channel_id") else
            "*Non configuré*"
        )

        c = Container()
        c.add_item(TextDisplay(f"## 🔔 Config {get_server_display_name(self.server)} — Rôle Réaction"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**📡 Salon :** {msg_status}\n"
            f"**🎭 Rôles configurés :** `{n}/{MAX_ROLES}`"
        ))
        if self.entries:
            lines = [
                f"`{i+1}.` {e.get('emoji', '•')} **{e['label']}**"
                for i, e in enumerate(self.entries)
            ]
            c.add_item(TextDisplay("\n".join(lines)))
        c.add_item(Separator())

        btn_ch   = Button(label="📡 Salon",   style=ButtonStyle.primary,   custom_id="rr_ch")
        btn_rl   = Button(label="🎭 Rôles",   style=ButtonStyle.primary,   custom_id="rr_rl")
        btn_dep  = Button(label="📤 Déployer", style=ButtonStyle.success,   custom_id="rr_dep")
        btn_back = Button(label="↩️ Tableau de bord", style=ButtonStyle.secondary, custom_id="rr_back")

        btn_ch.callback   = self._on_channel
        btn_rl.callback   = self._on_roles
        btn_dep.callback  = self._on_deploy
        btn_back.callback = self._on_back

        c.add_item(ActionRow(btn_ch, btn_rl, btn_dep))
        c.add_item(ActionRow(btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_channel(self, i: Interaction) -> None:
        await i.response.edit_message(
            view=_ChannelView(self.guild_id, self.server, self.cfg, self.owner_id, dashboard=self.dashboard)
        )

    async def _on_roles(self, i: Interaction) -> None:
        entries = await get_rr_entries(self.server)
        await i.response.edit_message(
            view=_RolesView(self.guild_id, self.server, entries, self.owner_id, dashboard=self.dashboard)
        )

    async def _on_deploy(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=True)
        cfg = await load_rr_config(self.server)
        channel_id = cfg.get("channel_id")
        if not channel_id:
            return await i.followup.send("Configurez d'abord le **salon** (📡 Salon).", ephemeral=True)

        channel = i.client.get_channel(channel_id)
        if channel is None:
            try:
                channel = await i.client.fetch_channel(channel_id)
            except (discord.NotFound, discord.HTTPException):
                return await i.followup.send("Salon introuvable.", ephemeral=True)

        entries = await get_rr_entries(self.server)
        view = build_role_react_view(entries)

        # Create or update
        existing = None
        if cfg.get("message_id"):
            try:
                existing = await channel.fetch_message(cfg["message_id"])
            except (discord.NotFound, discord.HTTPException):
                existing = None
                await save_rr_config(self.server, message_id=None)

        try:
            if existing:
                await existing.edit(view=view)
                action = "mis à jour"
            else:
                sent = await channel.send(view=view)
                await save_rr_config(self.server, message_id=sent.id)
                action = "déployé"
        except discord.HTTPException as e:
            log.exception("[ROLE_REACT] Erreur déploiement | guild=%d", self.guild_id)
            return await i.followup.send(f"Erreur Discord : {e}", ephemeral=True)

        # Recharger et refresher la vue config
        cfg = await load_rr_config(self.server)
        entries = await get_rr_entries(self.server)
        await i.edit_original_response(
            view=RoleReactConfigView(
                self.guild_id, self.server, cfg, entries, self.owner_id, dashboard=self.dashboard
            )
        )
        await i.followup.send(
            f"✅ Message {action} dans {channel.mention} !", ephemeral=True
        )

    async def _on_back(self, i: Interaction) -> None:
        if self.dashboard == "ngstaff":
            from views.ngstaff.config_dashboard_view import NGStaffConfigDashboardView
            await i.response.edit_message(
                view=NGStaffConfigDashboardView(self.guild_id, self.server, self.owner_id)
            )
        else:
            from views.alpha.config_dashboard_view import ConfigDashboardView
            await i.response.edit_message(view=ConfigDashboardView(self.guild_id, self.owner_id))


# ════════════════════════════════════════════════════════════
# 📡 Salon
# ════════════════════════════════════════════════════════════

class _ChannelView(LayoutView):
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
        c.add_item(TextDisplay("## 📡 Salon cible"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**Salon actuel :** {_ch(self.cfg.get('channel_id'))}\n"
            f"-# Le message de rôle réaction sera envoyé dans ce salon."
        ))
        c.add_item(ActionRow(ChannelSelect(
            placeholder="Choisir le salon",
            on_select=self._on_select,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
        )))
        c.add_item(Separator())
        btn = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="rr_back_ch")
        btn.callback = _back_main(self.guild_id, self.server, self.owner_id, dashboard=self.dashboard)
        c.add_item(ActionRow(btn))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_select(self, i: Interaction, channel_id: int) -> None:
        cfg = await save_rr_config(self.server, channel_id=channel_id, message_id=None)
        await i.response.edit_message(
            view=_ChannelView(self.guild_id, self.server, cfg, self.owner_id, dashboard=self.dashboard)
        )


# ════════════════════════════════════════════════════════════
# 🎭 Gestion des rôles
# ════════════════════════════════════════════════════════════

class _RolesView(LayoutView):
    def __init__(
        self, guild_id: int, server: str, entries: list[dict], owner_id: int, *, dashboard: str = "alpha"
    ) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.server = server
        self.entries = entries
        self.owner_id = owner_id
        self.dashboard = dashboard
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay(
            f"## 🎭 Gestion des rôles\n*{len(self.entries)}/{MAX_ROLES} rôles configurés*"
        ))
        c.add_item(Separator())

        if self.entries:
            lines = [
                f"`{i+1}.` {e.get('emoji', '•')} **{e['label']}** — <@&{e['role_id']}>"
                + (f"\n-# {e['description']}" if e.get("description") else "")
                for i, e in enumerate(self.entries)
            ]
            c.add_item(TextDisplay("\n".join(lines)))
            c.add_item(Separator())

            # Select pour éditer un rôle existant
            sel = discord.ui.Select(
                placeholder="Sélectionner un rôle à modifier…",
                options=[
                    discord.SelectOption(
                        label=e["label"],
                        value=str(e["id"]),
                        emoji=parse_emoji(e.get("emoji")),
                        description=f"Position {e['position']+1}",
                    )
                    for e in self.entries
                ],
                min_values=1, max_values=1,
                custom_id="rr_edit_select",
            )
            sel.callback = self._on_edit_select
            c.add_item(ActionRow(sel))
        else:
            c.add_item(TextDisplay("*Aucun rôle configuré. Ajoutez-en un ci-dessous.*"))

        c.add_item(Separator())
        btn_add  = Button(
            label="➕ Ajouter un rôle",
            style=ButtonStyle.success,
            custom_id="rr_add",
            disabled=len(self.entries) >= MAX_ROLES,
        )
        btn_back = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="rr_back_rl")
        btn_add.callback  = self._on_add
        btn_back.callback = _back_main(self.guild_id, self.server, self.owner_id, dashboard=self.dashboard)
        c.add_item(ActionRow(btn_add, btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_edit_select(self, i: Interaction) -> None:
        entry_id = int(i.data["values"][0])
        entry = next((e for e in self.entries if e["id"] == entry_id), None)
        if entry is None:
            return await i.response.send_message("Rôle introuvable.", ephemeral=True)
        await i.response.edit_message(
            view=_EditRoleView(self.guild_id, self.server, entry, self.owner_id, dashboard=self.dashboard)
        )

    async def _on_add(self, i: Interaction) -> None:
        await i.response.edit_message(
            view=_AddStep1View(self.guild_id, self.server, self.owner_id, dashboard=self.dashboard)
        )


# ════════════════════════════════════════════════════════════
# ✏️ Édition d'un rôle existant
# ════════════════════════════════════════════════════════════

class _EditRoleView(LayoutView):
    def __init__(
        self, guild_id: int, server: str, entry: dict, owner_id: int, *, dashboard: str = "alpha"
    ) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.server = server
        self.entry = entry
        self.owner_id = owner_id
        self.dashboard = dashboard
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self) -> None:
        e = self.entry
        c = Container()
        c.add_item(TextDisplay(f"## ✏️ Modifier — {e.get('emoji', '')} {e['label']}"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**Rôle Discord :** <@&{e['role_id']}>\n"
            f"**Label :** `{e['label']}`\n"
            f"**Emoji :** {e.get('emoji') or '*Aucun*'}\n"
            f"**Description :** {e.get('description') or '*Aucune*'}"
        ))
        c.add_item(Separator())

        btn_label = Button(label="📝 Label",       style=ButtonStyle.primary,   custom_id="rre_label")
        btn_emoji = Button(label="🖼️ Emoji",       style=ButtonStyle.primary,   custom_id="rre_emoji")
        btn_desc  = Button(label="📋 Description", style=ButtonStyle.primary,   custom_id="rre_desc")
        btn_del   = Button(label="🗑️ Supprimer",   style=ButtonStyle.danger,    custom_id="rre_del")
        btn_back  = Button(label="↩️ Retour",       style=ButtonStyle.secondary, custom_id="rre_back")

        btn_label.callback = self._on_label
        btn_emoji.callback = self._on_emoji
        btn_desc.callback  = self._on_desc
        btn_del.callback   = self._on_delete
        btn_back.callback  = _back_roles(self.guild_id, self.server, self.owner_id, dashboard=self.dashboard)

        c.add_item(ActionRow(btn_label, btn_emoji, btn_desc, btn_del, btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    def _make_text_modal(self, title: str, label_txt: str, field: str, current: str | None):
        async def on_submit(i: Interaction, value: str) -> None:
            value = value.strip()
            if field == "emoji" and value and not is_valid_emoji(value):
                return await i.response.send_message(
                    f"❌ `{value}` n'est pas un emoji valide — "
                    "vérifie que le nom et l'emoji n'ont pas été inversés.",
                    ephemeral=True,
                )
            await update_rr_entry(self.server, self.entry["id"], **{field: value or None})
            entries = await get_rr_entries(self.server)
            entry = next((e for e in entries if e["id"] == self.entry["id"]), None)
            if entry:
                self.entry = entry
            await i.response.edit_message(
                view=_EditRoleView(self.guild_id, self.server, self.entry, self.owner_id, dashboard=self.dashboard)
            )
        return TextModal(
            title=title, label=label_txt,
            placeholder=current or "",
            default=current or "",
            min_length=0, max_length=200,
            on_submit=on_submit,
        )

    async def _on_label(self, i: Interaction) -> None:
        async def on_submit(inter: Interaction, value: str) -> None:
            if not value.strip():
                return await inter.response.send_message("Le label ne peut pas être vide.", ephemeral=True)
            await update_rr_entry(self.server, self.entry["id"], label=value.strip())
            entries = await get_rr_entries(self.server)
            self.entry = next((e for e in entries if e["id"] == self.entry["id"]), self.entry)
            await inter.response.edit_message(
                view=_EditRoleView(self.guild_id, self.server, self.entry, self.owner_id, dashboard=self.dashboard)
            )
        modal = TextModal(
            title="Modifier le label", label="Nouveau label",
            placeholder="Ex: Actualités", default=self.entry["label"],
            min_length=1, max_length=80, on_submit=on_submit,
        )
        await i.response.send_modal(modal)

    async def _on_emoji(self, i: Interaction) -> None:
        await i.response.send_modal(self._make_text_modal(
            "Modifier l'emoji", "Emoji (unicode ou <:nom:id>)",
            "emoji", self.entry.get("emoji"),
        ))

    async def _on_desc(self, i: Interaction) -> None:
        await i.response.send_modal(self._make_text_modal(
            "Modifier la description", "Description courte (max 200 car.)",
            "description", self.entry.get("description"),
        ))

    async def _on_delete(self, i: Interaction) -> None:
        await remove_rr_entry(self.server, self.entry["id"])
        entries = await get_rr_entries(self.server)
        await i.response.edit_message(
            view=_RolesView(self.guild_id, self.server, entries, self.owner_id, dashboard=self.dashboard)
        )


# ════════════════════════════════════════════════════════════
# ➕ Ajout — Étape 1 : sélection du rôle Discord
# ════════════════════════════════════════════════════════════

class _AddStep1View(LayoutView):
    def __init__(self, guild_id: int, server: str, owner_id: int, *, dashboard: str = "alpha") -> None:
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.server = server
        self.owner_id = owner_id
        self.dashboard = dashboard
        self._build()

    async def interaction_check(self, i): return i.user.id == self.owner_id

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("## ➕ Ajouter un rôle — Étape 1/2"))
        c.add_item(Separator())
        c.add_item(TextDisplay("Sélectionnez le **rôle Discord** à ajouter à la liste."))
        c.add_item(ActionRow(RoleSelect(
            placeholder="Choisir un rôle Discord…",
            on_select=self._on_role_select,
        )))
        c.add_item(Separator())
        btn = Button(label="↩️ Annuler", style=ButtonStyle.secondary, custom_id="rr_add_cancel")
        btn.callback = _back_roles(self.guild_id, self.server, self.owner_id, dashboard=self.dashboard)
        c.add_item(ActionRow(btn))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_role_select(self, i: Interaction, role_ids: list[int]) -> None:
        role_id = role_ids[0]
        role = i.guild.get_role(role_id)
        role_name = role.name if role else f"Rôle {role_id}"

        # Étape 2 : modal avec les détails
        class _Step2Modal(discord.ui.Modal, title="Ajouter un rôle — Étape 2/2"):
            label_input = discord.ui.TextInput(
                label="Nom d'affichage", placeholder=f"Ex: {role_name}",
                min_length=1, max_length=80, required=True,
            )
            emoji_input = discord.ui.TextInput(
                label="Emoji (optionnel)", placeholder="Ex: 📰 ou <:nom:id>",
                max_length=100, required=False,
            )
            desc_input = discord.ui.TextInput(
                label="Description (optionnel)", placeholder="Ex: Actualités du serveur",
                max_length=200, required=False,
            )

            def __init__(self_, gid: int, server: str, rid: int, oid: int, *, dashboard: str = "alpha") -> None:
                super().__init__()
                self_._gid = gid
                self_._server = server
                self_._rid = rid
                self_._oid = oid
                self_._dashboard = dashboard

            async def on_submit(self_, inter: Interaction) -> None:
                label = self_.label_input.value.strip()
                emoji = self_.emoji_input.value.strip() or None
                desc  = self_.desc_input.value.strip() or None

                if emoji and not is_valid_emoji(emoji):
                    return await inter.response.send_message(
                        f"❌ `{emoji}` n'est pas un emoji valide (champ **Emoji**) — "
                        "vérifie que le nom et l'emoji n'ont pas été inversés.",
                        ephemeral=True,
                    )

                ok = await add_rr_entry(self_._server, self_._rid, label, emoji, desc)
                entries = await get_rr_entries(self_._server)
                new_view = _RolesView(
                    self_._gid, self_._server, entries, self_._oid, dashboard=self_._dashboard
                )
                if not ok:
                    await inter.response.edit_message(view=new_view)
                    await inter.followup.send(
                        "Impossible d'ajouter ce rôle (limite atteinte ou rôle déjà présent).",
                        ephemeral=True,
                    )
                else:
                    await inter.response.edit_message(view=new_view)

        await i.response.send_modal(
            _Step2Modal(self.guild_id, self.server, role_id, self.owner_id, dashboard=self.dashboard)
        )
