"""
views/mod/historique_view.py — Historique des sanctions d'un membre.

Refonte : le résumé par type (self.stats) était déjà calculé et transmis
depuis mod_historique.py mais jamais affiché — corrigé ici (bandeau
récapitulatif en tête de page). Chaque sanction affiche désormais un bouton
"Retirer" qui ouvre le flux de confirmation partagé (_revocation_common) et
supprime DÉFINITIVEMENT l'entrée via mod_sanction_manager.purge_sanction —
pensé pour corriger une erreur de sanction staff (mauvaise cible, mauvais
type...), pas pour lever une sanction normalement arrivée à échéance (ça,
c'est déjà le rôle de /mod unmute et /mod unban).
"""

from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import Button, Container, Section, Separator, TextDisplay

from utils.managers.mod_sanction_manager import SANCTION_LABELS, SanctionType, purge_sanction
from views._components.paginated_view import PaginatedView
from views.mod._revocation_common import RevocationConfirmView

ICON_DELETE = "<:supprimer:1495444051623809075>"


def _status_label(sanction: dict) -> str:
    """Statut d'une sanction."""

    if sanction["revoked_at"] is not None:
        return "*Révoquée*"

    if sanction["type"] in (SanctionType.MUTE.value, SanctionType.TEMPBAN.value):
        if sanction["active"]:
            return "*En cours*"
        return "*Expirée*"

    if sanction["type"] in (SanctionType.BAN.value, SanctionType.SOFTBAN.value):
        return "*En cours*" if sanction["active"] else "*Terminée*"

    return "*Terminée*"


def _build_stats_summary(stats: dict) -> str:
    """Bandeau récapitulatif par type de sanction (données déjà calculées par get_user_stats)."""
    parts = []
    for sanction_type in SanctionType:
        emoji, _ = SANCTION_LABELS[sanction_type]
        count = stats.get(sanction_type.value, 0)
        parts.append(f"{emoji} `{count}`")
    return "**📊 Résumé** — " + " · ".join(parts)


class HistoriqueView(PaginatedView):
    """Liste paginée des sanctions d'un membre, avec suppression d'entrée."""

    def __init__(
        self, entries: list[dict], *, target_display: str, stats: dict,
        guild: discord.Guild, owner_id: int, per_page: int = 8,
    ):
        self.target_display = target_display
        self.stats = stats
        self.guild = guild
        super().__init__(entries, per_page=per_page, owner_id=owner_id)

    def build_page_container(self, page_items: list) -> Container:
        container = Container()

        container.add_item(TextDisplay(f"# <:fichier:1495446721520730242> Historique de {self.target_display}"))
        container.add_item(Separator())

        container.add_item(TextDisplay(_build_stats_summary(self.stats)))
        container.add_item(Separator())

        if not page_items:
            container.add_item(TextDisplay("-# <:annuler:1495444256754761979> Aucune sanction enregistrée pour ce membre."))
            return container

        for sanction in page_items:
            emoji, label = SANCTION_LABELS[SanctionType(sanction["type"])]
            status = _status_label(sanction)
            created_ts = int(sanction["created_at"].timestamp())
            text = (
                f"➤ `#{sanction['id']}` - {emoji} **{label}** — {status}\n"
                f"➥ {sanction['reason']} · <t:{created_ts}:R>\n"
                f"Par <@{sanction['moderator_id']}>."
            )

            btn_purge = Button(label="Retirer", style=ButtonStyle.danger, emoji=ICON_DELETE)
            btn_purge.callback = self._make_purge_callback(sanction, label)
            container.add_item(Section(TextDisplay(text), accessory=btn_purge))
            container.add_item(Separator())

        return container

    # ------------------------------------------------------------------
    # Suppression d'une entrée
    # ------------------------------------------------------------------

    def _make_purge_callback(self, sanction: dict, type_label: str):
        sanction_id = sanction["id"]

        async def on_confirm(reason: str | None) -> dict:
            return await purge_sanction(
                sanction_id, self.owner_id, reason, guild=self.guild,
            )

        async def build_back_view() -> discord.ui.View:
            return self

        async def cb(interaction: discord.Interaction) -> None:
            confirm_view = RevocationConfirmView(
                title=f"🗑️ Retirer la sanction #{sanction_id} ({type_label}) ?",
                target_display=self.target_display,
                moderator_id=self.owner_id,
                on_confirm=on_confirm,
                build_back_view=build_back_view,
                action_label="suppression de l'historique",
            )
            await self.push_update(interaction, view=confirm_view)

        return cb