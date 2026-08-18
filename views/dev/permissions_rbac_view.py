"""
views/dev/permissions_rbac_view.py — Dashboard RBAC de /dev permissions.

Refonte v2 : UX simplifiée, confirmations intégrées (edit_message), pas de
flashs, validation stricte des IDs Discord, terminologie non-technique.

Navigation à 3 niveaux :
    Accueil catégories
      └── Gérer catégorie (liste des grades)
            └── Gérer grade (membres directs + grades cumulés)

Toggle « Voir les slugs » propagé en paramètre entre toutes les vues pour
que l'état reste cohérent pendant la navigation.
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, Interaction, SelectOption
from discord.ui import (
    ActionRow,
    Button,
    Container,
    Section,
    Select,
    Separator,
    TextDisplay,
)

from utils.container_universel import error_container, warning_container
from utils.managers import permission_rbac_manager as rbac
from views._components.base_view import BaseLayoutView
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

VIEW_TIMEOUT = 300

# Bornes actuelles d'un snowflake Discord (2016 → 2026+). Un ID sorti de
# Discord fait 17 à 19 chiffres — tout ce qui sort de cette plage est
# forcément invalide, on refuse avant même d'aller taper la DB.
SNOWFLAKE_MIN_LEN = 17
SNOWFLAKE_MAX_LEN = 19


# ============================================================
# 🧩 Helpers de rendu
# ============================================================

def _slug_line(display: str, slug: str, show_slugs: bool) -> str:
    """Ajoute une ligne discrète avec le slug si le toggle est activé."""
    if show_slugs:
        return f"{display}\n-# `{slug}`"
    return display


def _footer(container: Container) -> None:
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio · Panneau développeur"))


def _slug_toggle_button(
    show_slugs: bool, on_toggle,
) -> Button:
    """Bouton d'affichage/masquage des slugs techniques."""
    label = "Cacher les slugs" if show_slugs else "Voir les slugs"
    emoji = "🔎" if show_slugs else "🔍"
    btn = Button(label=label, emoji=emoji, style=ButtonStyle.secondary)
    btn.callback = on_toggle
    return btn


# ============================================================
# 🏠 Niveau 1 — Accueil : liste des catégories
# ============================================================

async def build_home_view(
    bot,
    author_id: int,
    show_slugs: bool = False,
) -> BaseLayoutView:
    """Vue d'accueil : liste stylisée des catégories + création."""

    categories = await rbac.list_categories()

    view = BaseLayoutView(owner_id=author_id, timeout=VIEW_TIMEOUT)
    container = Container()

    # ── Header ──────────────────────────────────────────
    container.add_item(TextDisplay("# 🔐 Permissions du bot"))
    container.add_item(TextDisplay(
        "-# Gère les catégories, les grades et leurs membres. "
        "Chaque grade correspond à un ensemble de permissions du bot."
    ))
    container.add_item(Separator())

    # ── Liste des catégories ────────────────────────────
    if not categories:
        container.add_item(TextDisplay(
            "-# *Aucune catégorie pour l'instant. Clique sur* **Nouvelle catégorie** *pour commencer.*"
        ))
    else:
        container.add_item(TextDisplay(f"## 📁 Catégories ({len(categories)})"))
        for cat in categories:
            grades = await rbac.list_grades(cat.id)
            body = _slug_line(
                f"**{cat.display_name}**\n-# {len(grades)} grade(s)",
                cat.slug,
                show_slugs,
            )
            btn_open = Button(label="Gérer", emoji="⚙️", style=ButtonStyle.primary)
            btn_open.callback = _cb_open_category(bot, author_id, cat.id, show_slugs)
            container.add_item(Section(TextDisplay(body), accessory=btn_open))

    container.add_item(Separator())

    # ── Actions globales ────────────────────────────────
    btn_new = Button(label="Nouvelle catégorie", emoji="➕", style=ButtonStyle.success)
    btn_new.callback = _cb_new_category(bot, author_id, show_slugs)
    btn_toggle = _slug_toggle_button(
        show_slugs, _cb_toggle_slugs_home(bot, author_id, show_slugs)
    )
    container.add_item(ActionRow(btn_new, btn_toggle))

    _footer(container)
    view.add_item(container)
    return view


def _cb_open_category(bot, author_id: int, category_id: int, show_slugs: bool):
    async def cb(interaction: Interaction) -> None:
        new_view = await build_category_view(bot, author_id, category_id, show_slugs)
        if new_view is None:
            await _reload_home(interaction, bot, author_id, show_slugs,
                               "Cette catégorie n'existe plus.")
            return
        await interaction.response.edit_message(view=new_view)
    return cb


def _cb_toggle_slugs_home(bot, author_id: int, current_show: bool):
    async def cb(interaction: Interaction) -> None:
        new_view = await build_home_view(bot, author_id, show_slugs=not current_show)
        await interaction.response.edit_message(view=new_view)
    return cb


