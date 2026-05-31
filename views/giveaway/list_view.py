"""
views/giveaway/list_view.py — Vue /giveaway list (Gold+).

Affiche les giveaways actifs et les 10 derniers terminés, avec sélection
interactive pour voir le détail d'un giveaway. Bouton rafraîchir.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import ButtonStyle, Interaction, SelectOption
from discord.ui import (
    ActionRow, Button, Container, LayoutView, Select, Separator, TextDisplay,
)

from utils.managers.giveaway_manager import (
    count_participants,
    get_active_giveaways,
    get_ended_giveaways,
    get_giveaway,
)

log = logging.getLogger(__name__)


def _end_time_label(end_time: datetime, ended: bool) -> str:
    """Timestamp Discord relatif ou absolu selon état."""
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    ts = int(end_time.timestamp())
    return f"<t:{ts}:{'f' if ended else 'R'}>"


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


class GiveawayListView(LayoutView):
    """Liste interactive des giveaways du serveur."""

    def __init__(
        self,
        guild: discord.Guild,
        active: list[dict],
        ended: list[dict],
        owner_id: int,
        selected_id: Optional[str] = None,
        selected_data: Optional[dict] = None,
        selected_participants: int = 0,
    ):
        super().__init__(timeout=300)
        self.guild = guild
        self.active = active
        self.ended = ended
        self.owner_id = owner_id
        self.selected_id = selected_id
        self.selected_data = selected_data
        self.selected_participants = selected_participants
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            from utils.container_universel import error_container
            await interaction.response.send_message(
                view=error_container("Seul l'**auteur** de la commande peut utiliser ce menu."),
                ephemeral=True,
            )
            return False
        return True

    def _build(self):
        container = Container()

        container.add_item(TextDisplay("# 📋 Giveaways du serveur"))
        container.add_item(TextDisplay("-# ✨ Fonctionnalité Gold+"))
        container.add_item(Separator())

        # ── 🟢 Actifs ──────────────────────────────────────
        container.add_item(TextDisplay(f"### 🟢 En cours ({len(self.active)})"))
        if not self.active:
            container.add_item(TextDisplay("-# *Aucun giveaway actif.*"))
        else:
            lines = []
            for g in self.active[:5]:
                prize = _truncate(g["prize"], 30)
                lines.append(
                    f"-# • `{g['id']}` — **{prize}** — "
                    f"Fin {_end_time_label(g['end_time'], False)}"
                )
            if len(self.active) > 5:
                lines.append(f"-# *...et {len(self.active) - 5} autre(s)*")
            container.add_item(TextDisplay("\n".join(lines)))

            options = []
            for g in self.active[:25]:
                prize = _truncate(g["prize"], 50)
                options.append(SelectOption(
                    label=_truncate(f"{g['id']} — {prize}", 100),
                    value=g["id"],
                    description=_truncate(
                        f"Fin {_end_time_label(g['end_time'], False)}", 100,
                    ).replace("<t:", "").replace(":R>", "").replace(":f>", ""),
                    emoji="🟢",
                    default=(g["id"] == self.selected_id),
                ))
            sel_active = Select(
                placeholder="🟢 Sélectionner un giveaway actif…",
                options=options,
            )
            sel_active.callback = self._on_active_select
            container.add_item(ActionRow(sel_active))

        container.add_item(Separator())

        # ── 🔴 Terminés ────────────────────────────────────
        container.add_item(TextDisplay(f"### 🔴 Derniers terminés ({len(self.ended)})"))
        if not self.ended:
            container.add_item(TextDisplay("-# *Aucun giveaway terminé.*"))
        else:
            lines = []
            for g in self.ended[:5]:
                prize = _truncate(g["prize"], 30)
                nb_win = len(g.get("winners") or [])
                lines.append(
                    f"-# • `{g['id']}` — **{prize}** — 🏆 {nb_win} gagnant(s)"
                )
            if len(self.ended) > 5:
                lines.append(f"-# *...et {len(self.ended) - 5} autre(s)*")
            container.add_item(TextDisplay("\n".join(lines)))

            options_ended = []
            for g in self.ended[:25]:
                prize = _truncate(g["prize"], 50)
                nb_win = len(g.get("winners") or [])
                options_ended.append(SelectOption(
                    label=_truncate(f"{g['id']} — {prize}", 100),
                    value=g["id"],
                    description=f"{nb_win} gagnant(s)",
                    emoji="🔴",
                    default=(g["id"] == self.selected_id),
                ))
            sel_ended = Select(
                placeholder="🔴 Sélectionner un giveaway terminé…",
                options=options_ended,
            )
            sel_ended.callback = self._on_ended_select
            container.add_item(ActionRow(sel_ended))

        container.add_item(Separator())

        # ── 🔍 Détail sélectionné ──────────────────────────
        if self.selected_data:
            g = self.selected_data
            ended = g["ended"]
            container.add_item(TextDisplay("### 🔍 Détail"))
            lines = [
                f"🆔 **ID :** `{g['id']}`",
                f"🏆 **Prix :** {g['prize']}",
                f"👥 **Gagnants à tirer :** {g['winners_count']}",
                f"👤 **Participants :** {self.selected_participants}",
                f"📅 **{'Terminé' if ended else 'Fin'} :** {_end_time_label(g['end_time'], ended)}",
                f"🎤 **Organisateur :** <@{g['host_id']}>",
            ]
            winners = g.get("winners") or []
            if ended and winners:
                mentions = " ".join(f"<@{w}>" for w in winners)
                lines.append(f"🎊 **Gagnant(s) :** {mentions}")

            req = g.get("requirements") or {}
            req_lines = []
            if req.get("role_id"):
                req_lines.append(f"  • Rôle : <@&{req['role_id']}>")
            if req.get("forbidden_role_id"):
                req_lines.append(f"  • Rôle interdit : <@&{req['forbidden_role_id']}>")
            if req.get("min_invites"):
                req_lines.append(f"  • Invitations : {req['min_invites']}+")
            if req.get("min_server_age_days"):
                req_lines.append(f"  • Ancienneté serveur : {req['min_server_age_days']}j+")
            if req_lines:
                lines.append("📋 **Prérequis :**")
                lines.extend(req_lines)

            container.add_item(TextDisplay("\n".join(lines)))
            container.add_item(Separator())

        # ── 🔄 Rafraîchir ──────────────────────────────────
        btn_refresh = Button(label="Rafraîchir", style=ButtonStyle.secondary, emoji="🔄")
        btn_refresh.callback = self._on_refresh
        container.add_item(ActionRow(btn_refresh))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio · ✨ Gold+"))

        self.add_item(container)

    # ─── Callbacks ────────────────────────────────────────

    async def _on_active_select(self, interaction: Interaction):
        gid = interaction.data["values"][0]
        await self._show_selected(interaction, gid)

    async def _on_ended_select(self, interaction: Interaction):
        gid = interaction.data["values"][0]
        await self._show_selected(interaction, gid)

    async def _show_selected(self, interaction: Interaction, gid: str):
        await interaction.response.defer()
        data = await get_giveaway(gid)
        if data is None:
            from utils.container_universel import error_container
            await interaction.followup.send(
                view=error_container("Giveaway **introuvable**."),
                ephemeral=True,
            )
            return
        # Sécurité guild
        if data["guild_id"] != self.guild.id:
            from utils.container_universel import error_container
            await interaction.followup.send(
                view=error_container("Ce giveaway n'appartient pas à ce serveur."),
                ephemeral=True,
            )
            return
        nb = await count_participants(gid)
        new_view = GiveawayListView(
            guild=self.guild, active=self.active, ended=self.ended,
            owner_id=self.owner_id,
            selected_id=gid, selected_data=data, selected_participants=nb,
        )
        await interaction.edit_original_response(view=new_view)

    async def _on_refresh(self, interaction: Interaction):
        await interaction.response.defer()
        active = await get_active_giveaways(self.guild.id)
        ended = await get_ended_giveaways(self.guild.id, limit=10)
        new_view = GiveawayListView(
            guild=self.guild, active=active, ended=ended, owner_id=self.owner_id,
        )
        await interaction.edit_original_response(view=new_view)