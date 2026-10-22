"""
views/ticket/panel_picker.py — Sélecteur de panel réutilisable (CV2 pur).

Ajouté lors de la refonte 2026-10-21 pour "uniformiser" /ticket panel_edit et
/ticket panel_delete avec le nouveau dashboard à menu déroulant unique
(cf. panel_setup_view.py) : ces deux commandes exigeaient jusqu'ici un lien
de message à copier-coller (clic droit → Copier le lien). Ce lien reste
accepté (plus rapide quand on l'a sous la main), mais devient optionnel —
quand il n'est pas fourni, ce sélecteur affiche la liste des panels du
serveur dans un menu déroulant natif, et l'admin choisit directement dans la
liste plutôt que de devoir retrouver/copier un lien.

`build_panel_picker_view` est volontairement générique (titre/description +
callback `on_pick` injecté) pour être partagé par panel_edit (ouvre le
dashboard de configuration pré-rempli) ET panel_delete (ouvre une
confirmation de suppression) sans dupliquer la logique d'affichage du menu.

Important : l'interaction reçue par `on_pick` est celle du SELECT (une
interaction fraîche, pas encore répondue) — pas celle de la commande slash
d'origine, qui a déjà été deferred plus haut. Chaque appelant doit donc
répondre à CETTE interaction (modal, `response.edit_message`, ou
`response.send_message` pour une nouvelle confirmation), jamais réutiliser
`interaction.followup` de la commande d'origine à cet endroit.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

import discord
from discord.ui import ActionRow, Container, LayoutView, Select, Separator, TextDisplay

from utils.container_universel import error_container
from utils.ticket_limits import DEFAULT_PANEL_EMOJI, MAX_SELECT_OPTIONS, WIZARD_TIMEOUT

# Signature du callback injecté par l'appelant (panel_edit / panel_delete).
OnPick = Callable[[discord.Interaction, dict], Awaitable[None]]

_LABEL_MAX = 100   # Plafond Discord : SelectOption.label.
_DESC_MAX = 95      # Plafond Discord 100 sur SelectOption.description, petite marge pour l'ellipse.


def _truncate(s: str, n: int) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _panel_description(guild: discord.Guild, panel: dict) -> str:
    """Description courte affichée sous le titre, dans le menu déroulant."""

    channel = guild.get_channel(panel.get("channel_id", 0))
    chan_part = f"#{channel.name}" if channel else "⚠️ salon introuvable"
    opened = panel.get("open_tickets_count", 0)
    return _truncate(f"{chan_part} · 🟢 {opened} en cours", _DESC_MAX)


# ============================================================
# 🪟 Vue — menu déroulant de sélection de panel
# ============================================================

def build_panel_picker_view(
    guild: discord.Guild,
    panels: list[dict],
    *,
    title: str,
    description: str,
    on_pick: OnPick,
) -> LayoutView:
    """Construit l'écran "choisir un panel" (menu déroulant natif).

    `panels` doit être non vide (les appelants vérifient `tm.list_panels(...)`
    avant d'appeler cette fonction et gèrent eux-mêmes le cas "aucun panel").
    """
    view = LayoutView(timeout=WIZARD_TIMEOUT)
    container = Container()

    container.add_item(TextDisplay(f"# {title}"))
    container.add_item(TextDisplay(f"-# {description}"))
    container.add_item(Separator())

    shown = panels[:MAX_SELECT_OPTIONS]
    options = [
        discord.SelectOption(
            label=_truncate(p.get("title") or p["panel_id"], _LABEL_MAX),
            value=p["panel_id"],
            description=_panel_description(guild, p),
            emoji=p.get("panel_emoji") or DEFAULT_PANEL_EMOJI,
        )
        for p in shown
    ]
    select = _PanelPickSelect(
        panels_by_id={p["panel_id"]: p for p in shown},
        on_pick=on_pick,
        options=options,
    )
    container.add_item(ActionRow(select))

    if len(panels) > MAX_SELECT_OPTIONS:
        container.add_item(Separator())
        container.add_item(TextDisplay(
            f"-# … et **{len(panels) - MAX_SELECT_OPTIONS}** autre(s) panel(s) non affiché(s)."
        ))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


class _PanelPickSelect(Select):
    """Le menu déroulant : une option par panel, choisir une option invoque
    le callback `on_pick` injecté par l'appelant avec le dict panel résolu."""

    def __init__(self, *, panels_by_id: dict[str, dict], on_pick: OnPick, options):
        super().__init__(
            placeholder="📋 Choisir un panel…",
            options=options,
            min_values=1,
            max_values=1,
        )
        self._panels_by_id = panels_by_id
        self._on_pick = on_pick

    async def callback(self, interaction: discord.Interaction) -> None:
        panel = self._panels_by_id.get(self.values[0])
        if panel is None:
            # Cas limite : le panel a été supprimé entre l'affichage du menu
            # et le clic (ex. supprimé depuis une autre interaction entretemps).
            await interaction.response.send_message(
                view=error_container("Ce panel n'existe plus (déjà supprimé ?)."),
                ephemeral=True,
            )
            return
        await self._on_pick(interaction, panel)