def _cb_new_category(bot, author_id: int, show_slugs: bool):
    async def on_submit(inter: Interaction, display_name: str) -> None:
        display_name = display_name.strip()
        if not display_name:
            await inter.response.send_message(
                view=error_container("Le nom ne peut pas être vide."),
                ephemeral=True,
            )
            return
        slug = await rbac.unique_category_slug(display_name)
        category = await rbac.create_category(slug, display_name)
        # Va directement dans la vue de la nouvelle catégorie (elle est vide)
        new_view = await build_category_view(bot, author_id, category.id, show_slugs)
        await inter.response.edit_message(view=new_view)

    async def cb(interaction: Interaction) -> None:
        await interaction.response.send_modal(TextModal(
            title="Nouvelle catégorie",
            label="Nom affiché",
            placeholder="Ex : Staff Delta",
            max_length=128,
            on_submit=on_submit,
        ))
    return cb


# ============================================================
# 📁 Niveau 2 — Gérer une catégorie (liste des grades)
# ============================================================

async def build_category_view(
    bot,
    author_id: int,
    category_id: int,
    show_slugs: bool = False,
    reorder_mode: bool = False,
) -> BaseLayoutView | None:
    """Vue de gestion d'une catégorie : ses grades + création + suppression.

    reorder_mode : si True, chaque grade affiche ⬆️/⬇️ au lieu du bouton
    Gérer. Sortie du mode via un bouton "Terminer" en bas.
    """

    category = await rbac.get_category(category_id)
    if category is None:
        return None

    grades = await rbac.list_grades(category_id)

    view = BaseLayoutView(owner_id=author_id, timeout=VIEW_TIMEOUT)
    container = Container()

    # ── Header ──────────────────────────────────────────
    header = f"# 📁 {category.display_name}"
    if show_slugs:
        header += f"\n-# `{category.slug}`"
    container.add_item(TextDisplay(header))
    sub = f"-# {len(grades)} grade(s) dans cette catégorie"
    if reorder_mode:
        sub += " · 🔀 Mode réordonnancement actif"
    container.add_item(TextDisplay(sub))
    container.add_item(Separator())

    # ── Liste des grades ────────────────────────────────
    if not grades:
        container.add_item(TextDisplay(
            "-# *Aucun grade pour l'instant. Clique sur* **Nouveau grade** *pour en créer un.*"
        ))
    elif reorder_mode:
        # Mode réordonnancement : chaque grade a ⬆️ Monter + ⬇️ Descendre.
        container.add_item(TextDisplay("## 🎖️ Grades"))
        for idx, grade in enumerate(grades):
            members = await rbac.list_members(grade.id)
            full_slug = f"{category.slug}.{grade.slug}"
            body = _slug_line(
                f"**{grade.display_name}**\n-# {len(members)} membre(s) direct(s)",
                full_slug,
                show_slugs,
            )
            container.add_item(TextDisplay(body))
            btn_up = Button(
                label="Monter", emoji="⬆️", style=ButtonStyle.secondary,
                disabled=(idx == 0),
            )
            btn_up.callback = _cb_move_grade(
                bot, author_id, category_id, grade.id, -1, show_slugs,
            )
            btn_down = Button(
                label="Descendre", emoji="⬇️", style=ButtonStyle.secondary,
                disabled=(idx == len(grades) - 1),
            )
            btn_down.callback = _cb_move_grade(
                bot, author_id, category_id, grade.id, +1, show_slugs,
            )
            container.add_item(ActionRow(btn_up, btn_down))
    else:
        # Mode normal : chaque grade a un bouton Gérer.
        container.add_item(TextDisplay("## 🎖️ Grades"))
        for grade in grades:
            members = await rbac.list_members(grade.id)
            full_slug = f"{category.slug}.{grade.slug}"
            body = _slug_line(
                f"**{grade.display_name}**\n-# {len(members)} membre(s) direct(s)",
                full_slug,
                show_slugs,
            )
            btn_open = Button(label="Gérer", emoji="⚙️", style=ButtonStyle.primary)
            btn_open.callback = _cb_open_grade(bot, author_id, grade.id, show_slugs)
            container.add_item(Section(TextDisplay(body), accessory=btn_open))

    container.add_item(Separator())

    # ── Actions ─────────────────────────────────────────
    if reorder_mode:
        # Seul bouton dispo : sortir du mode.
        btn_done = Button(label="Terminer", emoji="✅", style=ButtonStyle.success)
        btn_done.callback = _cb_toggle_reorder(bot, author_id, category_id, show_slugs, False)
        container.add_item(ActionRow(btn_done))
    else:
        btn_new = Button(label="Nouveau grade", emoji="➕", style=ButtonStyle.success)
        btn_new.callback = _cb_new_grade(bot, author_id, category_id, show_slugs)
        btn_rename = Button(label="Renommer", emoji="✏️", style=ButtonStyle.secondary)
        btn_rename.callback = _cb_rename_category(bot, author_id, category_id, show_slugs)
        btn_delete = Button(label="Supprimer la catégorie", emoji="🗑️", style=ButtonStyle.danger)
        btn_delete.callback = _cb_delete_category(bot, author_id, category_id, show_slugs)
        container.add_item(ActionRow(btn_new, btn_rename, btn_delete))

        btn_reorder = Button(
            label="Réordonner", emoji="🔀", style=ButtonStyle.secondary,
            disabled=(len(grades) < 2),
        )
        btn_reorder.callback = _cb_toggle_reorder(bot, author_id, category_id, show_slugs, True)
        btn_back = Button(label="Retour", emoji="↩️", style=ButtonStyle.secondary)
        btn_back.callback = _cb_back_to_home(bot, author_id, show_slugs)
        btn_toggle = _slug_toggle_button(
            show_slugs, _cb_toggle_slugs_category(bot, author_id, category_id, show_slugs),
        )
        container.add_item(ActionRow(btn_reorder, btn_back, btn_toggle))

    _footer(container)
    view.add_item(container)
    return view


