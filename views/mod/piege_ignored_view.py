"""
views/mod/piege_ignored_view.py — Sous-écran de PiegeConfigView : gestion
(ajout + suppression, liste paginée) des rôles/membres ignorés par le
piège anti-raid.

BUG CORRIGÉ (2026-09, signalé par Paul) : PiegeConfigView affichait
jusqu'à 10 rôles + 10 membres ignorés directement dans le panneau
principal, chacun sous la forme d'un `Section(TextDisplay, accessory=
Button)`. Un tel Section coûte 3 composants Discord (lui-même + son
accessory + son enfant texte, cf. discord.py Section._total_count) —
avec le reste du panneau (en-tête, salon, statut, 2 Select, doc...), la
limite Discord de 40 composants/message finissait par être dépassée dès
qu'il y avait suffisamment de rôles/membres ignorés (`ValueError:
maximum number of children exceeded (40)`, cf. traceback fourni par
Paul le 2026-09-16).

Fix : le panneau principal n'affiche plus qu'un simple compteur, avec un
bouton "Gérer la liste" qui ouvre CETTE vue dédiée. Ici la liste est
paginée (cf. views/_components/paginated_view.py::PaginatedView, même
base que le classement EXP) : chaque page ne montre qu'un nombre borné
de lignes, donc le budget de 40 composants ne peut plus jamais être
dépassé quel que soit le nombre de rôles/membres ignorés.

Rôles et membres sont fusionnés dans une seule liste paginée (tuples
`(type, id)`) plutôt que deux vues séparées : Paul a demandé "un bouton
avec une nouvelle page" (singulier) — un seul point d'entrée pour gérer
les deux catégories.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.managers.honeypot_manager import (
    add_ignored_member,
    add_ignored_role,
    load_config,
    remove_ignored_member,
    remove_ignored_role,
)
from views._components.paginated_view import PaginatedView
from views._components.role_select import RoleSelect
from views._components.user_select import UserSelect

ICON_HEADER = "<:bouclier:1539013183577133106>"
ICON_DELETE = "<:supprimer:1495444051623809075>"
EMOJI_BACK = "<:retour:1515658955190308995>"

MAX_ADD_AT_ONCE = 5

# Budget de composants Discord (limite dure de 40/message, Components V2) :
# Container(1) + 2 TextDisplay d'en-tête(2) + 3 Separator(3) + 2 ActionRow
# de Select d'ajout(2+2) + 1 ActionRow bouton Retour(2) + chrome de
# PaginatedView (Separator + indicateur de page + ActionRow prev/next =
# 1+1+3=5) = 17 de chrome fixe. Chaque ligne (Section+TextDisplay+
# accessory Button) coûte 3 (cf. discord.py Section._total_count = 2 +
# len(children), plus la Section elle-même comptée par Container.walk_
# children). 17 + 3×N <= 40  =>  N <= 7 : PER_PAGE=7 laisse 2 de marge
# (17 + 21 = 38) — NE PAS augmenter sans revérifier ce calcul (cf. le
# crash "maximum number of children exceeded (40)" que ce fichier corrige).
PER_PAGE = 7


class PiegeIgnoredListView(PaginatedView):
    """Liste paginée des rôles/membres ignorés, avec ajout et suppression."""

    def __init__(
        self, *, guild: discord.Guild, moderator_id: int,
        ignored_role_ids: list[int], ignored_member_ids: list[int], page: int = 0,
    ):
        self.guild = guild
        self.moderator_id = moderator_id

        items: list[tuple[str, int]] = (
            [("role", role_id) for role_id in ignored_role_ids]
            + [("member", member_id) for member_id in ignored_member_ids]
        )
        super().__init__(items, per_page=PER_PAGE, owner_id=moderator_id)

        if page:
            self.page = min(page, self.total_pages - 1)
            self._build()

    @classmethod
    async def create(cls, *, guild: discord.Guild, moderator_id: int, page: int = 0) -> "PiegeIgnoredListView":
        cfg = await load_config(guild.id)
        return cls(
            guild=guild,
            moderator_id=moderator_id,
            ignored_role_ids=cfg.get("ignored_role_ids") or [],
            ignored_member_ids=cfg.get("ignored_member_ids") or [],
            page=page,
        )

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def build_page_container(self, page_items: list[tuple[str, int]]) -> Container:
        container = Container()
        container.add_item(TextDisplay(f"# {ICON_HEADER} Rôles & membres ignorés"))
        container.add_item(TextDisplay(
            "-# Un membre possédant un de ces rôles, ou présent dans cette liste, "
            "ne déclenche jamais le piège."
        ))
        container.add_item(Separator())

        if not page_items:
            container.add_item(TextDisplay("-# Aucun rôle ni membre ignoré pour l'instant."))
        else:
            for entry_type, entry_id in page_items:
                container.add_item(Section(
                    TextDisplay(self._entry_label(entry_type, entry_id)),
                    accessory=self._remove_button(entry_type, entry_id),
                ))
        container.add_item(Separator())

        role_select = RoleSelect(
            placeholder="Ajouter un/des rôle(s) ignoré(s)",
            on_select=self._on_add_roles,
            max_values=MAX_ADD_AT_ONCE,
        )
        container.add_item(ActionRow(role_select))

        user_select = UserSelect(
            placeholder="Ajouter un/des membre(s) ignoré(s)",
            on_select=self._on_add_members,
            max_values=MAX_ADD_AT_ONCE,
        )
        container.add_item(ActionRow(user_select))
        container.add_item(Separator())

        back_btn = Button(label="Retour", style=ButtonStyle.secondary, emoji=EMOJI_BACK)
        back_btn.callback = self._cb_back
        container.add_item(ActionRow(back_btn))

        return container

    def _entry_label(self, entry_type: str, entry_id: int) -> str:
        if entry_type == "role":
            role = self.guild.get_role(entry_id)
            return f"🚫 {role.mention}" if role is not None else f"🚫 `Rôle supprimé ({entry_id})`"
        member = self.guild.get_member(entry_id)
        return f"🚫 {member.mention}" if member is not None else f"🚫 `Membre introuvable ({entry_id})`"

    def _remove_button(self, entry_type: str, entry_id: int) -> Button:
        btn = Button(style=ButtonStyle.danger, emoji=ICON_DELETE)
        btn.callback = self._cb_remove_role(entry_id) if entry_type == "role" else self._cb_remove_member(entry_id)
        return btn

    # ------------------------------------------------------------------
    # Callbacks — ajout
    # ------------------------------------------------------------------

    async def _on_add_roles(self, interaction: discord.Interaction, role_ids: list[int]) -> None:
        for role_id in role_ids:
            await add_ignored_role(self.guild.id, role_id)
        await self._reload(interaction)

    async def _on_add_members(self, interaction: discord.Interaction, member_ids: list[int]) -> None:
        for member_id in member_ids:
            await add_ignored_member(self.guild.id, member_id)
        await self._reload(interaction)

    # ------------------------------------------------------------------
    # Callbacks — suppression
    # ------------------------------------------------------------------

    def _cb_remove_role(self, role_id: int):
        async def _callback(interaction: discord.Interaction) -> None:
            await remove_ignored_role(self.guild.id, role_id)
            await self._reload(interaction)
        return _callback

    def _cb_remove_member(self, member_id: int):
        async def _callback(interaction: discord.Interaction) -> None:
            await remove_ignored_member(self.guild.id, member_id)
            await self._reload(interaction)
        return _callback

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    async def _reload(self, interaction: discord.Interaction) -> None:
        """Recharge la config et réaffiche à la même page (ramenée à la
        dernière page valide si un ajout/retrait l'a fait disparaître)."""
        new_view = await PiegeIgnoredListView.create(guild=self.guild, moderator_id=self.moderator_id, page=self.page)
        await self.push_update(interaction, view=new_view)

    async def _cb_back(self, interaction: discord.Interaction) -> None:
        from views.mod.piege_config_view import PiegeConfigView

        view = await PiegeConfigView.create(guild=self.guild, moderator_id=self.moderator_id)
        await self.push_update(interaction, view=view)