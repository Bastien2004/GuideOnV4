"""
views/mod/sanction_builder_view.py — Panneau interactif unique pour les
sanctions warn/mute/kick/ban/tempban/softban (/mod <cmd> -> interface).

Remplace les anciens parametres de commande (membre/raison/duree/notifier_mp)
par un panneau Components V2 entierement pilote par l'interface : "TOUT dans
l'interface, aucun attribut de commande" (decision de Paul). La cible est
choisie via UserSelect (membres actuels du serveur) — pour /mod unban, dont
la cible a quitte le serveur, voir views/mod/unban_select_view.py.

Style aligne sur views/bienvenue/config_view.py et views/autorole/config_view.py :
Section(TextDisplay("**emoji Label**\\n-# valeur"), accessory=Button) par champ,
icones maison (modifier/valider/annuler) plutot que des emojis unicode generiques.
"""
from __future__ import annotations

import logging
from datetime import timedelta

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container, success_container, warning_container
from utils.datetime_utils import format_duration, parse_duration
from utils.managers.mod_sanction_manager import (
    MAX_MUTE_SECONDS,
    MAX_TEMPBAN_SECONDS,
    MIN_MUTE_SECONDS,
    MIN_TEMPBAN_SECONDS,
    SANCTION_LABELS,
    SanctionError,
    SanctionType,
)
from utils.managers.mod_sanction_manager import ban as apply_ban
from utils.managers.mod_sanction_manager import kick as apply_kick
from utils.managers.mod_sanction_manager import mute as apply_mute
from utils.managers.mod_sanction_manager import softban as apply_softban
from utils.managers.mod_sanction_manager import tempban as apply_tempban
from utils.managers.mod_sanction_manager import warn as apply_warn
from utils.mod_hierarchy import validate_sanction_target
from utils.settings import settings
from views._components.base_view import BaseLayoutView
from views._components.text_modal import TextModal
from views._components.user_select import UserSelect
from views.mod.sanction_dm_view import build_sanction_dm_view

log = logging.getLogger(__name__)

MIN_REASON_LENGTH = 3
MAX_REASON_LENGTH = 500

# Icones maison — cohérence avec views/bienvenue et views/autorole.
ICON_MODIFIER = "<:modifier:1495444144712192003>"
ICON_VALIDER = "<:valider:1495444292867723284>"
ICON_ANNULER = "<:annuler:1495444256754761979>"

# Types necessitant une duree saisie dans le panneau.
DURATION_TYPES = (SanctionType.MUTE, SanctionType.TEMPBAN)

_DURATION_PLACEHOLDER = {
    SanctionType.MUTE: "Ex : 10m, 2h, 1d2h",
    SanctionType.TEMPBAN: "Ex : 1d, 7d, 30d",
}

_ACTION_LABEL = {
    SanctionType.WARN: "avertissement",
    SanctionType.MUTE: "mute",
    SanctionType.KICK: "expulsion",
    SanctionType.BAN: "bannissement",
    SanctionType.TEMPBAN: "bannissement temporaire",
    SanctionType.SOFTBAN: "softban",
}


