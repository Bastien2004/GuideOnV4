"""
views/dev/db_explorer_view.py — Interface de /dev database.

Deux écrans :
- DBTableListView  : liste paginée (25 max/page — limite Discord d'un select)
                     de toutes les tables connues du code (Base.metadata),
                     avec un bouton "Rechercher une table" (modal texte) car
                     le select Discord ne permet pas de taper pour filtrer,
                     et 71+ tables ne tiennent pas sur une seule page.
- DBTableDetailView : colonnes + indices d'une table, avec aperçu (10
                      premières lignes) ou recherche par colonne/valeur
                      (modal), résultat affiché directement dans la vue.

Lecture seule de bout en bout — aucun bouton ni callback ici n'écrit quoi
que ce soit en base (voir utils/db/introspect.py).
"""
from __future__ import annotations

import math

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Modal, Select, Separator, TextDisplay, TextInput

from utils.container_universel import error_container, send_ephemeral
from utils.db.introspect import (
    ColumnNotFoundError,
    InvalidSearchValueError,
    count_rows,
    describe_table,
    fetch_by_column,
    fetch_preview,
    format_value_plain,
    get_table,
    list_indexed_columns,
    list_table_names,
)
from views._components.base_view import BaseLayoutView

TABLES_PER_PAGE = 25  # limite Discord pour les options d'un select
MAX_COLUMNS_SHOWN_PER_ROW = 25  # garde-fou d'affichage pour les tables très larges
TABLE_CELL_MAX_WIDTH = 18  # colonnes/types (courts) dans le tableau "Colonnes"
RESULT_CELL_MAX_WIDTH = 25  # valeurs de résultat — assez large pour ne jamais tronquer un ID Discord (≤ 20 chiffres)


def _render_ascii_table(headers: list[str], rows: list[list[str]], *, max_col_width: int = TABLE_CELL_MAX_WIDTH) -> str:
    """
    Rendu compact en tableau monospace (bloc de code Discord), plutôt qu'une
    ligne `clé` : `valeur` par colonne — bien plus lisible dès qu'il y a
    plusieurs colonnes ou plusieurs lignes de résultat.
    """
    widths = []
    for i, header in enumerate(headers):
        col_values = [header] + [r[i] for r in rows]
        widths.append(min(max((len(v) for v in col_values), default=0), max_col_width))

    def fmt_row(values: list[str]) -> str:
        cells = []
        for value, width in zip(values, widths):
            cell = value if len(value) <= width else value[: max(0, width - 1)] + "…"
            cells.append(cell.ljust(width))
        return " │ ".join(cells)

    separator = "─┼─".join("─" * w for w in widths)
    lines = [fmt_row(headers), separator] + [fmt_row(r) for r in rows]
    return "```\n" + "\n".join(lines) + "\n```"


def _column_tag(col) -> str:
    if col.primary_key:
        return "PK"
    if col.unique:
        return "unique"
    if col.foreign_key:
        return "FK"
    return ""


# ============================================================
# 🗂️ Écran 1 : liste des tables
# ============================================================