def _cb_open_grade(bot, author_id: int, grade_id: int, show_slugs: bool):
    async def cb(interaction: Interaction) -> None:
        new_view = await build_grade_view(bot, author_id, grade_id, show_slugs)
        if new_view is None:
            # Le grade a disparu — retour à l'accueil
            await _reload_home(interaction, bot, author_id, show_slugs,
                               "Ce grade n'existe plus.")
            return
        await interaction.response.edit_message(view=new_view)
    return cb


def _cb_back_to_home(bot, author_id: int, show_slugs: bool):
    async def cb(interaction: Interaction) -> None:
        new_view = await build_home_view(bot, author_id, show_slugs)
        await interaction.response.edit_message(view=new_view)
    return cb


def _cb_toggle_slugs_category(bot, author_id: int, category_id: int, current_show: bool):
    async def cb(interaction: Interaction) -> None:
        new_view = await build_category_view(
            bot, author_id, category_id, show_slugs=not current_show
        )
        if new_view is None:
            await _reload_home(interaction, bot, author_id, not current_show,
                               "Cette catégorie n'existe plus.")
            return
        await interaction.response.edit_message(view=new_view)
    return cb


def _cb_new_grade(bot, author_id: int, category_id: int, show_slugs: bool):
    async def on_submit(inter: Interaction, display_name: str) -> None:
        display_name = display_name.strip()
        if not display_name:
            await inter.response.send_message(
                view=error_container("Le nom ne peut pas être vide."),
                ephemeral=True,
            )
            return
        slug = await rbac.unique_grade_slug(category_id, display_name)
        grade = await rbac.create_grade(category_id, slug, display_name)
        new_view = await build_grade_view(bot, author_id, grade.id, show_slugs)
        if new_view is None:
            await _reload_home(inter, bot, author_id, show_slugs,
                               "Ce grade n'existe plus.")
            return
        await inter.response.edit_message(view=new_view)

    async def cb(interaction: Interaction) -> None:
        await interaction.response.send_modal(TextModal(
            title="Nouveau grade",
            label="Nom affiché",
            placeholder="Ex : Modérateur",
            max_length=128,
            on_submit=on_submit,
        ))
    return cb


def _cb_delete_category(bot, author_id: int, category_id: int, show_slugs: bool):
    """Suppression avec confirmation INTÉGRÉE (edit_message, pas send_message)."""

    async def cb(interaction: Interaction) -> None:
        category = await rbac.get_category(category_id)
        if category is None:
            await _reload_home(interaction, bot, author_id, show_slugs,
                               "Cette catégorie a déjà été supprimée.")
            return

        grades = await rbac.list_grades(category_id)

        async def on_confirm(conf_inter: Interaction) -> None:
            await rbac.delete_category(category_id)
            new_view = await build_home_view(bot, author_id, show_slugs)
            await conf_inter.response.edit_message(view=new_view)

        async def on_cancel(cancel_inter: Interaction) -> None:
            new_view = await build_category_view(bot, author_id, category_id, show_slugs)
            if new_view is None:
                await _reload_home(cancel_inter, bot, author_id, show_slugs, None)
                return
            await cancel_inter.response.edit_message(view=new_view)

        confirm_view = _build_confirm_view(
            author_id=author_id,
            title="🗑️ Supprimer cette catégorie ?",
            body=(
                f"Tu vas supprimer **{category.display_name}** définitivement.\n"
                f"-# {len(grades)} grade(s), leurs membres et leurs cumuls seront aussi supprimés."
            ),
            on_confirm=on_confirm,
            on_cancel=on_cancel,
        )
        await interaction.response.edit_message(view=confirm_view)
    return cb


# ============================================================
# 🎖️ Niveau 3 — Gérer un grade (membres + grades cumulés)
# ============================================================

