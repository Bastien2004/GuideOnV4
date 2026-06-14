"""
Commande /dev maintenance — Gère le système de maintenance commande.
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction
from discord.ui import LayoutView, Container, TextDisplay, Separator, ActionRow, Button, Modal, TextInput, Section

from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.perm_dev import check_dev

from utils.managers.command_toggle_manager import get_all_commands, toggle_command


# ============================================================
# 📦 Constantes
# ============================================================

VIEW_TIMEOUT = 300
COMMANDS_PER_PAGE = 5
SEARCH_LIMIT = 5


# ============================================================
# 🧱 Ajout ligne commande
# ============================================================

async def add_command_section(container: Container, command_name: str, enabled: bool, page: int, search_query: str | None = None) -> None:
    """Ajoute la section des commandes sur l'interface de gestion des maintenances."""

    button = Button(
        label="ON" if enabled else "OFF",
        style=discord.ButtonStyle.success if enabled else discord.ButtonStyle.danger,
    )

    async def callback(interaction: discord.Interaction) -> None:
        if not await check_dev(interaction):
            return

        updated_data = await toggle_command(command_name)

        if search_query:
            results = {k: v for k, v in updated_data.items() if search_query.lower() in k.lower()}
            view = await create_search_result_view(search_query, results, page)
        else:
            view = await create_maintenance_view(updated_data, page)

        await interaction.response.edit_message(view=view)

    button.callback = callback

    status = "🟢" if enabled else "🔴"
    container.add_item(Section(TextDisplay(f"{status} `{command_name}`"), accessory=button))


# ============================================================
# 🛠️ Construction de l'interface
# ============================================================

async def create_maintenance_view(data: dict[str, bool], page: int = 0) -> LayoutView:
    """Création de l'interface principal."""

    view = LayoutView(timeout=VIEW_TIMEOUT)
    container = Container()

    items = sorted(data.items())
    total = len(items)
    total_pages = max(1, (total + COMMANDS_PER_PAGE - 1) // COMMANDS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))

    start = page * COMMANDS_PER_PAGE
    current_slice = items[start : start + COMMANDS_PER_PAGE]

    enabled_count = sum(1 for _, v in items if v)
    disabled_count = total - enabled_count

    container.add_item(TextDisplay("# 🛠️ Maintenance"))
    container.add_item(TextDisplay(
        f"-# {total} commandes — "
        f"🟢 {enabled_count} actives · "
        f"🔴 {disabled_count} désactivées"
    ))
    container.add_item(Separator())

    if not current_slice:
        container.add_item(TextDisplay("*Aucune commande enregistrée.*"))
    else:
        for command_name, enabled in current_slice:
            await add_command_section(container, command_name, enabled, page)

    container.add_item(Separator())
    container.add_item(TextDisplay(f"-# Page {page + 1} / {total_pages}"))

    # ◀️ Précédent
    btn_prev = Button(emoji="<:precedent:1515658763913138236>", style=discord.ButtonStyle.secondary, disabled=(page <= 0))

    async def prev_callback(interaction: discord.Interaction) -> None:
        if not await check_dev(interaction):
            return
        view = await create_maintenance_view(await get_all_commands(), page - 1)
        await interaction.response.edit_message(view=view)

    btn_prev.callback = prev_callback

    # ▶️ Suivant
    btn_next = Button(emoji="<:suivant:1515658825913339904>", style=discord.ButtonStyle.secondary, disabled=(page >= total_pages - 1))

    async def next_callback(interaction: discord.Interaction) -> None:
        if not await check_dev(interaction):
            return
        view = await create_maintenance_view(await get_all_commands(), page + 1)
        await interaction.response.edit_message(view=view)

    btn_next.callback = next_callback

    # 🔍 Recherche
    btn_search = Button(label="Rechercher", emoji="<:recherche:1515659396712104006>", style=discord.ButtonStyle.primary)

    async def search_callback(interaction: discord.Interaction) -> None:
        if not await check_dev(interaction):
            return
        await interaction.response.send_modal(SearchCommandModal(page))

    btn_search.callback = search_callback

    container.add_item(ActionRow(btn_prev, btn_search, btn_next))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 🔍 Construction affichage des recherches
# ============================================================

async def create_search_result_view(query: str, results: dict[str, bool], origin_page: int) -> LayoutView:
    """Construction interface d'affichage des recherches."""

    view = LayoutView(timeout=VIEW_TIMEOUT)
    container = Container()

    container.add_item(TextDisplay(f"# 🔍 Résultats — `{query}`"))
    container.add_item(TextDisplay(f"-# {len(results)} commande(s) trouvée(s)"))
    container.add_item(Separator())

    if not results:
        container.add_item(TextDisplay("*Aucune commande trouvée.*"))
    else:
        for command_name, enabled in list(sorted(results.items()))[:SEARCH_LIMIT]:
            await add_command_section(container, command_name, enabled, origin_page, query)

    container.add_item(Separator())

    btn_back = Button(label="Retour", emoji="<:retour:1515658955190308995>", style=discord.ButtonStyle.secondary)

    async def back_callback(interaction: discord.Interaction) -> None:
        if not await check_dev(interaction):
            return
        view = await create_maintenance_view(await get_all_commands(), origin_page)
        await interaction.response.edit_message(view=view)

    btn_back.callback = back_callback

    container.add_item(ActionRow(btn_back))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 🔍 Modal recherche
# ============================================================

class SearchCommandModal(Modal):
    def __init__(self, origin_page: int = 0) -> None:
        super().__init__(title="🔍 Rechercher une commande")
        self.origin_page = origin_page
        self.query = TextInput(
            label="Commande",
            placeholder="ticket, dev, config ...",
            required=True,
            max_length=60,
        )
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not await check_dev(interaction):
            return

        query = self.query.value.strip()
        data = await get_all_commands()
        results = {k: v for k, v in data.items() if query.lower() in k.lower()}
        view = await create_search_result_view(query, results, self.origin_page)
        await interaction.response.edit_message(view=view)


# ============================================================
# 🧭 Commande : /dev maintenance
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="maintenance", description="🛠️ [DEV] Gérer les commandes du bot")
async def maintenance(interaction: Interaction) -> None:

    # 🔐 Vérification des permissions.
    if not await check_dev(interaction, "gérer la maintenance du bot"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "dev_maintenance"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_maintenance")

    # 📋 Récupération des données.
    try:
        data = await get_all_commands()
        view = await create_maintenance_view(data)

    except Exception:
        return await interaction.followup.send(
            view=error_container("Impossible de charger l'**interface de maintenance**."),
            ephemeral=True,
        )

    # ✉️ Envoi de l'interface
    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@maintenance.error
async def maintenance_error(interaction: Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)