"""
views/invite/config_view.py — Interface /invite config.

Pattern identique à views/bienvenue/config_view.py :
- fonction create_invite_view(guild_id, bot, author_id) qui construit un LayoutView
- callbacks fermés _cb_*(...) ;  _guard(author_id) vérifie auteur + admin
- wrapper class InviteConfigView avec classmethod .create() pour la commande

Contenu du panneau :
- État du système (toggle ON/OFF, alertes si activé mais incomplet)
- Rôle-récompense (RoleSelect ephemeral pour choisir, bouton "Retirer" si défini)
- Seuil d'invites requis (TextModal pour saisir un entier > 0)
- Bouton "Réinitialiser" (remet les valeurs par défaut)
"""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.container_universel import error_container
from utils.managers.invite_manager import (
    load_invite_config,
    reset_invite_config,
    save_invite_config,
)
from views._components.role_select import RoleSelect

log = logging.getLogger(__name__)


# ======================================================
# =================== UI HELPERS =======================
# ======================================================

def _state_btn(active: bool) -> Button:
    return Button(
        label="Activé" if active else "Désactivé",
        style=ButtonStyle.success if active else ButtonStyle.danger,
        emoji="🟢" if active else "🔴",
    )


def _role_label(role_id: Optional[int], guild: discord.Guild) -> str:
    """Affichage lisible d'un rôle (mention si trouvé, ID en fallback, ou 'aucun')."""
    if role_id is None:
        return "`aucun rôle`"
    role = guild.get_role(role_id)
    return role.mention if role is not None else f"`ID {role_id} (rôle introuvable)`"


# ======================================================
# =============== CONSTRUCTION DE LA VUE ===============
# ======================================================

async def create_invite_view(
    guild_id: int, bot, author_id: Optional[int] = None
) -> Optional[LayoutView]:
    """Construit l'interface /invite config. Renvoie None si guild introuvable."""
    guild = bot.get_guild(guild_id)
    if guild is None:
        log.error("Guild %s introuvable dans le cache", guild_id)
        return None

    cfg = await load_invite_config(guild_id)
    enabled = cfg.get("enabled", False)
    reward_role_id = cfg.get("reward_role_id")
    threshold = cfg.get("reward_threshold", 10)

    # Diagnostic : système activé mais incomplet ?
    issues: list[str] = []
    if enabled:
        if reward_role_id is None:
            issues.append("aucun rôle-récompense")
        elif guild.get_role(reward_role_id) is None:
            issues.append("rôle-récompense introuvable")
        if threshold <= 0:
            issues.append("seuil invalide")
    if not enabled:
        etat = "-# ⚪ Système **désactivé**"
    elif issues:
        etat = "-# ⚠️ Actif mais incomplet : " + ", ".join(issues)
    else:
        etat = "-# ✅ Système **opérationnel**"

    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay(f"# 📨 Configuration · Invitations\n{etat}"))
    container.add_item(Separator())

    # --- Bloc : état du système ---
    btn_sys = _state_btn(enabled)
    btn_sys.callback = _cb_toggle(guild_id, bot, author_id)
    container.add_item(
        Section(TextDisplay("**État du système**"), accessory=btn_sys)
    )
    container.add_item(Separator())

    # --- Bloc : rôle-récompense ---
    btn_pick_role = Button(
        label="Choisir un rôle",
        style=ButtonStyle.secondary,
        emoji="🎁",
    )
    btn_pick_role.callback = _cb_pick_role(guild_id, bot, author_id)
    container.add_item(
        Section(
            TextDisplay(
                f"### 🎁 Rôle-récompense\n-# Attribué automatiquement au seuil "
                f"d'invitations.\n-# Rôle : {_role_label(reward_role_id, guild)}"
            ),
            accessory=btn_pick_role,
        )
    )
    # Bouton "Retirer" en plus si un rôle est défini
    if reward_role_id is not None:
        btn_clear_role = Button(
            label="Retirer le rôle",
            style=ButtonStyle.danger,
            emoji="🗑️",
        )
        btn_clear_role.callback = _cb_clear_role(guild_id, bot, author_id)
        container.add_item(ActionRow(btn_clear_role))
    container.add_item(Separator())

    # --- Bloc : seuil ---
    btn_threshold = Button(
        label=f"Modifier ({threshold})",
        style=ButtonStyle.secondary,
        emoji="🎯",
    )
    btn_threshold.callback = _cb_edit_threshold(guild_id, bot, author_id)
    container.add_item(
        Section(
            TextDisplay(
                f"### 🎯 Seuil requis\n-# Nombre d'invitations à atteindre pour "
                f"obtenir le rôle.\n-# Seuil actuel : **{threshold}**"
            ),
            accessory=btn_threshold,
        )
    )
    container.add_item(Separator())

    # --- Bloc : actions globales ---
    btn_reset = Button(label="Réinitialiser", style=ButtonStyle.danger, emoji="♻️")
    btn_reset.callback = _cb_reset(guild_id, bot, author_id)
    container.add_item(ActionRow(btn_reset))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ======================================================
# ===================== CALLBACKS ======================
# ======================================================

