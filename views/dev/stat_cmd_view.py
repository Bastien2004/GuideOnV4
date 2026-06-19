"""
views/dev/stat_cmd_view.py — Dashboard de statistiques d'usage des commandes.

Trois blocs : podium (top 3 all-time), graphique d'évolution (usage total
quotidien sur une fenêtre glissante), liste paginée (tous les totaux).
"""
from __future__ import annotations

import io

import discord
import matplotlib.pyplot as plt
from discord import ButtonStyle, Interaction, MediaGalleryItem
from discord.ui import ActionRow, Button, Container, LayoutView, MediaGallery, Separator, TextDisplay

from utils.managers.command_stats_manager import get_daily_series, get_grand_total, get_podium, get_totals_by_command

COMMANDS_PER_PAGE = 15
GRAPH_BG = "#23272a"
GRAPH_LINE = "#5865F2"

_WINDOW_CHOICES = [7, 30, 90]
_MEDALS = ["🥇", "🥈", "🥉"]


class _StatCmdView(LayoutView):
    """LayoutView avec restriction au propriétaire de la commande d'origine."""

    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Seul l'auteur de la commande peut utiliser ce menu.", ephemeral=True
            )
            return False
        return True


# ============================================================
# 📊 Génération du graphique
# ============================================================

def _generate_graph(series: list[dict], days: int) -> discord.File:
    """Courbe d'évolution de l'usage total (toutes commandes) sur `days` jours."""
    dates = [p["date"] for p in series]
    totals = [p["total"] for p in series]

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(dates, totals, color=GRAPH_LINE, linewidth=2.2, marker="o", markersize=4)
    ax.fill_between(dates, totals, color=GRAPH_LINE, alpha=0.15)

    fig.patch.set_facecolor(GRAPH_BG)
    ax.set_facecolor(GRAPH_BG)
    ax.tick_params(colors="white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("white")
    ax.spines["bottom"].set_color("white")
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", color="white", alpha=0.1)

    # Limite le nombre de labels affichés sur l'axe X pour rester lisible
    # même sur une fenêtre de 90 jours.
    step = max(1, len(dates) // 10)
    ax.set_xticks(dates[::step])
    ax.set_xticklabels(
        [d.strftime("%d/%m") for d in dates[::step]],
        rotation=45, color="white", fontsize=8,
    )

    fig.suptitle(f"Usage total des commandes — {days} derniers jours", color="white", fontsize=12)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)

    return discord.File(buf, filename="stat_cmd_graph.png")


# ============================================================
# 🧩 Construction de la vue principale
# ============================================================

async def build_stat_cmd_view(
    owner_id: int,
    *,
    window_days: int = 7,
    page: int = 0,
) -> tuple[LayoutView, discord.File]:
    """Construit le dashboard complet (podium + graphique + liste paginée)."""

    totals = await get_totals_by_command()
    podium = totals[:3]
    grand_total = await get_grand_total()
    series = await get_daily_series(window_days)
    graph_file = _generate_graph(series, window_days)

    total_pages = max(1, (len(totals) + COMMANDS_PER_PAGE - 1) // COMMANDS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * COMMANDS_PER_PAGE
    current_page_items = totals[start : start + COMMANDS_PER_PAGE]

    view = _StatCmdView(owner_id)

    # ── Header + podium ───────────────────────────────────────
    c_header = Container()
    c_header.add_item(TextDisplay("# 📊 Statistiques de commandes"))
    c_header.add_item(Separator())
    c_header.add_item(TextDisplay(f"**Total d'utilisations (toutes commandes) :** `{grand_total}`"))
    c_header.add_item(Separator())

    if not podium:
        c_header.add_item(TextDisplay("*Aucune commande utilisée pour l'instant.*"))
    else:
        lines = []
        for i, entry in enumerate(podium):
            medal = _MEDALS[i] if i < len(_MEDALS) else "•"
            lines.append(f"{medal} **{entry['command_name']}** — `{entry['total']}` utilisations")
        c_header.add_item(TextDisplay("## 🏆 Podium\n" + "\n".join(lines)))
    view.add_item(c_header)

    # ── Graphique ──────────────────────────────────────────────
    c_graph = Container()
    c_graph.add_item(TextDisplay(f"## 📈 Évolution — {window_days} derniers jours"))
    c_graph.add_item(Separator())
    c_graph.add_item(MediaGallery(MediaGalleryItem("attachment://stat_cmd_graph.png")))
    c_graph.add_item(Separator())

    window_buttons = []
    for w in _WINDOW_CHOICES:
        btn = Button(
            label=f"{w}j",
            style=ButtonStyle.primary if w == window_days else ButtonStyle.secondary,
            custom_id=f"stat_cmd_window_{w}",
        )

        async def _on_window(interaction: Interaction, w=w) -> None:
            new_view, new_file = await build_stat_cmd_view(owner_id, window_days=w, page=0)
            await interaction.response.edit_message(view=new_view, attachments=[new_file])

        btn.callback = _on_window
        window_buttons.append(btn)
    c_graph.add_item(ActionRow(*window_buttons))
    view.add_item(c_graph)

    # ── Liste paginée ──────────────────────────────────────────
    c_list = Container()
    c_list.add_item(TextDisplay("## 🗂️ Détail par commande"))
    c_list.add_item(Separator())

    if not current_page_items:
        c_list.add_item(TextDisplay("*Aucune donnée.*"))
    else:
        rank_offset = start
        lines = [
            f"`{rank_offset + i + 1:>2}.` **{entry['command_name']}** — `{entry['total']}`"
            for i, entry in enumerate(current_page_items)
        ]
        c_list.add_item(TextDisplay("\n".join(lines)))

    c_list.add_item(Separator())
    c_list.add_item(TextDisplay(f"-# Page {page + 1} / {total_pages}"))

    btn_prev = Button(emoji="◀️", style=ButtonStyle.secondary, custom_id="stat_cmd_prev", disabled=(page <= 0))
    btn_next = Button(emoji="▶️", style=ButtonStyle.secondary, custom_id="stat_cmd_next", disabled=(page >= total_pages - 1))

    async def _on_prev(interaction: Interaction) -> None:
        new_view, new_file = await build_stat_cmd_view(owner_id, window_days=window_days, page=page - 1)
        await interaction.response.edit_message(view=new_view, attachments=[new_file])

    async def _on_next(interaction: Interaction) -> None:
        new_view, new_file = await build_stat_cmd_view(owner_id, window_days=window_days, page=page + 1)
        await interaction.response.edit_message(view=new_view, attachments=[new_file])

    btn_prev.callback = _on_prev
    btn_next.callback = _on_next
    c_list.add_item(ActionRow(btn_prev, btn_next))
    c_list.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c_list)

    return view, graph_file