"""
views/dev/db_explorer_view.py — Interface de /dev database.

Deux écrans :
- DBTableListView  : liste paginée (25 max/page — limite Discord d'un select)
                     de toutes les tables connues du code (Base.metadata).
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
    format_value,
    get_table,
    list_indexed_columns,
    list_table_names,
)
from views._components.base_view import BaseLayoutView

TABLES_PER_PAGE = 25  # limite Discord pour les options d'un select
MAX_COLUMNS_SHOWN_PER_ROW = 25  # garde-fou d'affichage pour les tables très larges


# ============================================================
# 🗂️ Écran 1 : liste des tables
# ============================================================

class DBTableListView(BaseLayoutView):
    """Liste paginée des tables, sélectionnables via un menu déroulant."""

    def __init__(self, *, owner_id: int, page: int = 0):
        super().__init__(owner_id=owner_id, timeout=180)
        self.page = page
        self._select: Select | None = None
        self._build()

    def _build(self) -> None:
        self.clear_items()

        names = list_table_names()
        total_pages = max(1, math.ceil(len(names) / TABLES_PER_PAGE))
        self.page = max(0, min(self.page, total_pages - 1))
        start = self.page * TABLES_PER_PAGE
        current = names[start:start + TABLES_PER_PAGE]

        c = Container()
        c.add_item(TextDisplay("# 🗄️ Explorateur BDD"))
        c.add_item(TextDisplay("-# Lecture seule — aucune écriture possible depuis cette interface."))
        c.add_item(Separator())
        c.add_item(TextDisplay(f"**{len(names)} table(s)** enregistrée(s) dans le code — choisis-en une :"))

        select = Select(
            placeholder=f"Choisir une table (page {self.page + 1}/{total_pages})",
            options=[discord.SelectOption(label=name) for name in current] or [
                discord.SelectOption(label="—", value="—")
            ],
        )
        select.callback = self._on_select_table
        self._select = select
        c.add_item(ActionRow(select))

        btn_prev = Button(emoji="◀️", style=ButtonStyle.secondary, disabled=(self.page <= 0))
        btn_next = Button(emoji="▶️", style=ButtonStyle.secondary, disabled=(self.page >= total_pages - 1))
        btn_prev.callback = self._on_prev
        btn_next.callback = self._on_next
        c.add_item(ActionRow(btn_prev, btn_next))

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

    async def _on_select_table(self, interaction: discord.Interaction) -> None:
        table_name = self._select.values[0]
        detail_view = DBTableDetailView(owner_id=self.owner_id, table_name=table_name, list_page=self.page)
        await detail_view.load()
        await self.push_update(interaction, view=detail_view)


# ============================================================
# 🔍 Écran 2 : détail d'une table
# ============================================================

class DBTableDetailView(BaseLayoutView):
    """Colonnes/indices d'une table + aperçu ou résultat de recherche."""

    def __init__(self, *, owner_id: int, table_name: str, list_page: int = 0):
        super().__init__(owner_id=owner_id, timeout=180)
        self.table_name = table_name
        self.list_page = list_page
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
        c.add_item(TextDisplay(f"# 🗄️ `{self.table_name}`"))
        if self.row_count is not None:
            c.add_item(TextDisplay(f"-# {self.row_count} ligne(s) au total"))
        c.add_item(Separator())

        if table is None:
            c.add_item(TextDisplay("⚠️ Cette table n'existe plus dans le code."))
        else:
            columns = describe_table(table)
            lines = []
            for col in columns[:MAX_COLUMNS_SHOWN_PER_ROW]:
                tags = []
                if col.primary_key:
                    tags.append("🔑 PK")
                elif col.unique:
                    tags.append("🔒 unique")
                tag_str = f" — {' , '.join(tags)}" if tags else ""
                lines.append(f"`{col.name}` _{col.type_str}_{tag_str}")
            c.add_item(TextDisplay("**Colonnes :**\n" + "\n".join(lines)))
            c.add_item(Separator())

            indexed = list_indexed_columns(table)
            hint = ", ".join(f"`{name}`" for name in indexed) if indexed else "_aucune colonne indexée détectée_"
            c.add_item(TextDisplay(
                f"**Indices suggérés pour une recherche :** {hint}\n"
                "-# La recherche fonctionne en réalité sur n'importe quelle colonne réelle de la table."
            ))
            c.add_item(Separator())

        if self.result_rows is not None:
            c.add_item(TextDisplay(self.result_title or "**Résultat :**"))
            if not self.result_rows:
                c.add_item(TextDisplay("*Aucune ligne trouvée.*"))
            else:
                for i, row in enumerate(self.result_rows, start=1):
                    formatted = "\n".join(f"`{k}` : {format_value(v)}" for k, v in row.items())
                    c.add_item(TextDisplay(f"**Ligne {i}**\n{formatted}"))
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
        self.result_title = f"**Aperçu — {len(rows)} ligne(s) (max 10) :**"
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
        self.result_title = f"**Recherche `{column}` = `{value}`** — {len(rows)} ligne(s) (max 10) :"
        self._build()
        await interaction.response.edit_message(view=self)

    async def _on_back(self, interaction: discord.Interaction) -> None:
        list_view = DBTableListView(owner_id=self.owner_id, page=self.list_page)
        await self.push_update(interaction, view=list_view)


# ============================================================
# 📝 Modal de recherche
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