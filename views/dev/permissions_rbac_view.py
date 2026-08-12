"""
views/dev/permissions_rbac_view.py — Dashboard RBAC de /dev permissions
(refonte multi-serveurs, phase 4 — remplace l'ancien dashboard flat de
utils.managers.permission_manager / PermissionRole).

Navigation à 3 niveaux (§10 du prompt de refonte) :
    CategoryListView  -> GradeListView (par catégorie) -> GradeDetailView (par grade)

Toutes les views sont construites via des fonctions `build_*_view(...)`
plutôt que des classes stateful : cohérent avec le pattern déjà utilisé par
views/exp/gestion_view.py (rebuild complet + `push_update`), plus simple à
suivre pour une UI à état largement dérivé de la DB (pas de state local
persistant nécessaire entre deux clics).

Permissions : la vérification `equipe_guideon.dev` (+ garde-fou créateur) a
lieu une seule fois, dans cogs/dev/permissions_rbac.py, à l'ouverture de la
commande. Les clics suivants sont restreints au même auteur via
`BaseLayoutView.owner_id` (voir views/_components/base_view.py) — pas de
re-check de grade sur chaque bouton, comme pour views/exp/gestion_view.py.
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, Interaction, SelectOption
from discord.ui import ActionRow, Button, Container, Select, Separator, TextDisplay

from utils.container_universel import error_container, success_container
from utils.managers import permission_rbac_manager as rbac
from views._components.back_button import BackButton
from views._components.base_view import BaseLayoutView
from views._components.confirm_view import ConfirmView
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

VIEW_TIMEOUT = 300
MAX_PER_ROW = 5
MAX_ROWS = 5
MAX_GRID_ITEMS = MAX_PER_ROW * MAX_ROWS  # 25 — limite Discord (5 ActionRow x 5 boutons)


# ============================================================
# 🧱 Utilitaires de mise en page
# ============================================================

def _rows_of_buttons(buttons: list[Button]) -> list[ActionRow]:
    return [
        ActionRow(*buttons[i : i + MAX_PER_ROW])
        for i in range(0, len(buttons), MAX_PER_ROW)
    ]


async def _full_slug(grade: rbac.PermissionGrade) -> str:
    category = await rbac.get_category(grade.category_id)
    cat_slug = category.slug if category is not None else "?"
    return f"{cat_slug}.{grade.slug}"


def _footer(container: Container) -> None:
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))


# ============================================================
# 🧱 Niveau 1 — Liste des catégories
# ============================================================

async def build_category_list_view(bot, author_id: int) -> BaseLayoutView:
    categories = await rbac.list_categories()

    view = BaseLayoutView(owner_id=author_id, timeout=VIEW_TIMEOUT)
    container = Container()

    container.add_item(TextDisplay("# <:erreur_cad:1495446243957018684> Permissions du bot"))
    container.add_item(TextDisplay(f"-# {len(categories)} catégorie(s)"))
    container.add_item(Separator())

    buttons: list[Button] = []
    for cat in categories[: MAX_GRID_ITEMS - 1]:
        btn = Button(label=cat.display_name, style=ButtonStyle.secondary)
        btn.callback = _cb_open_category(bot, author_id, cat.id)
        buttons.append(btn)

    if len(categories) > MAX_GRID_ITEMS - 1:
        container.add_item(
            TextDisplay(f"-# ⚠️ {len(categories) - (MAX_GRID_ITEMS - 1)} catégorie(s) non affichée(s) (limite d'interface)")
        )

    new_btn = Button(label="Nouvelle catégorie", emoji="<:plus:1495444111505752154>", style=ButtonStyle.success)
    new_btn.callback = _cb_new_category(bot, author_id)
    buttons.append(new_btn)

    for row in _rows_of_buttons(buttons):
        container.add_item(row)

    _footer(container)
    view.add_item(container)
    return view


def _cb_open_category(bot, author_id: int, category_id: int):
    async def cb(interaction: Interaction) -> None:
        new_view = await build_grade_list_view(bot, author_id, category_id)
        await new_view_or_error(interaction, new_view, "Cette catégorie n'existe plus.")
    return cb


def _cb_new_category(bot, author_id: int):
    async def on_submit(interaction: Interaction, display_name: str) -> None:
        display_name = display_name.strip()
        if not display_name:
            await interaction.response.send_message(
                view=error_container("Le nom ne peut pas être vide."), ephemeral=True
            )
            return
        slug = await rbac.unique_category_slug(display_name)
        category = await rbac.create_category(slug, display_name)
        new_view = await build_grade_list_view(bot, author_id, category.id)
        await interaction.response.edit_message(view=new_view)

    async def cb(interaction: Interaction) -> None:
        await interaction.response.send_modal(
            TextModal(
                title="Nouvelle catégorie",
                label="Nom affiché",
                placeholder="Ex: Staff Delta",
                max_length=128,
                on_submit=on_submit,
            )
        )
    return cb


# ============================================================
# 🧱 Niveau 2 — Grades d'une catégorie
# ============================================================

async def build_grade_list_view(bot, author_id: int, category_id: int) -> BaseLayoutView | None:
    category = await rbac.get_category(category_id)
    if category is None:
        return None

    grades = await rbac.list_grades(category_id)

    view = BaseLayoutView(owner_id=author_id, timeout=VIEW_TIMEOUT)
    container = Container()

    container.add_item(TextDisplay(f"# ⚔️ {category.display_name}"))
    container.add_item(TextDisplay(f"-# {len(grades)} grade(s) · `{category.slug}`"))
    container.add_item(Separator())

    buttons: list[Button] = []
    for grade in grades[: MAX_GRID_ITEMS - 1]:
        btn = Button(label=grade.display_name, style=ButtonStyle.secondary)
        btn.callback = _cb_open_grade(bot, author_id, grade.id)
        buttons.append(btn)

    if len(grades) > MAX_GRID_ITEMS - 1:
        container.add_item(
            TextDisplay(f"-# ⚠️ {len(grades) - (MAX_GRID_ITEMS - 1)} grade(s) non affiché(s) (limite d'interface)")
        )

    new_btn = Button(label="Nouveau grade", emoji="<:plus:1495444111505752154>", style=ButtonStyle.success)
    new_btn.callback = _cb_new_grade(bot, author_id, category_id)
    buttons.append(new_btn)

    for row in _rows_of_buttons(buttons):
        container.add_item(row)

    container.add_item(Separator())

    back_btn = BackButton(on_back=_cb_back_to_categories(bot, author_id))
    delete_btn = Button(
        label="Supprimer la catégorie", emoji="<:moins:1508532114465882285>", style=ButtonStyle.danger
    )
    delete_btn.callback = _cb_delete_category(bot, author_id, category_id)
    container.add_item(ActionRow(back_btn, delete_btn))

    _footer(container)
    view.add_item(container)
    return view


def _cb_back_to_categories(bot, author_id: int):
    async def cb(interaction: Interaction) -> None:
        new_view = await build_category_list_view(bot, author_id)
        await interaction.response.edit_message(view=new_view)
    return cb


def _cb_open_grade(bot, author_id: int, grade_id: int):
    async def cb(interaction: Interaction) -> None:
        new_view = await build_grade_detail_view(bot, author_id, grade_id)
        await new_view_or_error(interaction, new_view, "Ce grade n'existe plus.")
    return cb


def _cb_new_grade(bot, author_id: int, category_id: int):
    async def on_submit(interaction: Interaction, display_name: str) -> None:
        display_name = display_name.strip()
        if not display_name:
            await interaction.response.send_message(
                view=error_container("Le nom ne peut pas être vide."), ephemeral=True
            )
            return
        slug = await rbac.unique_grade_slug(category_id, display_name)
        grade = await rbac.create_grade(category_id, slug, display_name)
        new_view = await build_grade_detail_view(bot, author_id, grade.id)
        await interaction.response.edit_message(view=new_view)

    async def cb(interaction: Interaction) -> None:
        await interaction.response.send_modal(
            TextModal(
                title="Nouveau grade",
                label="Nom affiché",
                placeholder="Ex: Modérateur",
                max_length=128,
                on_submit=on_submit,
            )
        )
    return cb


def _cb_delete_category(bot, author_id: int, category_id: int):
    async def cb(interaction: Interaction) -> None:
        category = await rbac.get_category(category_id)
        name = category.display_name if category else "cette catégorie"
        confirm = ConfirmView(
            owner_id=author_id,
            question=f"Supprimer la catégorie **{name}** et tous ses grades / membres / inclusions ?",
            confirm_label="Supprimer",
            confirm_style=ButtonStyle.danger,
        )
        await interaction.response.send_message(view=confirm, ephemeral=True)
        await confirm.wait()
        if not confirm.confirmed:
            return

        await rbac.delete_category(category_id)
        new_view = await build_category_list_view(bot, author_id)
        try:
            await interaction.edit_original_response(view=new_view)
        except (discord.NotFound, discord.HTTPException):
            log.warning("[DEV PERMISSIONS] Impossible de rafraîchir après suppression catégorie")
    return cb


# ============================================================
# 🧱 Niveau 3 — Détail d'un grade
# ============================================================

async def build_grade_detail_view(bot, author_id: int, grade_id: int) -> BaseLayoutView | None:
    grade = await rbac.get_grade(grade_id)
    if grade is None:
        return None
    category = await rbac.get_category(grade.category_id)
    if category is None:
        return None

    members = await rbac.list_members(grade_id)
    children = await rbac.list_children(grade_id)
    parents = await rbac.list_parents(grade_id)

    view = BaseLayoutView(owner_id=author_id, timeout=VIEW_TIMEOUT)
    container = Container()

    container.add_item(TextDisplay(f"# Grade : {grade.display_name} (`{category.slug}.{grade.slug}`)"))
    container.add_item(Separator())

    # ── Membres directs ─────────────────────────────────────
    if members:
        shown = members[:30]
        member_lines = "\n".join(f"• <@{m}>" for m in shown)
        if len(members) > 30:
            member_lines += f"\n-# … et {len(members) - 30} de plus"
    else:
        member_lines = "-# *aucun membre*"
    container.add_item(TextDisplay(f"## 👥 Membres directs ({len(members)})\n{member_lines}"))

    add_member_btn = Button(label="Ajouter un membre", emoji="<:plus:1495444111505752154>", style=ButtonStyle.success)
    add_member_btn.callback = _cb_add_member(bot, author_id, grade_id)
    remove_member_btn = Button(
        label="Retirer un membre", emoji="<:moins:1508532114465882285>",
        style=ButtonStyle.danger, disabled=not members,
    )
    remove_member_btn.callback = _cb_remove_member(bot, author_id, grade_id)
    container.add_item(ActionRow(add_member_btn, remove_member_btn))
    container.add_item(Separator())

    # ── Grades inclus (enfants) ─────────────────────────────
    if children:
        child_slugs = [await _full_slug(c) for c in children]
        children_lines = "\n".join(f"• `{s}`" for s in child_slugs)
    else:
        children_lines = "-# *aucun*"
    container.add_item(TextDisplay(f"## 🔗 Grades inclus ({len(children)})\n{children_lines}"))

    add_include_btn = Button(label="Ajouter une inclusion", emoji="<:plus:1495444111505752154>", style=ButtonStyle.success)
    add_include_btn.callback = _cb_add_include(bot, author_id, grade_id)
    remove_include_btn = Button(
        label="Retirer une inclusion", emoji="<:moins:1508532114465882285>",
        style=ButtonStyle.danger, disabled=not children,
    )
    remove_include_btn.callback = _cb_remove_include(bot, author_id, grade_id)
    container.add_item(ActionRow(add_include_btn, remove_include_btn))
    container.add_item(Separator())

    # ── Grade inclus par (parents, lecture seule) ───────────
    if parents:
        parent_slugs = [await _full_slug(p) for p in parents]
        parents_lines = "\n".join(f"• `{s}`" for s in parent_slugs)
    else:
        parents_lines = "-# *aucun*"
    container.add_item(TextDisplay(f"## 📥 Grade inclus par ({len(parents)})\n{parents_lines}"))
    container.add_item(Separator())

    back_btn = BackButton(on_back=_cb_back_to_grades(bot, author_id, category.id))
    delete_btn = Button(label="Supprimer le grade", emoji="<:moins:1508532114465882285>", style=ButtonStyle.danger)
    delete_btn.callback = _cb_delete_grade(bot, author_id, grade_id, category.id)
    container.add_item(ActionRow(back_btn, delete_btn))

    _footer(container)
    view.add_item(container)
    return view


def _cb_back_to_grades(bot, author_id: int, category_id: int):
    async def cb(interaction: Interaction) -> None:
        new_view = await build_grade_list_view(bot, author_id, category_id)
        await new_view_or_error(interaction, new_view, "Cette catégorie n'existe plus.")
    return cb


def _cb_delete_grade(bot, author_id: int, grade_id: int, category_id: int):
    async def cb(interaction: Interaction) -> None:
        grade = await rbac.get_grade(grade_id)
        name = grade.display_name if grade else "ce grade"
        confirm = ConfirmView(
            owner_id=author_id,
            question=f"Supprimer le grade **{name}** (membres et inclusions associés inclus) ?",
            confirm_label="Supprimer",
            confirm_style=ButtonStyle.danger,
        )
        await interaction.response.send_message(view=confirm, ephemeral=True)
        await confirm.wait()
        if not confirm.confirmed:
            return

        await rbac.delete_grade(grade_id)
        new_view = await build_grade_list_view(bot, author_id, category_id)
        try:
            await interaction.edit_original_response(view=new_view)
        except (discord.NotFound, discord.HTTPException):
            log.warning("[DEV PERMISSIONS] Impossible de rafraîchir après suppression grade")
    return cb


# ============================================================
# 👥 Gestion des membres (modal ID — cohérent avec l'ancien IdModal)
# ============================================================

class _MemberIdModal(discord.ui.Modal):
    def __init__(self, *, action: str, bot, author_id: int, grade_id: int) -> None:
        title = "Ajouter un membre" if action == "add" else "Retirer un membre"
        super().__init__(title=title)
        self.action = action
        self.bot = bot
        self.author_id = author_id
        self.grade_id = grade_id
        self.id_input = discord.ui.TextInput(
            label="ID Discord",
            placeholder="123456789012345678",
            required=True,
            min_length=15,
            max_length=25,
        )
        self.add_item(self.id_input)

    async def on_submit(self, interaction: Interaction) -> None:
        raw = self.id_input.value.strip()
        if not raw.isdigit():
            await interaction.response.send_message(
                view=error_container("L'ID doit être numérique."), ephemeral=True
            )
            return
        discord_id = int(raw)

        if self.action == "add":
            done = await rbac.add_member(self.grade_id, discord_id)
            txt = f"<@{discord_id}> ajouté." if done else f"<@{discord_id}> était déjà membre."
        else:
            done = await rbac.remove_member(self.grade_id, discord_id)
            txt = f"<@{discord_id}> retiré." if done else f"<@{discord_id}> n'était pas membre."

        new_view = await build_grade_detail_view(self.bot, self.author_id, self.grade_id)
        if new_view is None:
            await interaction.response.send_message(
                view=error_container("Ce grade n'existe plus."), ephemeral=True
            )
            return
        await interaction.response.edit_message(view=new_view)
        await interaction.followup.send(view=success_container(txt), ephemeral=True)


def _cb_add_member(bot, author_id: int, grade_id: int):
    async def cb(interaction: Interaction) -> None:
        await interaction.response.send_modal(
            _MemberIdModal(action="add", bot=bot, author_id=author_id, grade_id=grade_id)
        )
    return cb


def _cb_remove_member(bot, author_id: int, grade_id: int):
    async def cb(interaction: Interaction) -> None:
        await interaction.response.send_modal(
            _MemberIdModal(action="remove", bot=bot, author_id=author_id, grade_id=grade_id)
        )
    return cb


# ============================================================
# 🔗 Gestion des inclusions (Select dédié, cf §10 : "sauf soi-même et
# descendants" — filtré via rbac.can_include pour l'ajout, liste des
# enfants directs pour le retrait)
# ============================================================

class _GradeSelectView(BaseLayoutView):
    """View transitoire : un seul Select + un bouton Retour."""

    def __init__(
        self,
        *,
        owner_id: int,
        options: list[SelectOption],
        placeholder: str,
        on_choice,
        on_back,
    ) -> None:
        super().__init__(owner_id=owner_id, timeout=120)
        container = Container()
        container.add_item(TextDisplay(f"### {placeholder}"))
        container.add_item(Separator())

        select = Select(placeholder=placeholder, options=options, min_values=1, max_values=1)

        async def _on_select(interaction: Interaction) -> None:
            await on_choice(interaction, int(select.values[0]))

        select.callback = _on_select
        container.add_item(ActionRow(select))

        back_btn = BackButton(on_back=on_back)
        container.add_item(ActionRow(back_btn))
        self.add_item(container)


async def _build_add_include_options(grade_id: int) -> list[SelectOption]:
    all_grades = await rbac.list_all_grades_with_category()
    options: list[SelectOption] = []
    for g, cat in all_grades:
        if len(options) >= 25:
            break
        if not await rbac.can_include(grade_id, g.id):
            continue
        options.append(SelectOption(label=f"{cat.slug}.{g.slug}", description=g.display_name[:100], value=str(g.id)))
    return options


def _cb_add_include(bot, author_id: int, grade_id: int):
    async def cb(interaction: Interaction) -> None:
        options = await _build_add_include_options(grade_id)
        if not options:
            await interaction.response.send_message(
                view=error_container("Aucun grade disponible à inclure (tout créerait un cycle, ou tout est déjà inclus)."),
                ephemeral=True,
            )
            return

        async def on_choice(inner: Interaction, child_grade_id: int) -> None:
            added = await rbac.add_include(grade_id, child_grade_id)
            new_view = await build_grade_detail_view(bot, author_id, grade_id)
            await inner.response.edit_message(view=new_view)
            if not added:
                await inner.followup.send(
                    view=error_container("Inclusion refusée (cycle ou déjà existante)."), ephemeral=True
                )

        async def on_back(inner: Interaction) -> None:
            new_view = await build_grade_detail_view(bot, author_id, grade_id)
            await inner.response.edit_message(view=new_view)

        select_view = _GradeSelectView(
            owner_id=author_id,
            options=options,
            placeholder="Choisir le grade à inclure",
            on_choice=on_choice,
            on_back=on_back,
        )
        await interaction.response.edit_message(view=select_view)
    return cb


def _cb_remove_include(bot, author_id: int, grade_id: int):
    async def cb(interaction: Interaction) -> None:
        children = await rbac.list_children(grade_id)
        if not children:
            await interaction.response.send_message(
                view=error_container("Aucune inclusion à retirer."), ephemeral=True
            )
            return

        options = []
        for c in children[:25]:
            cat = await rbac.get_category(c.category_id)
            label = f"{cat.slug}.{c.slug}" if cat else c.slug
            options.append(SelectOption(label=label, description=c.display_name[:100], value=str(c.id)))

        async def on_choice(inner: Interaction, child_grade_id: int) -> None:
            await rbac.remove_include(grade_id, child_grade_id)
            new_view = await build_grade_detail_view(bot, author_id, grade_id)
            await inner.response.edit_message(view=new_view)

        async def on_back(inner: Interaction) -> None:
            new_view = await build_grade_detail_view(bot, author_id, grade_id)
            await inner.response.edit_message(view=new_view)

        select_view = _GradeSelectView(
            owner_id=author_id,
            options=options,
            placeholder="Choisir l'inclusion à retirer",
            on_choice=on_choice,
            on_back=on_back,
        )
        await interaction.response.edit_message(view=select_view)
    return cb


# ============================================================
# 🛟 Helper commun (grade/catégorie supprimé entre deux clics)
# ============================================================

async def new_view_or_error(interaction: Interaction, new_view: BaseLayoutView | None, error_msg: str) -> None:
    """Édite le message avec new_view, ou affiche error_msg si l'objet a été
    supprimé entre-temps (catégorie/grade supprimé par un autre onglet)."""
    if new_view is None:
        await interaction.response.send_message(view=error_container(error_msg), ephemeral=True)
        return
    await interaction.response.edit_message(view=new_view)