def _guard(author_id: Optional[int]):
    async def check(interaction: Interaction) -> bool:
        if author_id is not None and interaction.user.id != author_id:
            await interaction.response.send_message(
                view=error_container(
                    "Seul l'**auteur** de la commande peut utiliser ce __menu__."
                ),
                ephemeral=True,
            )
            return False
        member = interaction.user
        if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
            await interaction.response.send_message(
                view=error_container("Vous devez être **Administrateur**."),
                ephemeral=True,
            )
            return False
        return True
    return check


async def _rerender(interaction: Interaction, guild_id: int, bot, author_id):
    new_view = await create_invite_view(guild_id, bot, author_id)
    if new_view is None:
        await interaction.response.send_message(
            view=error_container("Serveur **introuvable**."), ephemeral=True
        )
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


def _cb_toggle(guild_id, bot, author_id):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        current = (await load_invite_config(guild_id)).get("enabled", False)
        await save_invite_config(guild_id, {"enabled": not current})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_reset(guild_id, bot, author_id):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await reset_invite_config(guild_id)
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_clear_role(guild_id, bot, author_id):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await save_invite_config(guild_id, {"reward_role_id": None})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_pick_role(guild_id, bot, author_id):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        async def on_select(sel: Interaction, role_ids: list[int]):
            if not role_ids:
                return
            role_id = role_ids[0]
            role = sel.guild.get_role(role_id)
            # Garde-fous : ni @everyone, ni un rôle géré (intégration bot/booster), ni au-dessus du bot
            if role is None:
                await sel.response.send_message(
                    view=error_container("Rôle **introuvable**."),
                    ephemeral=True,
                )
                return
            if role.is_default():
                await sel.response.send_message(
                    view=error_container("Le rôle **@everyone** ne peut pas être utilisé."),
                    ephemeral=True,
                )
                return
            if role.managed:
                await sel.response.send_message(
                    view=error_container(
                        "Ce rôle est **géré** par une intégration et ne peut pas être attribué."
                    ),
                    ephemeral=True,
                )
                return
            me = sel.guild.me
            if me is not None and role >= me.top_role:
                await sel.response.send_message(
                    view=error_container(
                        f"Je ne peux pas attribuer {role.mention} : son rang est "
                        f"**supérieur ou égal** au mien."
                    ),
                    ephemeral=True,
                )
                return

            await save_invite_config(guild_id, {"reward_role_id": role_id})
            new_view = await create_invite_view(guild_id, bot, author_id)
            await sel.response.edit_message(view=new_view)

        async def on_cancel(cancel_inter: Interaction):
            new_view = await create_invite_view(guild_id, bot, author_id)
            await cancel_inter.response.edit_message(view=new_view)

        select = RoleSelect(
            placeholder="Sélectionner un rôle",
            on_select=on_select,
            min_values=1,
            max_values=1,
        )
        btn_cancel = Button(label="Annuler", style=ButtonStyle.secondary, emoji="↩️")
        btn_cancel.callback = on_cancel

        temp = LayoutView(timeout=120)
        c = Container()
        c.add_item(TextDisplay("# 🎁 Choisir le rôle-récompense"))
        c.add_item(TextDisplay("-# Attribué automatiquement au seuil d'invitations atteint."))
        c.add_item(Separator())
        c.add_item(ActionRow(select))
        c.add_item(Separator())
        c.add_item(ActionRow(btn_cancel))
        temp.add_item(c)

        await interaction.response.edit_message(view=temp)
    return cb


def _cb_edit_threshold(guild_id, bot, author_id):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        from views._components.text_modal import TextModal  # import local pour éviter cycles

        current = (await load_invite_config(guild_id)).get("reward_threshold", 10)

        async def on_submit(inter: Interaction, value: str):
            value = value.strip()
            try:
                n = int(value)
            except ValueError:
                await inter.response.send_message(
                    view=error_container("Le seuil doit être un **nombre entier**."),
                    ephemeral=True,
                )
                return
            if n <= 0:
                await inter.response.send_message(
                    view=error_container("Le seuil doit être **supérieur à 0**."),
                    ephemeral=True,
                )
                return
            if n > 10_000:
                await inter.response.send_message(
                    view=error_container("Le seuil doit être **inférieur ou égal à 10 000**."),
                    ephemeral=True,
                )
                return
            await save_invite_config(guild_id, {"reward_threshold": n})
            await _rerender(inter, guild_id, bot, author_id)

        modal = TextModal(
            title="🎯 Modifier le seuil",
            label="Nombre d'invitations requis",
            placeholder="Ex : 10",
            default=str(current),
            min_length=1,
            max_length=6,
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)
    return cb


# ======================================================
# ========== COMPAT COMMANDE : InviteConfigView ========
# ======================================================

class InviteConfigView:
    @classmethod
    async def create(cls, guild_id: int, author_id: int, bot) -> LayoutView:
        view = await create_invite_view(guild_id, bot, author_id)
        if view is None:
            return error_container(
                "**Impossible** de charger la __configuration__ (serveur introuvable)."
            )
        return view