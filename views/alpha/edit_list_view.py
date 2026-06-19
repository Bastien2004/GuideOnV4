"""
views/alpha/edit_list_view.py — Dashboard CRUD liste staff Alpha.

Permet d'ajouter / modifier / supprimer des membres de la liste staff
(DB + rafraîchissement du message stafflist) sans les messages décoratifs
du processus rank/derank.

Flux :
  MainView → [Ajouter | Modifier | Supprimer]
    Ajouter  → UserSelect → Grade buttons → TextModal(pseudo + emoji) → save
    Modifier → UserSelect → Options (pseudo|grade|emoji) → TextModal/Grade buttons → save
    Supprimer→ UserSelect → Confirmation → delete
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.container_universel import error_container, success_container, warning_container
from utils.managers.alpha_staff_manager import (
    add_staff_member,
    get_staff_member,
    list_staff,
    remove_staff_member,
    update_staff_member,
    upsert_staff_member,
)
from utils.db.models.alpha_staff import GRADES_ORDER, GRADE_LABELS, GRADE_EMOJIS
from utils.alpha_staff_display import build_member_badges
from views._components.user_select import UserSelect
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)


# ── Helper retour main ───────────────────────────────────────

async def _back_to_main(interaction: Interaction, owner_id: int) -> None:
    members = await list_staff()
    await interaction.response.edit_message(
        view=EditListView(interaction.guild_id, owner_id, members)
    )


# ════════════════════════════════════════════════════════════
# 🏠 Vue principale
# ════════════════════════════════════════════════════════════

class EditListView(LayoutView):
    """Dashboard principal : résumé + 3 boutons d'action."""

    def __init__(self, guild_id: int, owner_id: int, members: list[dict] | None = None) -> None:
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.members = members or []
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Seul l'auteur peut utiliser ce menu.", ephemeral=True
            )
            return False
        return True

    def _build(self) -> None:
        total = len(self.members)

        # Stats par grade — grade=None regroupé séparément ("Sans grade",
        # membres existant uniquement via un statut secondaire).
        grade_counts: dict[str | None, int] = {}
        for m in self.members:
            grade_counts[m["grade"]] = grade_counts.get(m["grade"], 0) + 1

        summary_lines = [
            f"• {GRADE_LABELS.get(g, g)} : **{grade_counts[g]}**"
            for g in GRADES_ORDER if g in grade_counts
        ]
        if grade_counts.get(None):
            summary_lines.append(f"• *Sans grade (statut seul)* : **{grade_counts[None]}**")

        builder_count = sum(1 for m in self.members if m.get("is_builder"))
        if builder_count:
            summary_lines.append(f"• 🧱 Builders (cumul) : **{builder_count}**")

        c = Container()
        c.add_item(TextDisplay("# 📋 Dashboard — Liste Staff Alpha"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**{total} membre(s) au total**\n\n"
            + "\n".join(summary_lines)
        ))
        c.add_item(Separator())

        btn_add = Button(label="➕ Ajouter", style=ButtonStyle.success, custom_id="el_add")
        btn_mod = Button(label="✏️ Modifier", style=ButtonStyle.primary, custom_id="el_mod")
        btn_del = Button(label="➖ Supprimer", style=ButtonStyle.danger, custom_id="el_del")
        btn_add.callback = self._on_add
        btn_mod.callback = self._on_modify
        btn_del.callback = self._on_remove

        c.add_item(ActionRow(btn_add, btn_mod, btn_del))
        c.add_item(TextDisplay("-# GuideOn Studio — modifications sans effets rank/derank"))
        self.add_item(c)

    # ── Navigation ────────────────────────────────────────────

    async def _on_add(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(view=_UserSelectView(
            guild_id=self.guild_id,
            owner_id=self.owner_id,
            title="## ➕ Ajouter un membre",
            desc="Sélectionnez le membre Discord à ajouter à la liste staff.",
            on_select=self._after_select_add,
        ))

    async def _on_modify(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(view=_UserSelectView(
            guild_id=self.guild_id,
            owner_id=self.owner_id,
            title="## ✏️ Modifier un membre",
            desc="Sélectionnez le membre dont vous souhaitez modifier les informations.",
            on_select=self._after_select_modify,
        ))

    async def _on_remove(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(view=_UserSelectView(
            guild_id=self.guild_id,
            owner_id=self.owner_id,
            title="## ➖ Supprimer un membre",
            desc="Sélectionnez le membre à retirer de la liste staff.",
            on_select=self._after_select_remove,
        ))

    # ── Callbacks post-UserSelect ─────────────────────────────

    async def _after_select_add(self, interaction: Interaction, user_ids: list[int]) -> None:
        uid = user_ids[0]
        member = interaction.guild.get_member(uid)
        name = member.display_name if member else f"<@{uid}>"
        await interaction.response.edit_message(
            view=_GradeSelectView(
                guild_id=self.guild_id,
                owner_id=self.owner_id,
                discord_id=uid,
                member_name=name,
                on_grade=self._after_grade_add,
            )
        )

    async def _after_grade_add(
        self, interaction: Interaction, discord_id: int, member_name: str, grade: str | None
    ) -> None:
        if grade is None:
            return await interaction.response.edit_message(
                view=_GradeSelectView(
                    guild_id=self.guild_id,
                    owner_id=self.owner_id,
                    discord_id=discord_id,
                    member_name=member_name,
                    on_grade=self._after_grade_add,
                    error_message="« Aucun grade » n'a pas de sens pour un **ajout** — "
                                  "choisissez un grade, ou utilisez `/alpha rank type:statut` "
                                  "pour un statut Journaliste/Affilié/Builder seul.",
                )
            )

        label = GRADE_LABELS.get(grade, grade)

        async def on_submit(inter: Interaction, values: tuple[str, str]) -> None:
            pseudo, emoji = values
            pseudo = pseudo.strip()
            emoji = emoji.strip()
            already = await get_staff_member(discord_id)
            if already:
                await update_staff_member(discord_id, pseudo_jeu=pseudo, grade=grade, skin_head_emoji=emoji or None)
                msg = f"**{pseudo}** (<@{discord_id}>) mis à jour — **{label}**."
            else:
                await add_staff_member(discord_id, pseudo_jeu=pseudo, grade=grade, skin_head_emoji=emoji)
                msg = f"**{pseudo}** (<@{discord_id}>) ajouté — **{label}**."
            # Refresh stafflist
            from cogs.alpha.stafflist import refresh_staff_message
            await refresh_staff_message(inter.client, self.guild_id)
            members = await list_staff()
            await inter.response.edit_message(
                view=EditListView(self.guild_id, self.owner_id, members)
            )

        modal = _AddStaffModal(
            member_name=member_name,
            grade_label=label,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)

    async def _after_select_modify(self, interaction: Interaction, user_ids: list[int]) -> None:
        uid = user_ids[0]
        data = await get_staff_member(uid)
        if data is None:
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else f"<@{uid}>"
            return await interaction.response.edit_message(
                view=_NotFoundView(self.guild_id, self.owner_id, name)
            )
        await interaction.response.edit_message(
            view=_ModifyOptionsView(self.guild_id, self.owner_id, data)
        )

    async def _after_select_remove(self, interaction: Interaction, user_ids: list[int]) -> None:
        uid = user_ids[0]
        data = await get_staff_member(uid)
        if data is None:
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else f"<@{uid}>"
            return await interaction.response.edit_message(
                view=_NotFoundView(self.guild_id, self.owner_id, name)
            )
        await interaction.response.edit_message(
            view=_ConfirmRemoveView(self.guild_id, self.owner_id, data)
        )


# ════════════════════════════════════════════════════════════
# 🔘 Sous-vue : UserSelect générique
# ════════════════════════════════════════════════════════════

class _UserSelectView(LayoutView):
    def __init__(
        self, guild_id: int, owner_id: int,
        title: str, desc: str,
        on_select,
    ) -> None:
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self._on_select = on_select
        self._build(title, desc)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.owner_id

    def _build(self, title: str, desc: str) -> None:
        c = Container()
        c.add_item(TextDisplay(title))
        c.add_item(Separator())
        c.add_item(TextDisplay(desc))

        select = UserSelect(
            placeholder="Sélectionner un membre Discord",
            on_select=self._on_select,
        )
        c.add_item(ActionRow(select))
        c.add_item(Separator())

        btn_back = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="usel_back")
        btn_back.callback = self._on_back
        c.add_item(ActionRow(btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_back(self, interaction: Interaction) -> None:
        await _back_to_main(interaction, self.owner_id)


# ════════════════════════════════════════════════════════════
# 🎭 Sous-vue : Sélection de grade (boutons)
# ════════════════════════════════════════════════════════════

class _GradeSelectView(LayoutView):
    def __init__(
        self, guild_id: int, owner_id: int,
        discord_id: int, member_name: str,
        on_grade,
        error_message: str | None = None,
    ) -> None:
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.discord_id = discord_id
        self.member_name = member_name
        self._on_grade = on_grade
        self.error_message = error_message
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.owner_id

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay(f"## Sélectionner un grade\npour **{self.member_name}**"))
        if self.error_message:
            c.add_item(TextDisplay(f"⚠️ {self.error_message}"))
        c.add_item(Separator())

        # 6 grades de la hiérarchie, répartis sur 2 rangées de 3.
        row1_grades = GRADES_ORDER[:3]   # administrateur, super_moderateur, moderateur_plus
        row2_grades = GRADES_ORDER[3:]   # moderateur_confirme, moderateur_test, guide

        row1_buttons = []
        for g in row1_grades:
            b = Button(label=GRADE_LABELS[g], style=ButtonStyle.primary, custom_id=f"grade_{g}")
            b.callback = self._make_callback(g)
            row1_buttons.append(b)

        row2_buttons = []
        for g in row2_grades:
            b = Button(label=GRADE_LABELS[g], style=ButtonStyle.secondary, custom_id=f"grade_{g}")
            b.callback = self._make_callback(g)
            row2_buttons.append(b)

        # Bouton dédié pour retirer le grade (membre "sans grade" — statuts
        # secondaires uniquement). N'a de sens qu'en modification, pas à la
        # création (un nouvel ajout doit avoir un grade pour exister via ce
        # dashboard) — affiché systématiquement, sans effet de bord si déjà
        # sans grade (le callback gère ce cas via update_staff_member).
        none_button = Button(label="🚫 Aucun grade", style=ButtonStyle.danger, custom_id="grade_none")
        none_button.callback = self._make_callback(None)

        c.add_item(ActionRow(*row1_buttons))
        c.add_item(ActionRow(*row2_buttons))
        c.add_item(ActionRow(none_button))
        c.add_item(Separator())

        btn_back = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="grade_back")
        btn_back.callback = self._on_back
        c.add_item(ActionRow(btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    def _make_callback(self, grade: str | None):
        async def cb(interaction: Interaction) -> None:
            await self._on_grade(interaction, self.discord_id, self.member_name, grade)
        return cb

    async def _on_back(self, interaction: Interaction) -> None:
        await _back_to_main(interaction, self.owner_id)


# ════════════════════════════════════════════════════════════
# ✏️ Sous-vue : Options de modification
# ════════════════════════════════════════════════════════════

class _ModifyOptionsView(LayoutView):
    def __init__(self, guild_id: int, owner_id: int, member_data: dict) -> None:
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.data = member_data
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.owner_id

    def _build(self) -> None:
        d = self.data
        label = GRADE_LABELS.get(d["grade"], d["grade"]) if d["grade"] else "*Aucun grade*"
        badges = build_member_badges(d)
        builder_line = f"\n• Pseudo Builder : **{d['pseudo_jeu_builder']}**" if d.get("pseudo_jeu_builder") else ""

        c = Container()
        c.add_item(TextDisplay(f"## ✏️ Modifier **{d['pseudo_jeu']}**{badges}"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"• Grade : **{label}**\n"
            f"• Skin : {d['skin_head_emoji'] or '*(vide)*'}\n"
            f"• Discord : <@{d['discord_id']}>"
            f"{builder_line}"
        ))
        c.add_item(Separator())

        btn_pseudo = Button(label="📝 Pseudo", style=ButtonStyle.primary, custom_id="mod_pseudo")
        btn_grade  = Button(label="🎭 Grade",  style=ButtonStyle.primary, custom_id="mod_grade")
        btn_emoji  = Button(label="🖼️ Emoji",  style=ButtonStyle.primary, custom_id="mod_emoji")
        btn_back   = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="mod_back")

        btn_pseudo.callback = self._on_pseudo
        btn_grade.callback  = self._on_grade
        btn_emoji.callback  = self._on_emoji
        btn_back.callback   = self._on_back

        c.add_item(ActionRow(btn_pseudo, btn_grade, btn_emoji, btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_pseudo(self, interaction: Interaction) -> None:
        d = self.data
        modal = TextModal(
            title="Modifier le pseudo",
            label="Nouveau pseudo Minecraft",
            placeholder=d["pseudo_jeu"],
            default=d["pseudo_jeu"],
            min_length=1, max_length=64,
            on_submit=self._save_pseudo,
        )
        await interaction.response.send_modal(modal)

    async def _save_pseudo(self, interaction: Interaction, value: str) -> None:
        await update_staff_member(self.data["discord_id"], pseudo_jeu=value.strip())
        from cogs.alpha.stafflist import refresh_staff_message
        await refresh_staff_message(interaction.client, self.guild_id)
        members = await list_staff()
        await interaction.response.edit_message(
            view=EditListView(self.guild_id, self.owner_id, members)
        )

    async def _on_grade(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(
            view=_GradeSelectView(
                guild_id=self.guild_id,
                owner_id=self.owner_id,
                discord_id=self.data["discord_id"],
                member_name=self.data["pseudo_jeu"],
                on_grade=self._save_grade,
            )
        )

    async def _save_grade(
        self, interaction: Interaction, discord_id: int, member_name: str, grade: str | None
    ) -> None:
        await update_staff_member(discord_id, grade=grade)
        from cogs.alpha.stafflist import refresh_staff_message
        await refresh_staff_message(interaction.client, self.guild_id)
        members = await list_staff()
        await interaction.response.edit_message(
            view=EditListView(self.guild_id, self.owner_id, members)
        )

    async def _on_emoji(self, interaction: Interaction) -> None:
        d = self.data
        modal = TextModal(
            title="Modifier l'emoji skin",
            label="Nouvel emoji skin head",
            placeholder="<:Tete_Pseudo:000000000000000000>",
            default=d["skin_head_emoji"],
            min_length=0, max_length=128,
            on_submit=self._save_emoji,
        )
        await interaction.response.send_modal(modal)

    async def _save_emoji(self, interaction: Interaction, value: str) -> None:
        await update_staff_member(self.data["discord_id"], skin_head_emoji=value.strip())
        from cogs.alpha.stafflist import refresh_staff_message
        await refresh_staff_message(interaction.client, self.guild_id)
        members = await list_staff()
        await interaction.response.edit_message(
            view=EditListView(self.guild_id, self.owner_id, members)
        )

    async def _on_back(self, interaction: Interaction) -> None:
        await _back_to_main(interaction, self.owner_id)


# ════════════════════════════════════════════════════════════
# ✅ Sous-vue : Confirmation suppression
# ════════════════════════════════════════════════════════════

class _ConfirmRemoveView(LayoutView):
    def __init__(self, guild_id: int, owner_id: int, member_data: dict) -> None:
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.data = member_data
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.owner_id

    def _build(self) -> None:
        d = self.data
        label = GRADE_LABELS.get(d["grade"], d["grade"]) if d["grade"] else "*Aucun grade*"
        badges = build_member_badges(d)
        c = Container()
        c.add_item(TextDisplay("## ⚠️ Confirmer la suppression"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"Retirer **{d['pseudo_jeu']}**{badges} (<@{d['discord_id']}>) de la liste staff ?\n"
            f"Grade : **{label}**\n\n"
            f"*Aucun message ni rôle Discord ne sera modifié.*"
        ))
        c.add_item(Separator())

        btn_confirm = Button(label="✅ Confirmer", style=ButtonStyle.danger, custom_id="cr_confirm")
        btn_cancel  = Button(label="↩️ Annuler",  style=ButtonStyle.secondary, custom_id="cr_cancel")
        btn_confirm.callback = self._on_confirm
        btn_cancel.callback  = self._on_cancel
        c.add_item(ActionRow(btn_confirm, btn_cancel))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_confirm(self, interaction: Interaction) -> None:
        await remove_staff_member(self.data["discord_id"])
        from cogs.alpha.stafflist import refresh_staff_message
        await refresh_staff_message(interaction.client, self.guild_id)
        members = await list_staff()
        await interaction.response.edit_message(
            view=EditListView(self.guild_id, self.owner_id, members)
        )

    async def _on_cancel(self, interaction: Interaction) -> None:
        await _back_to_main(interaction, self.owner_id)


# ════════════════════════════════════════════════════════════
# ❌ Sous-vue : Membre introuvable
# ════════════════════════════════════════════════════════════

class _NotFoundView(LayoutView):
    def __init__(self, guild_id: int, owner_id: int, member_name: str) -> None:
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.owner_id = owner_id
        c = Container()
        c.add_item(TextDisplay("## ❌ Membre introuvable"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**{member_name}** n'est pas dans la liste du staff Alpha."
        ))
        c.add_item(Separator())
        btn = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="nf_back")
        btn.callback = self._on_back
        c.add_item(ActionRow(btn))
        self.add_item(c)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.owner_id

    async def _on_back(self, interaction: Interaction) -> None:
        await _back_to_main(interaction, self.owner_id)


# ════════════════════════════════════════════════════════════
# 📝 Modal d'ajout (pseudo + emoji)
# ════════════════════════════════════════════════════════════

class _AddStaffModal(discord.ui.Modal):
    def __init__(self, member_name: str, grade_label: str, on_submit) -> None:
        super().__init__(title=f"Ajouter — {grade_label}")
        self._on_submit = on_submit

        self.pseudo = discord.ui.TextInput(
            label="Pseudo Minecraft",
            placeholder=f"Ex: {member_name}",
            min_length=1, max_length=64,
            required=True,
        )
        self.emoji = discord.ui.TextInput(
            label="Emoji skin head (optionnel)",
            placeholder="<:Tete_Pseudo:000000000000000000>",
            min_length=0, max_length=128,
            required=False,
        )
        self.add_item(self.pseudo)
        self.add_item(self.emoji)

    async def on_submit(self, interaction: Interaction) -> None:
        await self._on_submit(interaction, (self.pseudo.value, self.emoji.value or ""))