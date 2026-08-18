"""
views/dev/maintenance_view.py — Interface Components V2 de /dev maintenance :
activation/désactivation des commandes, recherche, pagination. Extraite de
cogs/dev/maintenance.py (le fichier original ne contenait déjà aucune
logique métier propre — get_all_commands/toggle_command vivent dans
utils.managers.command_toggle_manager — donc pas de nouveau utils/
maintenance.py : tout ce qui reste ici est construction d'interface +
câblage des callbacks, comme WikiHomeView/WikiCategoryView).
"""
from __future__ import annotations

import discord
from discord.ui import ActionRow, Button, Container, LayoutView, Modal, Section, Separator, TextDisplay, TextInput

from utils.managers.command_toggle_manager import delete_command, get_all_commands, toggle_command
from utils.perm_dev import check_dev

VIEW_TIMEOUT = 300
COMMANDS_PER_PAGE = 5
SEARCH_LIMIT = 5


# ============================================================
# 🧱 Ajout ligne commande
# ============================================================

async def add_command_section(
    container: Container,
    command_name: str,
    enabled: bool,
    page: int,
    search_query: str | None = None,
) -> None:
    """Ajoute la ligne d'une commande (statut + toggle + delete) au container."""

    status = "🟢" if enabled else "🔴"
    container.add_item(TextDisplay(f"{status} `{command_name}`"))

    # Bouton toggle ON/OFF
    toggle_btn = Button(
        label="ON" if enabled else "OFF",
        style=discord.ButtonStyle.success if enabled else discord.ButtonStyle.danger,
    )

    async def toggle_cb(interaction: discord.Interaction) -> None:
        if not await check_dev(interaction):
            return
        updated_data = await toggle_command(command_name)
        if search_query:
            results = {k: v for k, v in updated_data.items() if search_query.lower() in k.lower()}
            view = await create_search_result_view(search_query, results, page)
        else:
            view = await create_maintenance_view(updated_data, page)
        await interaction.response.edit_message(view=view)

    toggle_btn.callback = toggle_cb

    # Bouton delete (avec confirmation intégrée)
    delete_btn = Button(
        label="Supprimer", emoji="🗑️", style=discord.ButtonStyle.secondary,
    )

    async def delete_cb(interaction: discord.Interaction) -> None:
        if not await check_dev(interaction):
            return
        confirm_view = await create_delete_confirm_view(
            command_name, page, search_query=search_query,
        )
        await interaction.response.edit_message(view=confirm_view)

    delete_btn.callback = delete_cb

    container.add_item(ActionRow(toggle_btn, delete_btn))


# ============================================================
# 🛠️ Construction de l'interface
# ============================================================

async def create_maintenance_view(data: dict[str, bool], page: int = 0) -> LayoutView:
    """Création de l'interface principale."""

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
# 🗑️ Confirmation de suppression
# ============================================================

async def create_delete_confirm_view(
    command_name: str, origin_page: int, *, search_query: str | None = None,
) -> LayoutView:
    """
    Vue de confirmation intégrée (edit_message, pas de modal) avant
    suppression définitive d'une commande. Deux boutons : Confirmer / Annuler.
    Le retour se fait sur la vue d'origine (maintenance ou résultat de
    recherche selon d'où on vient).
    """
    view = LayoutView(timeout=VIEW_TIMEOUT)
    container = Container()

    container.add_item(TextDisplay("# 🗑️ Supprimer la commande ?"))
    container.add_item(Separator())
    container.add_item(TextDisplay(
        f"Tu vas supprimer définitivement la ligne `{command_name}` de la table "
        "`command_controls`.\n"
        "-# Cette action est **irréversible**. Une commande absente de la "
        "table est considérée comme **activée par défaut** — donc supprimer "
        "une commande obsolète est safe."
    ))
    container.add_item(Separator())

    # ✅ Confirmer
    btn_confirm = Button(label="Confirmer", emoji="✅", style=discord.ButtonStyle.danger)

    async def confirm_cb(interaction: discord.Interaction) -> None:
        if not await check_dev(interaction):
            return
        await delete_command(command_name)
        updated_data = await get_all_commands()
        if search_query:
            results = {
                k: v for k, v in updated_data.items()
                if search_query.lower() in k.lower()
            }
            new_view = await create_search_result_view(search_query, results, origin_page)
        else:
            new_view = await create_maintenance_view(updated_data, origin_page)
        await interaction.response.edit_message(view=new_view)

    btn_confirm.callback = confirm_cb

    # ↩️ Annuler
    btn_cancel = Button(label="Annuler", emoji="↩️", style=discord.ButtonStyle.secondary)

    async def cancel_cb(interaction: discord.Interaction) -> None:
        if not await check_dev(interaction):
            return
        if search_query:
            data = await get_all_commands()
            results = {k: v for k, v in data.items() if search_query.lower() in k.lower()}
            new_view = await create_search_result_view(search_query, results, origin_page)
        else:
            new_view = await create_maintenance_view(await get_all_commands(), origin_page)
        await interaction.response.edit_message(view=new_view)

    btn_cancel.callback = cancel_cb

    container.add_item(ActionRow(btn_confirm, btn_cancel))
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