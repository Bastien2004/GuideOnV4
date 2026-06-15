"""
views/giveaway/blacklist_view.py — Panneau /giveaway blacklist (admin).

Affiche la blacklist du serveur paginée (10/page). Actions :
- "Ajouter" → UserSelect ephemeral + modal optionnel (raison + durée en jours)
- "Retirer" → UserSelect des utilisateurs actuellement blacklist
- "Purger expirés" → supprime les entrées expirées
- "Rafraîchir"
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import (
    ActionRow, Button, Container, LayoutView, Separator, TextDisplay,
)

from utils.container_universel import error_container, info_container, success_container
from utils.managers.giveaway_manager import (
    add_to_blacklist,
    get_blacklist,
    purge_expired_blacklist,
    remove_from_blacklist,
)
from views._components.text_modal import TextModal
from views._components.user_select import UserSelect

log = logging.getLogger(__name__)

PER_PAGE = 10
MAX_REASON_LENGTH = 500
MAX_DURATION_DAYS = 365 * 10  # 10 ans


def _fmt_expires(expires_at: Optional[datetime]) -> str:
    if expires_at is None:
        return "**Permanente**"
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return f"Jusqu'au <t:{int(expires_at.timestamp())}:f>"


def _parse_duration_days(s: str) -> Optional[int]:
    """Parse une durée en jours simple : entier, ou 'Nd' pour N jours. None si invalide ou vide."""
    s = s.strip()
    if not s or s == "0":
        return None
    # accepte "30" ou "30d"
    m = re.fullmatch(r"(\d+)d?", s.lower())
    if not m:
        return None
    n = int(m.group(1))
    if n <= 0 or n > MAX_DURATION_DAYS:
        return None
    return n


class BlacklistView(LayoutView):
    """Panneau de gestion de la blacklist giveaway."""

    def __init__(
        self, guild: discord.Guild, entries: list[dict],
        owner_id: int, page: int = 0,
    ):
        super().__init__(timeout=600)
        self.guild = guild
        self.entries = entries  # déjà filtrés (sans expirés)
        self.owner_id = owner_id
        self.page = page
        self.total_pages = max(1, (len(entries) + PER_PAGE - 1) // PER_PAGE)
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                view=error_container("Seul l'**auteur** peut utiliser ce menu."),
                ephemeral=True,
            )
            return False
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                view=error_container("Vous devez être **Administrateur**."),
                ephemeral=True,
            )
            return False
        return True

    def _build(self):
        container = Container()

        container.add_item(TextDisplay("# 🚫 Blacklist · Giveaway"))
        container.add_item(TextDisplay(f"-# {len(self.entries)} entrée(s) active(s)"))
        container.add_item(Separator())

        # ── Liste paginée ─────────────────────────────────
        if not self.entries:
            container.add_item(TextDisplay("-# 🤷 Aucun utilisateur blacklist sur ce serveur."))
        else:
            start = self.page * PER_PAGE
            end = start + PER_PAGE
            page_items = self.entries[start:end]

            lines = []
            for entry in page_items:
                uid = entry["user_id"]
                reason = entry.get("reason") or "*aucune raison*"
                exp = _fmt_expires(entry.get("expires_at"))
                added_by = entry.get("added_by")
                lines.append(
                    f"-# 🚫 <@{uid}>\n"
                    f"-# ↳ {reason}\n"
                    f"-# ↳ {exp} · ajouté par <@{added_by}>"
                )
            container.add_item(TextDisplay("\n".join(lines)))
            container.add_item(Separator())

            # Pagination
            if self.total_pages > 1:
                btn_prev = Button(label="◀", style=ButtonStyle.secondary,
                                  disabled=(self.page == 0))
                btn_prev.callback = self._on_prev
                btn_page = Button(
                    label=f"Page {self.page + 1} / {self.total_pages}",
                    style=ButtonStyle.secondary, disabled=True,
                )
                btn_next = Button(label="▶", style=ButtonStyle.secondary,
                                  disabled=(self.page >= self.total_pages - 1))
                btn_next.callback = self._on_next
                container.add_item(ActionRow(btn_prev, btn_page, btn_next))
                container.add_item(Separator())

        # ── Actions ───────────────────────────────────────
        btn_add = Button(label="Ajouter", style=ButtonStyle.success, emoji="➕")
        btn_add.callback = self._on_add
        btn_remove = Button(label="Retirer", style=ButtonStyle.danger, emoji="➖")
        btn_remove.callback = self._on_remove
        btn_purge = Button(label="Purger expirés", style=ButtonStyle.secondary, emoji="🧹")
        btn_purge.callback = self._on_purge
        btn_refresh = Button(label="Rafraîchir", style=ButtonStyle.secondary, emoji="🔄")
        btn_refresh.callback = self._on_refresh
        container.add_item(ActionRow(btn_add, btn_remove, btn_purge, btn_refresh))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    # ─── Pagination ──────────────────────────────────────

    async def _reload(self, interaction: Interaction):
        """Recharge la blacklist depuis la DB et redessine la vue."""
        entries = await get_blacklist(self.guild.id, include_expired=False)
        new_view = BlacklistView(
            guild=self.guild, entries=entries, owner_id=self.owner_id,
            page=min(self.page, max(0, (len(entries) - 1) // PER_PAGE)),
        )
        if interaction.response.is_done():
            await interaction.edit_original_response(view=new_view)
        else:
            await interaction.response.edit_message(view=new_view)

    async def _on_prev(self, interaction: Interaction):
        self.page = max(0, self.page - 1)
        new_view = BlacklistView(
            guild=self.guild, entries=self.entries,
            owner_id=self.owner_id, page=self.page,
        )
        await interaction.response.edit_message(view=new_view)

    async def _on_next(self, interaction: Interaction):
        self.page = min(self.total_pages - 1, self.page + 1)
        new_view = BlacklistView(
            guild=self.guild, entries=self.entries,
            owner_id=self.owner_id, page=self.page,
        )
        await interaction.response.edit_message(view=new_view)

    async def _on_refresh(self, interaction: Interaction):
        await interaction.response.defer()
        await self._reload(interaction)

    # ─── Actions ──────────────────────────────────────────

    async def _on_add(self, interaction: Interaction):
        async def back_to_main(back_inter: Interaction):
            entries = await get_blacklist(self.guild.id, include_expired=False)
            new_view = BlacklistView(
                guild=self.guild, entries=entries,
                owner_id=self.owner_id, page=0,
            )
            await back_inter.response.edit_message(view=new_view)

        async def on_user_select(sel: Interaction, user_ids: list[int]):
            if not user_ids:
                return
            uid = user_ids[0]
            if uid == sel.user.id:
                await sel.response.send_message(
                    view=error_container("Tu ne peux pas te **blacklist toi-même**."),
                    ephemeral=True,
                )
                return
            member = sel.guild.get_member(uid)
            if member is not None and member.bot:
                await sel.response.send_message(
                    view=error_container("Les **bots** ne peuvent pas être blacklist."),
                    ephemeral=True,
                )
                return

            # Modal raison + durée (les deux optionnels). Discord ouvre le modal
            # par-dessus naturellement, pas de problème UX.
            async def on_submit(inter: Interaction, reason: str, duration: str):
                reason = reason.strip() or None
                days = _parse_duration_days(duration)
                expires_at = (datetime.now(timezone.utc) + timedelta(days=days)) if days else None
                try:
                    await add_to_blacklist(
                        sel.guild.id, uid,
                        added_by=sel.user.id,
                        reason=reason,
                        expires_at=expires_at,
                    )
                except Exception:
                    log.exception("Échec add_to_blacklist")
                    await inter.response.send_message(
                        view=error_container("Erreur lors de l'**ajout** à la blacklist."),
                        ephemeral=True,
                    )
                    return
                # Retour direct à la vue principale (l'entrée s'y verra)
                entries = await get_blacklist(self.guild.id, include_expired=False)
                new_view = BlacklistView(
                    guild=self.guild, entries=entries,
                    owner_id=self.owner_id, page=0,
                )
                await inter.response.edit_message(view=new_view)

            modal = _BlacklistAddModal(
                title=f"🚫 Blacklist · {uid}",
                on_submit=on_submit,
            )
            await sel.response.send_modal(modal)

        select = UserSelect(
            placeholder="Sélectionner un utilisateur",
            on_select=on_user_select, min_values=1, max_values=1,
        )
        btn_cancel = Button(label="Annuler", style=ButtonStyle.secondary, emoji="↩️")
        btn_cancel.callback = back_to_main

        temp = LayoutView(timeout=120)
        c = Container()
        c.add_item(TextDisplay("# ➕ Ajouter à la blacklist"))
        c.add_item(TextDisplay("-# Sélectionne l'utilisateur à blacklist."))
        c.add_item(Separator())
        c.add_item(ActionRow(select))
        c.add_item(Separator())
        c.add_item(ActionRow(btn_cancel))
        temp.add_item(c)
        await interaction.response.edit_message(view=temp)

    async def _on_remove(self, interaction: Interaction):
        if not self.entries:
            await interaction.response.send_message(
                view=info_container("La blacklist est **vide**."),
                ephemeral=True,
            )
            return

        async def back_to_main(back_inter: Interaction):
            entries = await get_blacklist(self.guild.id, include_expired=False)
            new_view = BlacklistView(
                guild=self.guild, entries=entries,
                owner_id=self.owner_id, page=0,
            )
            await back_inter.response.edit_message(view=new_view)

        async def on_user_select(sel: Interaction, user_ids: list[int]):
            if not user_ids:
                return
            uid = user_ids[0]
            removed = await remove_from_blacklist(sel.guild.id, uid)
            if not removed:
                # Pas dans la blacklist → message d'info dans la vue + retour
                empty = LayoutView(timeout=120)
                c = Container()
                c.add_item(TextDisplay("# ➖ Retrait"))
                c.add_item(Separator())
                c.add_item(TextDisplay(
                    f"-# ℹ️ <@{uid}> n'était **pas** dans la blacklist."
                ))
                c.add_item(Separator())
                btn_back = Button(label="Retour", style=ButtonStyle.secondary, emoji="↩️")
                btn_back.callback = back_to_main
                c.add_item(ActionRow(btn_back))
                empty.add_item(c)
                await sel.response.edit_message(view=empty)
                return
            # Retour direct à la vue principale (l'entrée a disparu)
            entries = await get_blacklist(self.guild.id, include_expired=False)
            new_view = BlacklistView(
                guild=self.guild, entries=entries,
                owner_id=self.owner_id, page=0,
            )
            await sel.response.edit_message(view=new_view)

        select = UserSelect(
            placeholder="Sélectionner l'utilisateur à retirer",
            on_select=on_user_select, min_values=1, max_values=1,
        )
        btn_cancel = Button(label="Annuler", style=ButtonStyle.secondary, emoji="↩️")
        btn_cancel.callback = back_to_main

        temp = LayoutView(timeout=120)
        c = Container()
        c.add_item(TextDisplay("# ➖ Retirer de la blacklist"))
        c.add_item(TextDisplay("-# Sélectionne l'utilisateur à retirer."))
        c.add_item(Separator())
        c.add_item(ActionRow(select))
        c.add_item(Separator())
        c.add_item(ActionRow(btn_cancel))
        temp.add_item(c)
        await interaction.response.edit_message(view=temp)

    async def _on_purge(self, interaction: Interaction):
        await interaction.response.defer()
        purged = await purge_expired_blacklist(self.guild.id)
        if purged == 0:
            await interaction.followup.send(
                view=info_container("Aucune entrée expirée à purger."),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                view=success_container(f"**{purged}** entrée(s) expirée(s) supprimée(s)."),
                ephemeral=True,
            )
        await self._reload(interaction)


# ======================================================
# ============ MODAL : ajout blacklist =================
# ======================================================

class _BlacklistAddModal(discord.ui.Modal):
    """Modal avec 2 champs : raison (optionnelle) + durée en jours (optionnelle)."""

    def __init__(self, title: str, on_submit):
        super().__init__(title=title)
        self._on_submit = on_submit
        self.reason_input = discord.ui.TextInput(
            label="Raison (optionnel)",
            placeholder="Ex : Triche signalée",
            required=False,
            max_length=MAX_REASON_LENGTH,
            style=discord.TextStyle.paragraph,
        )
        self.duration_input = discord.ui.TextInput(
            label="Durée en jours (vide = permanent)",
            placeholder="Ex : 30",
            required=False,
            max_length=6,
            style=discord.TextStyle.short,
        )
        self.add_item(self.reason_input)
        self.add_item(self.duration_input)

    async def on_submit(self, interaction: Interaction) -> None:
        await self._on_submit(
            interaction,
            self.reason_input.value or "",
            self.duration_input.value or "",
        )


# ======================================================
# ========= COMPAT COMMANDE : BlacklistView ============
# ======================================================

class GiveawayBlacklistView:
    @classmethod
    async def create(cls, guild: discord.Guild, owner_id: int) -> LayoutView:
        entries = await get_blacklist(guild.id, include_expired=False)
        return BlacklistView(guild=guild, entries=entries, owner_id=owner_id)