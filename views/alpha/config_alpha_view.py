"""
views/alpha/config_alpha_view.py — Dashboard de configuration du système de rank Alpha.
"""

from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.managers.alpha_rank_config_manager import load_rank_config, save_rank_config
from views._components.channel_select import ChannelSelect
from views._components.role_select import RoleSelect

log = logging.getLogger(__name__)


# ── Helpers d'affichage ──────────────────────────────────────

def _ch(val: int | None) -> str:
    return f"<#{val}>" if val else "`Non configuré`"

def _role(val: int | None) -> str:
    return f"<@&{val}>" if val else "`Non configuré`"


# ════════════════════════════════════════════════════════════
# 🏠 Vue principale
# ════════════════════════════════════════════════════════════

class ConfigRankView(LayoutView):
    """Dashboard principal — aperçu de la config + boutons de section."""

    def __init__(self, guild_id: int, cfg: dict, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.cfg = cfg
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Seul l'auteur peut utiliser ce menu.", ephemeral=True
            )
            return False
        return True

    def _build(self) -> None:
        cfg = self.cfg
        c = Container()
        c.add_item(TextDisplay("# <:parametre:1495444004328706059> Config Alpha — Système Rank"))
        c.add_item(Separator())

        c.add_item(TextDisplay(
            f"__**<:salons:1508535670333902999> Salons**__\n"
            f"➢ **Rank/Derank** : {_ch(cfg.get('rank_channel_id'))}\n"
            f"➢ **Journalistes** : {_ch(cfg.get('journaliste_channel_id'))}\n"
            f"➢ **Développeurs** : {_ch(cfg.get('dev_channel_id'))}\n\n"
        ))
        c.add_item(Separator())

        c.add_item(TextDisplay(
            f"__**<:notifier:1495444487206604833> Pings**__\n"
            f"➢ **Journaliste** : {_role(cfg.get('journaliste_ping_id'))}\n"
            f"➢ **Développeur** : {_role(cfg.get('dev_ping_id'))}\n\n"
        ))
        c.add_item(Separator())

        c.add_item(TextDisplay(
            f"**🎭 Rôles par grade**\n"
            f"• Guide : {_role(cfg.get('role_guide_id'))}\n"
            f"• Modo (test) : {_role(cfg.get('role_moderateur_test_id'))}\n"
            f"• Modo confirmé : {_role(cfg.get('role_moderateur_confirme_id'))}\n"
            f"• Modo+ : {_role(cfg.get('role_moderateur_plus_id'))}\n"
            f"• Super-Modo : {_role(cfg.get('role_super_moderateur_id'))}\n"
            f"• Admin : {_role(cfg.get('role_administrateur_id'))}\n"
            f"• 🔰 Staff Alpha (rôle équipe) : {_role(cfg.get('role_equipe_id'))}\n\n"
        ))
        c.add_item(Separator())

        c.add_item(TextDisplay(
            f"**🎭 Statuts secondaires**\n"
            f"• 📰 Journaliste : {_role(cfg.get('role_journaliste_id'))}\n"
            f"• 🎥 Affilié : {_role(cfg.get('role_affilie_id'))}\n"
            f"• 🧱 Builder : {_role(cfg.get('role_builder_id'))}\n\n"
        ))
        c.add_item(Separator())

        c.add_item(TextDisplay(
            f"**🎭 Emoji annonce**\n"
            f"• Réaction rank/derank : {cfg.get('rank_emoji') or '`Non configuré`'}"
        ))
        c.add_item(Separator())

        btn_salons = Button(label="📡 Salons", style=ButtonStyle.primary, custom_id="cfg_salons")
        btn_pings  = Button(label="🔔 Pings",  style=ButtonStyle.primary, custom_id="cfg_pings")
        btn_roles1 = Button(label="🎭 Rôles",  style=ButtonStyle.primary, custom_id="cfg_roles1")
        btn_emoji  = Button(label="🎭 Emoji annonce", style=ButtonStyle.secondary, custom_id="cfg_emoji")
        btn_back   = Button(label="↩️ Tableau de bord", style=ButtonStyle.secondary, custom_id="cfg_back_dash")
        btn_salons.callback = self._on_salons
        btn_pings.callback  = self._on_pings
        btn_roles1.callback = self._on_roles1
        btn_emoji.callback  = self._on_emoji
        btn_back.callback   = self._on_back_dash

        c.add_item(ActionRow(btn_salons, btn_pings, btn_roles1))
        c.add_item(ActionRow(btn_emoji, btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    # ── Callbacks de navigation ──────────────────────────────

    async def _on_back_dash(self, interaction: Interaction) -> None:
        from views.alpha.config_dashboard_view import ConfigDashboardView
        await interaction.response.edit_message(
            view=ConfigDashboardView(self.guild_id, self.owner_id)
        )

    async def _on_salons(self, interaction: Interaction) -> None:
        cfg = await load_rank_config(self.guild_id)
        await interaction.response.edit_message(
            view=_SalonsView(self.guild_id, cfg, self.owner_id)
        )

    async def _on_pings(self, interaction: Interaction) -> None:
        cfg = await load_rank_config(self.guild_id)
        await interaction.response.edit_message(
            view=_PingsView(self.guild_id, cfg, self.owner_id)
        )

    async def _on_roles1(self, interaction: Interaction) -> None:
        cfg = await load_rank_config(self.guild_id)
        await interaction.response.edit_message(
            view=_RolesView(self.guild_id, cfg, self.owner_id, page=1)
        )

    async def _on_emoji(self, interaction: Interaction) -> None:
        from views._components.text_modal import TextModal
        current = self.cfg.get("rank_emoji") or ""

        async def on_submit(inter: Interaction, value: str) -> None:
            cfg = await save_rank_config(self.guild_id, rank_emoji=value.strip() or None)
            await inter.response.edit_message(
                view=ConfigRankView(self.guild_id, cfg, self.owner_id)
            )

        modal = TextModal(
            title="Emoji annonce rank/derank",
            label="Emoji (custom ou unicode, vide = désactiver)",
            placeholder="Ex: <:Alpha:1500414179650048070> ou 🎉",
            default=current,
            min_length=0,
            max_length=100,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)


# ════════════════════════════════════════════════════════════
# 📡 Sous-vue Salons
# ════════════════════════════════════════════════════════════

class _SalonsView(LayoutView):
    def __init__(self, guild_id: int, cfg: dict, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.cfg = cfg
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.owner_id

    def _build(self) -> None:
        cfg = self.cfg
        c = Container()
        c.add_item(TextDisplay("## 📡 Configuration des Salons"))
        c.add_item(Separator())

        c.add_item(TextDisplay(f"**Salon rank/derank :** {_ch(cfg.get('rank_channel_id'))}"))
        c.add_item(ActionRow(ChannelSelect(
            placeholder="Choisir le salon rank/derank",
            on_select=lambda i, ch: self._save(i, "rank_channel_id", ch),
            channel_types=[discord.ChannelType.text],
        )))

        c.add_item(TextDisplay(f"**Salon journalistes :** {_ch(cfg.get('journaliste_channel_id'))}"))
        c.add_item(ActionRow(ChannelSelect(
            placeholder="Choisir le salon journalistes",
            on_select=lambda i, ch: self._save(i, "journaliste_channel_id", ch),
            channel_types=[discord.ChannelType.text],
        )))

        c.add_item(TextDisplay(f"**Salon développeurs :** {_ch(cfg.get('dev_channel_id'))}"))
        c.add_item(ActionRow(ChannelSelect(
            placeholder="Choisir le salon développeurs",
            on_select=lambda i, ch: self._save(i, "dev_channel_id", ch),
            channel_types=[discord.ChannelType.text],
        )))

        c.add_item(Separator())
        btn_back = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="salons_back")
        btn_back.callback = self._on_back
        c.add_item(ActionRow(btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _save(self, interaction: Interaction, field: str, value: int) -> None:
        self.cfg = await save_rank_config(self.guild_id, **{field: value})
        await interaction.response.edit_message(
            view=_SalonsView(self.guild_id, self.cfg, self.owner_id)
        )

    async def _on_back(self, interaction: Interaction) -> None:
        cfg = await load_rank_config(self.guild_id)
        await interaction.response.edit_message(
            view=ConfigRankView(self.guild_id, cfg, self.owner_id)
        )


# ════════════════════════════════════════════════════════════
# 🔔 Sous-vue Pings
# ════════════════════════════════════════════════════════════

class _PingsView(LayoutView):
    def __init__(self, guild_id: int, cfg: dict, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.cfg = cfg
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.owner_id

    def _build(self) -> None:
        cfg = self.cfg
        c = Container()
        c.add_item(TextDisplay("## 🔔 Configuration des Pings"))
        c.add_item(Separator())

        c.add_item(TextDisplay(
            f"**Ping journaliste :** {_role(cfg.get('journaliste_ping_id'))}\n"
            f"-# Rôle @mentionné dans le message d'affiche de rank/derank"
        ))
        c.add_item(ActionRow(RoleSelect(
            placeholder="Choisir le rôle @Journaliste",
            on_select=lambda i, ids: self._save(i, "journaliste_ping_id", ids[0]),
        )))

        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**Ping développeur :** {_role(cfg.get('dev_ping_id'))}\n"
            f"-# Rôle @mentionné pour demander l'ajout d'un emoji skin"
        ))
        c.add_item(ActionRow(RoleSelect(
            placeholder="Choisir le rôle @Développeur",
            on_select=lambda i, ids: self._save(i, "dev_ping_id", ids[0]),
        )))

        c.add_item(Separator())
        btn_back = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="pings_back")
        btn_back.callback = self._on_back
        c.add_item(ActionRow(btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _save(self, interaction: Interaction, field: str, value: int) -> None:
        self.cfg = await save_rank_config(self.guild_id, **{field: value})
        await interaction.response.edit_message(
            view=_PingsView(self.guild_id, self.cfg, self.owner_id)
        )

    async def _on_back(self, interaction: Interaction) -> None:
        cfg = await load_rank_config(self.guild_id)
        await interaction.response.edit_message(
            view=ConfigRankView(self.guild_id, cfg, self.owner_id)
        )


# ════════════════════════════════════════════════════════════
# 🎭 Sous-vue Rôles par grade (paginée : 3 pages de 3-4 rôles)
# ════════════════════════════════════════════════════════════

_ROLES_PAGES: list[list[tuple[str, str]]] = [
    # page 1 : grades inférieurs
    [
        ("role_guide_id",               "Guide"),
        ("role_moderateur_test_id",     "Modérateur (Test)"),
        ("role_moderateur_confirme_id", "Modérateur Confirmé"),
        ("role_moderateur_plus_id",     "Modérateur+"),
    ],
    # page 2 : grades supérieurs + rôle équipe transverse
    [
        ("role_super_moderateur_id",  "Super Modérateur"),
        ("role_administrateur_id",    "Administrateur"),
        ("role_equipe_id",            "🔰 Staff Alpha (rôle équipe — tous grades)"),
    ],
    # page 3 : statuts secondaires (cumulables, hors hiérarchie)
    [
        ("role_journaliste_id", "📰 Journaliste"),
        ("role_affilie_id",     "🎥 Affilié"),
        ("role_builder_id",     "🧱 Builder"),
    ],
]
_TOTAL_PAGES = len(_ROLES_PAGES)


class _RolesView(LayoutView):
    def __init__(self, guild_id: int, cfg: dict, owner_id: int, page: int = 1) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.cfg = cfg
        self.owner_id = owner_id
        self.page = page  # 1 à _TOTAL_PAGES
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.owner_id

    def _build(self) -> None:
        cfg = self.cfg
        page_idx = self.page - 1
        grades = _ROLES_PAGES[page_idx]

        c = Container()
        c.add_item(TextDisplay(f"## 🎭 Rôles par grade — page {self.page}/{_TOTAL_PAGES}"))
        c.add_item(Separator())

        for field, label in grades:
            c.add_item(TextDisplay(f"**{label} :** {_role(cfg.get(field))}"))
            c.add_item(ActionRow(RoleSelect(
                placeholder=f"Rôle Discord → {label}",
                on_select=self._make_save(field),
            )))

        c.add_item(Separator())

        # Navigation
        nav_buttons: list[Button] = []
        if self.page > 1:
            btn_prev = Button(label="◀ Page précédente", style=ButtonStyle.secondary, custom_id="roles_prev")
            btn_prev.callback = self._on_prev
            nav_buttons.append(btn_prev)
        if self.page < _TOTAL_PAGES:
            btn_next = Button(label="Page suivante ▶", style=ButtonStyle.secondary, custom_id="roles_next")
            btn_next.callback = self._on_next
            nav_buttons.append(btn_next)
        btn_back = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="roles_back")
        btn_back.callback = self._on_back
        nav_buttons.append(btn_back)
        c.add_item(ActionRow(*nav_buttons))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    def _make_save(self, field: str):
        async def _save(interaction: Interaction, role_ids: list[int]) -> None:
            self.cfg = await save_rank_config(self.guild_id, **{field: role_ids[0]})
            await interaction.response.edit_message(
                view=_RolesView(self.guild_id, self.cfg, self.owner_id, page=self.page)
            )
        return _save

    async def _on_prev(self, interaction: Interaction) -> None:
        cfg = await load_rank_config(self.guild_id)
        await interaction.response.edit_message(
            view=_RolesView(self.guild_id, cfg, self.owner_id, page=self.page - 1)
        )

    async def _on_next(self, interaction: Interaction) -> None:
        cfg = await load_rank_config(self.guild_id)
        await interaction.response.edit_message(
            view=_RolesView(self.guild_id, cfg, self.owner_id, page=self.page + 1)
        )

    async def _on_back(self, interaction: Interaction) -> None:
        cfg = await load_rank_config(self.guild_id)
        await interaction.response.edit_message(
            view=ConfigRankView(self.guild_id, cfg, self.owner_id)
        )