class DBTableListView(BaseLayoutView):
    """
    Liste paginée des tables (mode navigation), ou liste filtrée par nom
    (mode recherche, activé via le bouton "Rechercher une table" — un select
    Discord ne permet pas de taper pour filtrer, d'où le passage par un modal
    texte plutôt que de compter sur la pagination pour trouver une table).
    """

    def __init__(self, *, owner_id: int, page: int = 0, filter_query: str | None = None):
        super().__init__(owner_id=owner_id, timeout=180)
        self.page = page
        self.filter_query = filter_query or None
        self._select: Select | None = None
        self._build()

    def _matching_names(self) -> list[str]:
        names = list_table_names()
        if not self.filter_query:
            return names
        needle = self.filter_query.lower()
        return [n for n in names if needle in n.lower()]

    def _build(self) -> None:
        self.clear_items()

        all_count = len(list_table_names())
        names = self._matching_names()
        total_pages = max(1, math.ceil(len(names) / TABLES_PER_PAGE))
        self.page = max(0, min(self.page, total_pages - 1))
        start = self.page * TABLES_PER_PAGE
        current = names[start:start + TABLES_PER_PAGE]

        c = Container()
        c.add_item(TextDisplay("# 🗄️ Explorateur BDD"))
        c.add_item(TextDisplay("-# Lecture seule — aucune écriture possible depuis cette interface."))
        c.add_item(Separator())

        if self.filter_query:
            c.add_item(TextDisplay(
                f"**Recherche `{self.filter_query}`** — {len(names)}/{all_count} table(s) correspondante(s)."
            ))
        else:
            c.add_item(TextDisplay(f"**{all_count} table(s)** enregistrée(s) dans le code — choisis-en une :"))

        if names:
            select = Select(
                placeholder=f"Choisir une table (page {self.page + 1}/{total_pages})",
                options=[discord.SelectOption(label=name) for name in current],
            )
            select.callback = self._on_select_table
            self._select = select
            c.add_item(ActionRow(select))
        else:
            c.add_item(TextDisplay("*Aucune table ne correspond à cette recherche.*"))
            self._select = None

        btn_prev = Button(emoji="◀️", style=ButtonStyle.secondary, disabled=(self.page <= 0))
        btn_next = Button(emoji="▶️", style=ButtonStyle.secondary, disabled=(self.page >= total_pages - 1))
        btn_prev.callback = self._on_prev
        btn_next.callback = self._on_next
        c.add_item(ActionRow(btn_prev, btn_next))

        btn_search = Button(label="Rechercher une table", style=ButtonStyle.primary, emoji="🔍")
        btn_search.callback = self._on_open_search
        buttons = [btn_search]
        if self.filter_query:
            btn_clear = Button(label="Effacer la recherche", style=ButtonStyle.secondary, emoji="✖️")
            btn_clear.callback = self._on_clear_search
            buttons.append(btn_clear)
        c.add_item(ActionRow(*buttons))

        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(c)

    async def _on_prev(self, interaction: discord.Interaction) -> None:
        self.page -= 1
        self._build()
        await self.push_update(interaction)

    async def _on_next(self, interaction: discord.Interaction) -> None:
        self.page += 1
        self._build()
        await self.push_update(interaction)

    async def _on_open_search(self, interaction: discord.Interaction) -> None:
        modal = DBTableSearchModal(on_submit=self._on_search_submit)
        await interaction.response.send_modal(modal)

    async def _on_search_submit(self, interaction: discord.Interaction, query: str) -> None:
        query = query.strip()
        if not query:
            await self._on_clear_search(interaction)
            return

        matches = self._matching_names_for(query)
        if len(matches) == 1:
            # Un seul résultat : on va directement au détail, pas la peine
            # de repasser par un select à une seule option.
            detail_view = DBTableDetailView(owner_id=self.owner_id, table_name=matches[0], list_page=0, filter_query=query)
            await detail_view.load()
            await interaction.response.edit_message(view=detail_view)
            return

        self.filter_query = query
        self.page = 0
        self._build()
        await interaction.response.edit_message(view=self)

    async def _on_clear_search(self, interaction: discord.Interaction) -> None:
        self.filter_query = None
        self.page = 0
        self._build()
        await interaction.response.edit_message(view=self)

    def _matching_names_for(self, query: str) -> list[str]:
        needle = query.lower()
        return [n for n in list_table_names() if needle in n.lower()]

    async def _on_select_table(self, interaction: discord.Interaction) -> None:
        table_name = self._select.values[0]
        detail_view = DBTableDetailView(
            owner_id=self.owner_id, table_name=table_name, list_page=self.page, filter_query=self.filter_query
        )
        await detail_view.load()
        await self.push_update(interaction, view=detail_view)


# ============================================================
# 🔍 Écran 2 : détail d'une table
# ============================================================