async def build_grade_view(
    bot,
    author_id: int,
    grade_id: int,
    show_slugs: bool = False,
) -> BaseLayoutView | None:
    """Vue de gestion d'un grade : membres directs, grades cumulés, appartenance."""

    grade = await rbac.get_grade(grade_id)
    if grade is None:
        return None
    category = await rbac.get_category(grade.category_id)
    if category is None:
        return None

    members = await rbac.list_members(grade_id)
    children = await rbac.list_children(grade_id)
    parents = await rbac.list_parents(grade_id)

    full_slug = f"{category.slug}.{grade.slug}"

    view = BaseLayoutView(owner_id=author_id, timeout=VIEW_TIMEOUT)
    container = Container()

    # ── Header ──────────────────────────────────────────
    header = f"# 🎖️ {grade.display_name}"
    if show_slugs:
        header += f"\n-# `{full_slug}`"
    container.add_item(TextDisplay(header))
    container.add_item(TextDisplay(f"-# Catégorie : **{category.display_name}**"))
    container.add_item(Separator())

    # ── Section 1 : Membres directs ─────────────────────
    container.add_item(TextDisplay(f"## 👥 Membres directs ({len(members)})"))
    if not members:
        container.add_item(TextDisplay("-# *Aucun membre dans ce grade.*"))
    else:
        shown = members[:30]
        lines = "\n".join(f"• <@{m}>" for m in shown)
        if len(members) > 30:
            lines += f"\n-# *… et {len(members) - 30} de plus*"
        container.add_item(TextDisplay(lines))

    btn_add_member = Button(label="Ajouter", emoji="➕", style=ButtonStyle.success)
    btn_add_member.callback = _cb_open_member_modal(
        bot, author_id, grade_id, show_slugs, action="add"
    )
    btn_remove_member = Button(
        label="Retirer", emoji="➖",
        style=ButtonStyle.danger, disabled=not members,
    )
    btn_remove_member.callback = _cb_open_member_modal(
        bot, author_id, grade_id, show_slugs, action="remove"
    )
    container.add_item(ActionRow(btn_add_member, btn_remove_member))
    container.add_item(Separator())

    # ── Section 2 : Grades cumulés ──────────────────────
    container.add_item(TextDisplay(f"## 🔗 Grades cumulés ({len(children)})"))
    container.add_item(TextDisplay(
        "-# Les membres des grades ci-dessous sont automatiquement considérés comme membres de ce grade."
    ))
    if not children:
        container.add_item(TextDisplay("-# *Aucun grade cumulé.*"))
    else:
        lines_c = []
        for c in children:
            c_cat = await rbac.get_category(c.category_id)
            if c_cat is None:
                continue
            label = f"**{c.display_name}** _({c_cat.display_name})_"
            if show_slugs:
                label += f"\n-# `{c_cat.slug}.{c.slug}`"
            lines_c.append(f"• {label}")
        container.add_item(TextDisplay("\n".join(lines_c)))

    btn_add_include = Button(label="Cumuler un grade", emoji="➕", style=ButtonStyle.success)
    btn_add_include.callback = _cb_open_include_add(bot, author_id, grade_id, show_slugs)
    btn_remove_include = Button(
        label="Retirer un cumul", emoji="➖",
        style=ButtonStyle.danger, disabled=not children,
    )
    btn_remove_include.callback = _cb_open_include_remove(bot, author_id, grade_id, show_slugs)
    container.add_item(ActionRow(btn_add_include, btn_remove_include))
    container.add_item(Separator())

    # ── Section 3 : Appartenance (lecture seule) ────────
    if parents:
        container.add_item(TextDisplay(f"## 📥 Ce grade est cumulé par ({len(parents)})"))
        lines_p = []
        for p in parents:
            p_cat = await rbac.get_category(p.category_id)
            if p_cat is None:
                continue
            label = f"**{p.display_name}** _({p_cat.display_name})_"
            if show_slugs:
                label += f"\n-# `{p_cat.slug}.{p.slug}`"
            lines_p.append(f"• {label}")
        container.add_item(TextDisplay("\n".join(lines_p)))
        container.add_item(Separator())

    # ── Actions bas ─────────────────────────────────────
    btn_rename = Button(label="Renommer", emoji="✏️", style=ButtonStyle.secondary)
    btn_rename.callback = _cb_rename_grade(bot, author_id, grade_id, show_slugs)
    btn_delete = Button(label="Supprimer ce grade", emoji="🗑️", style=ButtonStyle.danger)
    btn_delete.callback = _cb_delete_grade(bot, author_id, grade_id, category.id, show_slugs)
    container.add_item(ActionRow(btn_rename, btn_delete))

    btn_back = Button(label="Retour", emoji="↩️", style=ButtonStyle.secondary)
    btn_back.callback = _cb_back_to_category(bot, author_id, category.id, show_slugs)
    btn_toggle = _slug_toggle_button(
        show_slugs, _cb_toggle_slugs_grade(bot, author_id, grade_id, show_slugs)
    )
    container.add_item(ActionRow(btn_back, btn_toggle))

    _footer(container)
    view.add_item(container)
    return view


