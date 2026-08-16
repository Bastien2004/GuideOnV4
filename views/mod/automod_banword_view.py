"""
views/mod/automod_banword_view.py — Configuration du système Ban Word.

Éléments :
  - toggle activation
  - liste des mots (paginée si nombreuse)
  - ajout d'un mot (modal)
  - retrait d'un mot (modal — pas de select pour rester cohérent avec le
    choix général "pas de select" du projet côté /dev permissions)
  - purge complète (avec confirmation intégrée)
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container, warning_container
from utils.managers import mod_automod_banword_manager as banword_mgr
from views._components.base_view import BaseLayoutView
from views._components.text_modal import TextModal


MAX_WORD_LENGTH = 100
WORDS_PER_PAGE = 30  # affichage inline uniquement


class AutomodBanwordView(BaseLayoutView):
    """Configuration du système ban word."""

    def __init__(
        self, *, guild: discord.Guild, owner_id: int, cfg: dict, words: list[str],
        parent_dashboard,
    ):
        super().__init__(owner_id=owner_id, timeout=300)
        self.guild = guild
        self.cfg = cfg
        self.words = words
        self.parent_dashboard = parent_dashboard
        self._build()

    @classmethod
    async def build(
        cls, *, guild: discord.Guild, owner_id: int, parent_dashboard,
    ) -> "AutomodBanwordView":
        cfg = await banword_mgr.load_config(guild.id)
        words = await banword_mgr.list_words(guild.id)
        return cls(
            guild=guild, owner_id=owner_id, cfg=cfg, words=words,
            parent_dashboard=parent_dashboard,
        )

    async def _refresh(self, interaction: Interaction) -> None:
        self.cfg = await banword_mgr.load_config(self.guild.id)
        self.words = await banword_mgr.list_words(self.guild.id)
        self.clear_items()
        self._build()
        await self.push_update(interaction)

    def _build(self) -> None:
        container = Container()
        enabled = self.cfg.get("enabled", False)

        # ── Header ────────────────────────────────────────
        state_dot = "🟢" if enabled else "🔴"
        state_label = "Activé" if enabled else "Désactivé"
        container.add_item(TextDisplay(f"# 🚫 Ban Word · {state_dot} {state_label}"))
        container.add_item(TextDisplay(
            "-# Bloque tout message contenant un mot de la liste. Le système "
            "reconnaît les contournements courants (accents, chiffres, "
            "espaces, caractères spéciaux)."
        ))
        container.add_item(Separator())

        # ── Toggle activation ────────────────────────────
        toggle_label = "Désactiver le système" if enabled else "Activer le système"
        toggle_emoji = "🔴" if enabled else "🟢"
        toggle_style = ButtonStyle.danger if enabled else ButtonStyle.success

        btn_toggle = Button(label=toggle_label, emoji=toggle_emoji, style=toggle_style)
        btn_toggle.callback = self._on_toggle

        container.add_item(Section(
            TextDisplay(
                "**⚡ Activation**\n"
                "-# Une fois activé, chaque message sera analysé avant publication."
            ),
            accessory=btn_toggle,
        ))
        container.add_item(Separator())

        # ── Liste des mots ───────────────────────────────
        container.add_item(TextDisplay(
            f"**📋 Liste des mots bannis** ({len(self.words)})"
        ))
        if not self.words:
            container.add_item(TextDisplay("-# *Aucun mot dans la liste.*"))
        else:
            display = self.words[:WORDS_PER_PAGE]
            body = " · ".join(f"`{w}`" for w in display)
            if len(self.words) > WORDS_PER_PAGE:
                body += f"\n-# *… et {len(self.words) - WORDS_PER_PAGE} mots de plus (non affichés)*"
            container.add_item(TextDisplay(body))

        # Actions sur la liste
        btn_add = Button(label="Ajouter un mot", emoji="➕", style=ButtonStyle.success)
        btn_add.callback = self._on_add_word

        btn_remove = Button(
            label="Retirer un mot", emoji="➖", style=ButtonStyle.danger,
            disabled=not self.words,
        )
        btn_remove.callback = self._on_remove_word

        btn_clear = Button(
            label="Tout vider", emoji="🗑️", style=ButtonStyle.danger,
            disabled=not self.words,
        )
        btn_clear.callback = self._on_clear_words

        container.add_item(ActionRow(btn_add, btn_remove, btn_clear))
        container.add_item(Separator())

        # ── Retour ───────────────────────────────────────
        btn_back = Button(label="Retour", emoji="↩️", style=ButtonStyle.secondary)
        btn_back.callback = self._on_back
        container.add_item(ActionRow(btn_back))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideOn Studio · Auto-modération"))
        self.add_item(container)

    # ────────────────────────────────────────────────────────
    # Callbacks
    # ────────────────────────────────────────────────────────

    async def _on_toggle(self, interaction: Interaction) -> None:
        current = self.cfg.get("enabled", False)
        await banword_mgr.set_enabled(self.guild.id, not current)
        await self._refresh(interaction)

    async def _on_add_word(self, interaction: Interaction) -> None:
        async def submit(inter: Interaction, value: str) -> None:
            value = (value or "").strip()
            if not value:
                await inter.response.send_message(
                    view=warning_container("Le mot ne peut pas être vide."),
                    ephemeral=True,
                )
                return
            if len(value) > MAX_WORD_LENGTH:
                await inter.response.send_message(
                    view=warning_container(
                        f"Le mot doit contenir au maximum **{MAX_WORD_LENGTH} caractères**."
                    ),
                    ephemeral=True,
                )
                return
            added = await banword_mgr.add_word(self.guild.id, value)
            if not added:
                await inter.response.send_message(
                    view=warning_container(f"Le mot `{value.lower()}` est **déjà** dans la liste."),
                    ephemeral=True,
                )
                return
            await self._refresh(inter)

        await interaction.response.send_modal(TextModal(
            title="Ajouter un mot",
            label="Mot à bannir",
            placeholder="Ex : insulte",
            required=True,
            max_length=MAX_WORD_LENGTH,
            on_submit=submit,
        ))

    async def _on_remove_word(self, interaction: Interaction) -> None:
        async def submit(inter: Interaction, value: str) -> None:
            value = (value or "").strip()
            if not value:
                await inter.response.send_message(
                    view=warning_container("Le mot ne peut pas être vide."),
                    ephemeral=True,
                )
                return
            removed = await banword_mgr.remove_word(self.guild.id, value)
            if not removed:
                await inter.response.send_message(
                    view=warning_container(f"Le mot `{value.lower()}` n'est **pas** dans la liste."),
                    ephemeral=True,
                )
                return
            await self._refresh(inter)

        await interaction.response.send_modal(TextModal(
            title="Retirer un mot",
            label="Mot à retirer",
            placeholder="Ex : insulte",
            required=True,
            max_length=MAX_WORD_LENGTH,
            on_submit=submit,
        ))

    async def _on_clear_words(self, interaction: Interaction) -> None:
        # Confirmation intégrée (transforme la vue actuelle en confirm).
        confirm_view = _build_clear_confirm_view(
            owner_id=self.owner_id, count=len(self.words),
            on_confirm=self._do_clear, on_cancel=self._back_from_confirm,
        )
        await interaction.response.edit_message(view=confirm_view)

    async def _do_clear(self, interaction: Interaction) -> None:
        await banword_mgr.clear_words(self.guild.id)
        await self._refresh(interaction)

    async def _back_from_confirm(self, interaction: Interaction) -> None:
        await self._refresh(interaction)

    async def _on_back(self, interaction: Interaction) -> None:
        from views.mod.automod_dashboard_view import AutomodDashboardView
        new_view = await AutomodDashboardView.build(
            guild=self.guild, owner_id=self.owner_id,
        )
        await interaction.response.edit_message(view=new_view)


# ============================================================
# Vue de confirmation intégrée pour la purge
# ============================================================

def _build_clear_confirm_view(
    *, owner_id: int, count: int, on_confirm, on_cancel,
) -> BaseLayoutView:
    view = BaseLayoutView(owner_id=owner_id, timeout=120)
    c = Container()
    c.add_item(TextDisplay("# 🗑️ Vider la liste des mots bannis ?"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"Tu vas supprimer **{count}** mot(s) définitivement.\n"
        "-# Cette action est irréversible."
    ))
    c.add_item(Separator())
    btn_confirm = Button(label="Confirmer", emoji="✅", style=ButtonStyle.danger)
    btn_confirm.callback = on_confirm
    btn_cancel = Button(label="Annuler", emoji="↩️", style=ButtonStyle.secondary)
    btn_cancel.callback = on_cancel
    c.add_item(ActionRow(btn_confirm, btn_cancel))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio · Auto-modération"))
    view.add_item(c)
    return view