class SanctionBuilderView(BaseLayoutView):
    """Panneau unique parametrable par SanctionType (warn/mute/kick/ban/tempban/softban)."""

    def __init__(self, *, sanction_type: SanctionType, guild: discord.Guild, moderator_id: int):
        super().__init__(owner_id=moderator_id, timeout=300)
        self.sanction_type = sanction_type
        self.guild = guild
        self.moderator_id = moderator_id

        self.target: discord.Member | None = None
        self.reason: str | None = None
        self.duration_seconds: int | None = None
        self.notify_mp: bool = True

        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _needs_duration(self) -> bool:
        return self.sanction_type in DURATION_TYPES

    def _is_complete(self) -> bool:
        if self.target is None or not self.reason:
            return False
        if self._needs_duration() and self.duration_seconds is None:
            return False
        return True

    def _build(self) -> None:
        self.clear_items()
        emoji, label = SANCTION_LABELS[self.sanction_type]

        container = Container()
        container.add_item(TextDisplay(f"# {emoji} {label}"))
        container.add_item(Separator())

        # ── Cible (UserSelect — ne peut pas être un accessory de Section) ──
        target_display = self.target.mention if self.target is not None else "`Non sélectionnée`"
        select = UserSelect(placeholder="Choisir un membre", on_select=self._on_select_target)
        container.add_item(TextDisplay(f"**🎯 Cible**\n-# {target_display}"))
        container.add_item(ActionRow(select))
        container.add_item(Separator())

        # ── Raison ────────────────────────────────────────
        reason_display = f"« {self.reason} »" if self.reason else "`Non définie`"
        btn_reason = Button(label="Modifier", style=ButtonStyle.secondary, emoji=ICON_MODIFIER)
        btn_reason.callback = self._on_click_reason
        container.add_item(Section(
            TextDisplay(f"**📝 Raison**\n-# {reason_display}"),
            accessory=btn_reason,
        ))
        container.add_item(Separator())

        # ── Durée (mute/tempban uniquement) ────────────────
        if self._needs_duration():
            dur_display = (
                format_duration(timedelta(seconds=self.duration_seconds))
                if self.duration_seconds else "`Non définie`"
            )
            btn_duration = Button(label="Modifier", style=ButtonStyle.secondary, emoji=ICON_MODIFIER)
            btn_duration.callback = self._on_click_duration
            container.add_item(Section(
                TextDisplay(f"**⏳ Durée**\n-# {dur_display}"),
                accessory=btn_duration,
            ))
            container.add_item(Separator())

        # ── Notification MP (bouton d'état, cf. _state_btn de bienvenue) ──
        btn_mp = Button(
            label="Activé" if self.notify_mp else "Désactivé",
            style=ButtonStyle.success if self.notify_mp else ButtonStyle.danger,
            emoji=ICON_VALIDER if self.notify_mp else ICON_ANNULER,
        )
        btn_mp.callback = self._on_toggle_mp
        container.add_item(Section(
            TextDisplay("**📨 Notification MP**\n-# Prévenir le membre en message privé avant la sanction."),
            accessory=btn_mp,
        ))
        container.add_item(Separator())

        btn_confirm = Button(
            label="Confirmer",
            emoji=ICON_VALIDER,
            style=ButtonStyle.danger,
            disabled=not self._is_complete(),
        )
        btn_confirm.callback = self._on_confirm

        btn_doc = Button(label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚")

        container.add_item(ActionRow(btn_confirm, btn_doc))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self._build()
        await self.push_update(interaction)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def _on_select_target(self, interaction: discord.Interaction, ids: list[int]) -> None:
        member = self.guild.get_member(ids[0])
        if member is None:
            try:
                member = await self.guild.fetch_member(ids[0])
            except discord.NotFound:
                await interaction.response.send_message(
                    view=error_container("Ce membre ne semble plus être sur ce serveur."),
                    ephemeral=True,
                )
                return
            except discord.HTTPException:
                await interaction.response.send_message(
                    view=error_container("Impossible de récupérer ce membre."),
                    ephemeral=True,
                )
                return

        refus = validate_sanction_target(interaction, member)
        if refus is not None:
            await interaction.response.send_message(view=warning_container(refus), ephemeral=True)
            return

        self.target = member
        await self._refresh(interaction)

    async def _on_click_reason(self, interaction: discord.Interaction) -> None:
        async def on_submit(inter: discord.Interaction, value: str) -> None:
            value = value.strip()
            if len(value) < MIN_REASON_LENGTH:
                await inter.response.send_message(
                    view=warning_container(f"La raison doit contenir au moins **{MIN_REASON_LENGTH} caractères**."),
                    ephemeral=True,
                )
                return
            if len(value) > MAX_REASON_LENGTH:
                await inter.response.send_message(
                    view=warning_container(f"La raison doit contenir au maximum **{MAX_REASON_LENGTH} caractères**."),
                    ephemeral=True,
                )
                return
            self.reason = value
            await self._refresh(inter)

        modal = TextModal(
            title=f"Raison — {SANCTION_LABELS[self.sanction_type][1]}",
            label="Raison de la sanction",
            placeholder="Explique la raison de cette sanction...",
            default=self.reason or "",
            min_length=MIN_REASON_LENGTH,
            max_length=MAX_REASON_LENGTH,
            style=discord.TextStyle.paragraph,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _on_click_duration(self, interaction: discord.Interaction) -> None:
        is_mute = self.sanction_type is SanctionType.MUTE
        min_s = MIN_MUTE_SECONDS if is_mute else MIN_TEMPBAN_SECONDS
        max_s = MAX_MUTE_SECONDS if is_mute else MAX_TEMPBAN_SECONDS

        async def on_submit(inter: discord.Interaction, value: str) -> None:
            try:
                duration_seconds = int(parse_duration(value).total_seconds())
            except ValueError:
                await inter.response.send_message(
                    view=warning_container("Format de durée invalide. Exemples valides : `10m`, `2h`, `1d2h30m`."),
                    ephemeral=True,
                )
                return
            if duration_seconds < min_s or duration_seconds > max_s:
                await inter.response.send_message(
                    view=warning_container(f"La durée doit être entre **{min_s}s** et **{max_s}s**."),
                    ephemeral=True,
                )
                return
            self.duration_seconds = duration_seconds
            await self._refresh(inter)

        current = format_duration(timedelta(seconds=self.duration_seconds)) if self.duration_seconds else ""
        modal = TextModal(
            title="Durée de la sanction",
            label="Durée",
            placeholder=_DURATION_PLACEHOLDER[self.sanction_type],
            default=current,
            min_length=2,
            max_length=20,
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _on_toggle_mp(self, interaction: discord.Interaction) -> None:
        self.notify_mp = not self.notify_mp
        await self._refresh(interaction)

    async def _apply(self, dm_sent: bool) -> dict:
        if self.sanction_type is SanctionType.WARN:
            return await apply_warn(self.guild.id, self.target.id, self.moderator_id, self.reason, dm_sent=dm_sent)
        if self.sanction_type is SanctionType.MUTE:
            return await apply_mute(
                self.guild.id, self.target, self.moderator_id, self.reason, self.duration_seconds, dm_sent=dm_sent
            )
        if self.sanction_type is SanctionType.KICK:
            return await apply_kick(self.guild.id, self.target, self.moderator_id, self.reason, dm_sent=dm_sent)
        if self.sanction_type is SanctionType.BAN:
            return await apply_ban(self.guild, self.target, self.moderator_id, self.reason, dm_sent=dm_sent)
        if self.sanction_type is SanctionType.TEMPBAN:
            return await apply_tempban(
                self.guild, self.target, self.moderator_id, self.reason, self.duration_seconds, dm_sent=dm_sent
            )
        if self.sanction_type is SanctionType.SOFTBAN:
            return await apply_softban(self.guild, self.target, self.moderator_id, self.reason, dm_sent=dm_sent)
        raise SanctionError("Type de sanction non pris en charge par ce panneau.")

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        if not self._is_complete():
            await interaction.response.send_message(
                view=warning_container("Veuillez compléter tous les champs requis avant de confirmer."),
                ephemeral=True,
            )
            return

        refus = validate_sanction_target(interaction, self.target)
        if refus is not None:
            await interaction.response.send_message(view=warning_container(refus), ephemeral=True)
            return

        dm_sent = False
        if self.notify_mp:
            try:
                dm_view = build_sanction_dm_view(
                    self.guild.name, self.sanction_type, self.reason,
                    duration_seconds=self.duration_seconds if self._needs_duration() else None,
                )
                await self.target.send(view=dm_view)
                dm_sent = True
            except (discord.Forbidden, discord.HTTPException):
                log.debug("[SANCTION_BUILDER] MP impossible à envoyer à %s", self.target.id)

        try:
            sanction = await self._apply(dm_sent)
        except SanctionError as e:
            view = warning_container(e.message) if e.warning else error_container(e.message)
            await interaction.response.send_message(view=view, ephemeral=True)
            return
        except Exception:
            log.exception(
                "[SANCTION_BUILDER] Échec inattendu type=%s guild=%s user=%s",
                self.sanction_type.value, self.guild.id, self.target.id,
            )
            await interaction.response.send_message(
                view=error_container(
                    f"Une erreur inattendue est survenue lors du **{_ACTION_LABEL[self.sanction_type]}**."
                ),
                ephemeral=True,
            )
            return

        mp_note = "📨 MP envoyé." if dm_sent else ("📭 MP non envoyé." if self.notify_mp else "📭 MP désactivé par le staff.")
        recap_lines = [
            f"**{self.target.mention}** — {_ACTION_LABEL[self.sanction_type]} appliqué (`#{sanction['id']}`).",
            f"-# Raison : {self.reason}",
        ]
        if self._needs_duration():
            recap_lines.append(f"-# Durée : {format_duration(timedelta(seconds=self.duration_seconds))}")
        recap_lines.append(f"-# {mp_note}")

        done_view = success_container("\n".join(recap_lines))
        await self.push_update(interaction, view=done_view)
        self.stop()