def _cb_back_to_category(bot, author_id: int, category_id: int, show_slugs: bool):
    async def cb(interaction: Interaction) -> None:
        new_view = await build_category_view(bot, author_id, category_id, show_slugs)
        if new_view is None:
            await _reload_home(interaction, bot, author_id, show_slugs,
                               "Cette catégorie n'existe plus.")
            return
        await interaction.response.edit_message(view=new_view)
    return cb


def _cb_toggle_slugs_grade(bot, author_id: int, grade_id: int, current_show: bool):
    async def cb(interaction: Interaction) -> None:
        new_view = await build_grade_view(bot, author_id, grade_id, show_slugs=not current_show)
        if new_view is None:
            await _reload_home(interaction, bot, author_id, not current_show,
                               "Ce grade n'existe plus.")
            return
        await interaction.response.edit_message(view=new_view)
    return cb


def _cb_delete_grade(bot, author_id: int, grade_id: int, category_id: int, show_slugs: bool):
    """Suppression avec confirmation INTÉGRÉE."""

    async def cb(interaction: Interaction) -> None:
        grade = await rbac.get_grade(grade_id)
        if grade is None:
            fallback = await build_category_view(bot, author_id, category_id, show_slugs)
            if fallback is None:
                await _reload_home(interaction, bot, author_id, show_slugs,
                                   "Ce grade a déjà été supprimé.")
            else:
                await interaction.response.edit_message(view=fallback)
            return

        members = await rbac.list_members(grade_id)

        async def on_confirm(conf_inter: Interaction) -> None:
            await rbac.delete_grade(grade_id)
            new_view = await build_category_view(bot, author_id, category_id, show_slugs)
            if new_view is None:
                await _reload_home(conf_inter, bot, author_id, show_slugs, None)
                return
            await conf_inter.response.edit_message(view=new_view)

        async def on_cancel(cancel_inter: Interaction) -> None:
            new_view = await build_grade_view(bot, author_id, grade_id, show_slugs)
            if new_view is None:
                await _reload_home(cancel_inter, bot, author_id, show_slugs, None)
                return
            await cancel_inter.response.edit_message(view=new_view)

        confirm_view = _build_confirm_view(
            author_id=author_id,
            title="🗑️ Supprimer ce grade ?",
            body=(
                f"Tu vas supprimer **{grade.display_name}** définitivement.\n"
                f"-# {len(members)} membre(s) direct(s) et tous les cumuls associés seront perdus."
            ),
            on_confirm=on_confirm,
            on_cancel=on_cancel,
        )
        await interaction.response.edit_message(view=confirm_view)
    return cb


# ============================================================
# 👥 Ajout / retrait d'un membre (modal ID, validation stricte)
# ============================================================