class DBTableDetailView(BaseLayoutView):
    """Colonnes/indices d'une table + aperçu ou résultat de recherche."""

    def __init__(self, *, owner_id: int, table_name: str, list_page: int = 0, filter_query: str | None = None):
        super().__init__(owner_id=owner_id, timeout=180)
        self.table_name = table_name
        self.list_page = list_page
        self.filter_query = filter_query
        self.row_count: int | None = None
        self.result_rows: list[dict] | None = None
        self.result_title: str | None = None

    async def load(self) -> None:
        """Charge le nombre de lignes (appelé une fois avant le premier affichage)."""
        table = get_table(self.table_name)
        if table is not None:
            self.row_count = await count_rows(table)
        self._build()

    def _build(self) -> None:
        self.clear_items()
        table = get_table(self.table_name)

        c = Container()
        header = f"# 🗄️ `{self.table_name}`"
        if self.row_count is not None:
            header += f"\n-# {self.row_count} ligne(s) au total"
        c.add_item(TextDisplay(header))
        c.add_item(Separator())

        if table is None:
            c.add_item(TextDisplay("⚠️ Cette table n'existe plus dans le code."))
        else:
            columns = describe_table(table)[:MAX_COLUMNS_SHOWN_PER_ROW]
            col_table = _render_ascii_table(
                ["colonne", "type", "indice"],
                [[col.name, col.type_str, _column_tag(col)] for col in columns],
            )
            c.add_item(TextDisplay(f"## Colonnes\n{col_table}"))

            indexed = list_indexed_columns(table)
            if indexed:
                c.add_item(TextDisplay(
                    "-# Indices utilisables pour une recherche : " + ", ".join(f"`{n}`" for n in indexed)
                ))
            c.add_item(Separator())

        if self.result_rows is not None:
            c.add_item(TextDisplay(f"## {self.result_title or 'Résultat'}"))
            if not self.result_rows:
                c.add_item(TextDisplay("*Aucune ligne trouvée.*"))
            else:
                headers = list(self.result_rows[0].keys())
                rows = [[format_value_plain(row.get(h), max_len=60) for h in headers] for row in self.result_rows]
                c.add_item(TextDisplay(_render_ascii_table(headers, rows, max_col_width=RESULT_CELL_MAX_WIDTH)))
            c.add_item(Separator())

        btn_preview = Button(label="Aperçu (10 lignes)", style=ButtonStyle.secondary, emoji="📄")
        btn_search = Button(label="Rechercher", style=ButtonStyle.primary, emoji="🔍")
        btn_back = Button(label="Retour", style=ButtonStyle.secondary, emoji="<:retour:1515658955190308995>")
        btn_preview.callback = self._on_preview
        btn_search.callback = self._on_search
        btn_back.callback = self._on_back
        c.add_item(ActionRow(btn_preview, btn_search, btn_back))

        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(c)

    async def _on_preview(self, interaction: discord.Interaction) -> None:
        table = get_table(self.table_name)
        if table is None:
            await send_ephemeral(interaction, error_container("Cette table n'existe plus dans le code."))
            return
        rows = await fetch_preview(table)
        self.result_rows = rows
        self.result_title = f"Aperçu — {len(rows)} ligne(s) (max 10)"
        self._build()
        await self.push_update(interaction)

    async def _on_search(self, interaction: discord.Interaction) -> None:
        modal = DBSearchModal(on_submit=self._on_search_submit)
        await interaction.response.send_modal(modal)

    async def _on_search_submit(self, interaction: discord.Interaction, column: str, value: str) -> None:
        table = get_table(self.table_name)
        if table is None:
            await interaction.response.send_message(
                view=error_container("Cette table n'existe plus dans le code."), ephemeral=True
            )
            return

        try:
            rows = await fetch_by_column(table, column, value)
        except ColumnNotFoundError as e:
            await interaction.response.send_message(view=error_container(str(e)), ephemeral=True)
            return
        except InvalidSearchValueError as e:
            await interaction.response.send_message(view=error_container(str(e)), ephemeral=True)
            return

        self.result_rows = rows
        self.result_title = f"Recherche {column} = {value} — {len(rows)} ligne(s) (max 10)"
        self._build()
        await interaction.response.edit_message(view=self)

    async def _on_back(self, interaction: discord.Interaction) -> None:
        list_view = DBTableListView(owner_id=self.owner_id, page=self.list_page, filter_query=self.filter_query)
        await self.push_update(interaction, view=list_view)


# ============================================================
# 📝 Modal de recherche de table (menu de gauche, pallie l'absence de
# saisie texte dans un select Discord)
# ============================================================

class DBTableSearchModal(Modal):
    def __init__(self, *, on_submit) -> None:
        super().__init__(title="Rechercher une table")
        self._on_submit_cb = on_submit
        self.query_input = TextInput(
            label="Nom de la table (ou une partie)",
            placeholder="ex: ng_server, ticket, mod_sanction...",
            max_length=64,
        )
        self.add_item(self.query_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._on_submit_cb(interaction, self.query_input.value)


# ============================================================
# 📝 Modal de recherche (colonne / valeur, dans le détail d'une table)
# ============================================================

class DBSearchModal(Modal):
    def __init__(self, *, on_submit) -> None:
        super().__init__(title="Rechercher une ligne")
        self._on_submit_cb = on_submit
        self.column_input = TextInput(
            label="Colonne (indice)",
            placeholder="ex: guild_id, id, name, discord_guild_id...",
            max_length=64,
        )
        self.value_input = TextInput(
            label="Valeur recherchée",
            placeholder="ex: 123456789012345678",
            max_length=200,
        )
        self.add_item(self.column_input)
        self.add_item(self.value_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._on_submit_cb(
            interaction, self.column_input.value.strip(), self.value_input.value.strip()
        )