class _MemberIdModal(discord.ui.Modal):
    """Modal de saisie d'un ID Discord, validé strictement 17-19 chiffres."""

    def __init__(
        self, *, action: str, bot, author_id: int, grade_id: int, show_slugs: bool,
    ) -> None:
        title = "Ajouter un membre" if action == "add" else "Retirer un membre"
        super().__init__(title=title)
        self.action = action
        self.bot = bot
        self.author_id = author_id
        self.grade_id = grade_id
        self.show_slugs = show_slugs

        self.id_input = discord.ui.TextInput(
            label="ID Discord (17 à 19 chiffres)",
            placeholder="Ex : 751903718135431188",
            required=True,
            min_length=SNOWFLAKE_MIN_LEN,
            max_length=SNOWFLAKE_MAX_LEN,
        )
        self.add_item(self.id_input)

    async def on_submit(self, interaction: Interaction) -> None:
        raw = self.id_input.value.strip()

        # Validation stricte : uniquement chiffres, longueur snowflake.
        if not raw.isdigit() or not (SNOWFLAKE_MIN_LEN <= len(raw) <= SNOWFLAKE_MAX_LEN):
            await interaction.response.send_message(
                view=error_container(
                    f"ID invalide. Un ID Discord contient **{SNOWFLAKE_MIN_LEN} à "
                    f"{SNOWFLAKE_MAX_LEN} chiffres** uniquement."
                ),
                ephemeral=True,
            )
            return

        discord_id = int(raw)

        # Applique l'action puis retourne à la vue grade mise à jour, sans flash.
        if self.action == "add":
            await rbac.add_member(self.grade_id, discord_id)
        else:
            await rbac.remove_member(self.grade_id, discord_id)

        new_view = await build_grade_view(
            self.bot, self.author_id, self.grade_id, self.show_slugs
        )
        if new_view is None:
            await interaction.response.send_message(
                view=error_container("Ce grade n'existe plus."),
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(view=new_view)


def _cb_open_member_modal(
    bot, author_id: int, grade_id: int, show_slugs: bool, *, action: str,
):
    async def cb(interaction: Interaction) -> None:
        await interaction.response.send_modal(_MemberIdModal(
            action=action, bot=bot, author_id=author_id,
            grade_id=grade_id, show_slugs=show_slugs,
        ))
    return cb


# ============================================================
# 🔗 Ajout / retrait d'un cumul (select intermédiaire)
# ============================================================

def _cb_open_include_add(bot, author_id: int, grade_id: int, show_slugs: bool):
    """Ouvre une vue transitoire avec un select de grades cumulables."""

    async def cb(interaction: Interaction) -> None:
        options = await _build_add_include_options(grade_id)
        if not options:
            await interaction.response.send_message(
                view=error_container(
                    "Aucun autre grade disponible à cumuler (soit tous déjà cumulés, "
                    "soit ils créeraient un cycle)."
                ),
                ephemeral=True,
            )
            return

        async def on_choice(sel_inter: Interaction, chosen_grade_id: int) -> None:
            ok = await rbac.add_include(grade_id, chosen_grade_id)
            if not ok:
                await sel_inter.response.send_message(
                    view=error_container(
                        "Impossible d'ajouter ce cumul (cycle détecté ou grade invalide)."
                    ),
                    ephemeral=True,
                )
                return
            new_view = await build_grade_view(bot, author_id, grade_id, show_slugs)
            if new_view is None:
                await _reload_home(sel_inter, bot, author_id, show_slugs,
                                   "Ce grade n'existe plus.")
                return
            await sel_inter.response.edit_message(view=new_view)

        async def on_cancel(cancel_inter: Interaction) -> None:
            new_view = await build_grade_view(bot, author_id, grade_id, show_slugs)
            if new_view is None:
                await _reload_home(cancel_inter, bot, author_id, show_slugs, None)
                return
            await cancel_inter.response.edit_message(view=new_view)

        select_view = _build_grade_select_view(
            author_id=author_id,
            title="🔗 Choisir le grade à cumuler",
            body="Les membres du grade choisi seront automatiquement considérés comme membres du grade actuel.",
            options=options,
            on_choice=on_choice,
            on_cancel=on_cancel,
        )
        await interaction.response.edit_message(view=select_view)
    return cb


def _cb_open_include_remove(bot, author_id: int, grade_id: int, show_slugs: bool):
    """Ouvre une vue transitoire pour retirer un cumul actuel."""

    async def cb(interaction: Interaction) -> None:
        children = await rbac.list_children(grade_id)
        if not children:
            await interaction.response.send_message(
                view=error_container("Aucun cumul à retirer."),
                ephemeral=True,
            )
            return

        options: list[SelectOption] = []
        for c in children[:25]:
            c_cat = await rbac.get_category(c.category_id)
            cat_label = c_cat.display_name if c_cat else "?"
            options.append(SelectOption(
                label=c.display_name[:100],
                description=f"Catégorie : {cat_label}"[:100],
                value=str(c.id),
            ))

        async def on_choice(sel_inter: Interaction, chosen_grade_id: int) -> None:
            await rbac.remove_include(grade_id, chosen_grade_id)
            new_view = await build_grade_view(bot, author_id, grade_id, show_slugs)
            if new_view is None:
                await _reload_home(sel_inter, bot, author_id, show_slugs,
                                   "Ce grade n'existe plus.")
                return
            await sel_inter.response.edit_message(view=new_view)

        async def on_cancel(cancel_inter: Interaction) -> None:
            new_view = await build_grade_view(bot, author_id, grade_id, show_slugs)
            if new_view is None:
                await _reload_home(cancel_inter, bot, author_id, show_slugs, None)
                return
            await cancel_inter.response.edit_message(view=new_view)

        select_view = _build_grade_select_view(
            author_id=author_id,
            title="🔗 Retirer un cumul",
            body="Choisis le grade à ne plus cumuler.",
            options=options,
            on_choice=on_choice,
            on_cancel=on_cancel,
        )
        await interaction.response.edit_message(view=select_view)
    return cb


async def _build_add_include_options(grade_id: int) -> list[SelectOption]:
    """Options de grades cumulables : exclut soi-même, descendants, et déjà cumulés."""
    all_grades = await rbac.list_all_grades_with_category()
    current_children_ids = {c.id for c in await rbac.list_children(grade_id)}
    options: list[SelectOption] = []
    for g, cat in all_grades:
        if len(options) >= 25:
            break
        if g.id in current_children_ids:
            continue
        if not await rbac.can_include(grade_id, g.id):
            continue
        options.append(SelectOption(
            label=g.display_name[:100],
            description=f"Catégorie : {cat.display_name}"[:100],
            value=str(g.id),
        ))
    return options


# ============================================================
# 🔧 Vues transitoires (confirmation + select générique)
# ============================================================

def _build_confirm_view(
    *, author_id: int, title: str, body: str, on_confirm, on_cancel,
) -> BaseLayoutView:
    """Vue de confirmation intégrée (remplace la vue actuelle via edit_message)."""

    view = BaseLayoutView(owner_id=author_id, timeout=120)
    container = Container()
    container.add_item(TextDisplay(title))
    container.add_item(Separator())
    container.add_item(TextDisplay(body))
    container.add_item(Separator())

    btn_confirm = Button(label="Confirmer", emoji="✅", style=ButtonStyle.danger)
    btn_confirm.callback = on_confirm
    btn_cancel = Button(label="Annuler", emoji="↩️", style=ButtonStyle.secondary)
    btn_cancel.callback = on_cancel
    container.add_item(ActionRow(btn_confirm, btn_cancel))

    _footer(container)
    view.add_item(container)
    return view


def _build_grade_select_view(
    *, author_id: int, title: str, body: str,
    options: list[SelectOption], on_choice, on_cancel,
) -> BaseLayoutView:
    """Vue transitoire avec un Select + bouton Retour."""

    view = BaseLayoutView(owner_id=author_id, timeout=120)
    container = Container()
    container.add_item(TextDisplay(title))
    container.add_item(Separator())
    container.add_item(TextDisplay(body))
    container.add_item(Separator())

    select = Select(placeholder="Choisir un grade…", options=options, min_values=1, max_values=1)

    async def _on_select(inter: Interaction) -> None:
        await on_choice(inter, int(select.values[0]))

    select.callback = _on_select
    container.add_item(ActionRow(select))

    btn_back = Button(label="Annuler", emoji="↩️", style=ButtonStyle.secondary)
    btn_back.callback = on_cancel
    container.add_item(ActionRow(btn_back))

    _footer(container)
    view.add_item(container)
    return view


# ============================================================
# 🔄 Helpers de récupération d'erreur
# ============================================================

async def _reload_home(
    interaction: Interaction, bot, author_id: int, show_slugs: bool,
    error_msg: str | None,
) -> None:
    """Revient à l'accueil suite à une erreur de récupération (élément supprimé)."""
    new_view = await build_home_view(bot, author_id, show_slugs)
    try:
        await interaction.response.edit_message(view=new_view)
    except discord.InteractionResponded:
        try:
            await interaction.edit_original_response(view=new_view)
        except (discord.NotFound, discord.HTTPException):
            log.warning("[DEV PERMISSIONS] Impossible de revenir à l'accueil")
    if error_msg:
        try:
            await interaction.followup.send(
                view=error_container(error_msg), ephemeral=True,
            )
        except (discord.NotFound, discord.HTTPException):
            pass


# ============================================================
# 🔀 Callbacks du mode réordonnancement
# ============================================================

def _cb_toggle_reorder(
    bot, author_id: int, category_id: int, show_slugs: bool, enter_reorder: bool,
):
    """Entre ou sort du mode réordonnancement pour la vue catégorie."""
    async def cb(interaction: Interaction) -> None:
        new_view = await build_category_view(
            bot, author_id, category_id, show_slugs,
            reorder_mode=enter_reorder,
        )
        if new_view is None:
            await _reload_home(interaction, bot, author_id, show_slugs,
                               "Cette catégorie n'existe plus.")
            return
        await interaction.response.edit_message(view=new_view)
    return cb


def _cb_move_grade(
    bot, author_id: int, category_id: int, grade_id: int,
    direction: int, show_slugs: bool,
):
    """Déplace un grade d'un cran (direction -1 = haut, +1 = bas)."""
    async def cb(interaction: Interaction) -> None:
        moved = await rbac.move_grade(grade_id, direction)
        if not moved:
            # Peut arriver si un autre dev bouge le grade en même temps
            # (concurrence rare mais possible). Silencieux.
            log.debug(
                "[DEV PERMISSIONS] move_grade(%s, %d) sans effet",
                grade_id, direction,
            )
        new_view = await build_category_view(
            bot, author_id, category_id, show_slugs,
            reorder_mode=True,  # on reste en mode réordonnancement
        )
        if new_view is None:
            await _reload_home(interaction, bot, author_id, show_slugs,
                               "Cette catégorie n'existe plus.")
            return
        await interaction.response.edit_message(view=new_view)
    return cb


# ============================================================
# ✏️ Renommage catégorie / grade
# ============================================================

class _RenameModal(discord.ui.Modal):
    """
    Modal 2 champs (nom affiché + slug) pré-remplis. À la soumission,
    appelle `on_submit_cb(interaction, new_display_name, new_slug)`.
    """

    def __init__(
        self,
        *,
        title: str,
        current_display_name: str,
        current_slug: str,
        on_submit_cb,
    ) -> None:
        super().__init__(title=title, timeout=180)
        self._on_submit_cb = on_submit_cb

        self.field_display = discord.ui.TextInput(
            label="Nom affiché",
            style=discord.TextStyle.short,
            default=current_display_name,
            required=True,
            max_length=64,
        )
        self.field_slug = discord.ui.TextInput(
            label="Slug (identifiant technique)",
            style=discord.TextStyle.short,
            default=current_slug,
            placeholder="ex: op, super_moderateur — sans point, sans espace",
            required=True,
            max_length=64,
        )
        self.add_item(self.field_display)
        self.add_item(self.field_slug)

    async def on_submit(self, interaction: Interaction) -> None:
        await self._on_submit_cb(
            interaction,
            self.field_display.value,
            self.field_slug.value,
        )


def _cb_rename_category(bot, author_id: int, category_id: int, show_slugs: bool):
    """Ouvre le modal de renommage d'une catégorie."""
    async def cb(interaction: Interaction) -> None:
        category = await rbac.get_category(category_id)
        if category is None:
            await _reload_home(
                interaction, bot, author_id, show_slugs,
                "Cette catégorie n'existe plus.",
            )
            return

        old_slug = category.slug

        async def on_submit(inter: Interaction, new_display: str, new_slug: str) -> None:
            ok, err = await rbac.rename_category(
                category_id,
                new_display_name=new_display,
                new_slug=new_slug,
            )
            if not ok:
                await inter.response.send_message(
                    view=warning_container(err), ephemeral=True,
                )
                return

            # Recharge la vue catégorie (peut avoir un nouveau slug/display).
            new_view = await build_category_view(bot, author_id, category_id, show_slugs)
            if new_view is None:
                await _reload_home(
                    inter, bot, author_id, show_slugs,
                    "Cette catégorie n'existe plus.",
                )
                return
            await inter.response.edit_message(view=new_view)

            # Warning si le slug a changé (implication code).
            updated = await rbac.get_category(category_id)
            if updated is not None and updated.slug != old_slug:
                await inter.followup.send(
                    view=warning_container(
                        f"⚠️ **Slug modifié** : `{old_slug}` → `{updated.slug}`.\n"
                        "-# Vérifie que le nouveau slug est bien utilisé dans le "
                        "code (`has_grade_check(\"<slug>.<grade>\", ...)`), "
                        "sinon les checks concernés vont échouer silencieusement."
                    ),
                    ephemeral=True,
                )

        await interaction.response.send_modal(_RenameModal(
            title="Renommer la catégorie",
            current_display_name=category.display_name,
            current_slug=category.slug,
            on_submit_cb=on_submit,
        ))
    return cb


def _cb_rename_grade(bot, author_id: int, grade_id: int, show_slugs: bool):
    """Ouvre le modal de renommage d'un grade."""
    async def cb(interaction: Interaction) -> None:
        grade = await rbac.get_grade(grade_id)
        if grade is None:
            await _reload_home(
                interaction, bot, author_id, show_slugs,
                "Ce grade n'existe plus.",
            )
            return

        category = await rbac.get_category(grade.category_id)
        old_slug = grade.slug
        old_full_slug = f"{category.slug}.{old_slug}" if category else old_slug

        async def on_submit(inter: Interaction, new_display: str, new_slug: str) -> None:
            ok, err = await rbac.rename_grade(
                grade_id,
                new_display_name=new_display,
                new_slug=new_slug,
            )
            if not ok:
                await inter.response.send_message(
                    view=warning_container(err), ephemeral=True,
                )
                return

            new_view = await build_grade_view(bot, author_id, grade_id, show_slugs)
            if new_view is None:
                await _reload_home(
                    inter, bot, author_id, show_slugs,
                    "Ce grade n'existe plus.",
                )
                return
            await inter.response.edit_message(view=new_view)

            updated = await rbac.get_grade(grade_id)
            if updated is not None and updated.slug != old_slug:
                new_full_slug = f"{category.slug}.{updated.slug}" if category else updated.slug
                await inter.followup.send(
                    view=warning_container(
                        f"⚠️ **Slug modifié** : `{old_full_slug}` → `{new_full_slug}`.\n"
                        "-# Vérifie que le nouveau slug est bien utilisé dans le "
                        "code (`has_grade_check(\"<slug>\", ...)`), sinon les "
                        "checks concernés vont échouer silencieusement."
                    ),
                    ephemeral=True,
                )

        await interaction.response.send_modal(_RenameModal(
            title="Renommer le grade",
            current_display_name=grade.display_name,
            current_slug=grade.slug,
            on_submit_cb=on_submit,
        ))
    return cb


# ============================================================
# 🔙 Compatibilité — ancien nom d'entrée
# ============================================================

# Le cog cogs/dev/permission.py appelle build_category_list_view.
# Alias pour ne pas devoir toucher au cog.
build_category_list_view = build_home_view